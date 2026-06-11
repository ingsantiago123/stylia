# DIAGNÓSTICO STYLIA — Auditoría Arquitectónica y Plan de Refactorización

> **Autor**: Auditoría técnica (Arquitectura de Software / NLP editorial)
> **Fecha**: 2026-06-11
> **Alcance**: `backend/app/**` (pipeline, servicios, modelos, prompts), v0.3.0
> **Metodología**: lectura completa de `tasks_pipeline.py`, `correction.py`, `rendering.py`, `extraction.py`, `extraction_docx.py`, `prompt_builder.py`, `complexity_router.py`, `group_collector.py`, `openai_client.py`, `quality_gates.py` (firmas), `analysis.py` (estructura) y modelos ORM. Toda afirmación cita archivo y línea.

---

## Veredicto ejecutivo

STYLIA tiene una intuición de producto correcta (perfiles editoriales, rutas de complejidad, gates, HITL, conciencia estructural) montada sobre una **arquitectura de identidad rota**: el documento se parsea **tres veces con tres modelos incompatibles** (bloques visuales de PyMuPDF, párrafos de `python-docx`, índice plano `paragraph_index`) y la reconciliación entre ellos se hace por **fuzzy matching de texto** en al menos cuatro puntos del pipeline. Esto convierte cada etapa en una apuesta probabilística: el sistema no *sabe* dónde está un párrafo, lo *adivina*.

Sobre esa base se han ido apilando parches (blocks sintéticos, seeds aproximados, boundary checks, índices por prefijo de 50 caracteres, estimación lineal de páginas) que mitigan síntomas sin tocar la causa. El resultado actual incluye **defectos verificables de pérdida y corrupción de datos**, entre ellos:

1. **Los patches grupales (D.5) se pierden o corrompen entre la corrección y el render** (detalle en §1.1.4): se persisten con `paragraph_index=0`, el render candidato los deduplica contra ese índice y la restitución de `location` desde MinIO falla por mismatch de claves `None` vs `0`. En la Etapa E final además se reconstruyen **sin** `group_id` ni `structural_role`.
2. **La corrección grupal de tablas direcciona celdas equivocadas**: el prompt pide índices `fila × num_cols + columna` pero el parser los mapea contra `enumerate(blocks)`; con una sola celda vacía, una celda multipárrafo o una tabla particionada, las correcciones se aplican a celdas incorrectas o se descartan en masa (§1.1.5).
3. **En modo paralelo (feature flag activo), la etapa D.5 no se ejecuta nunca y los párrafos agrupados tampoco se omiten de la pasada individual**: toda la "conciencia estructural" desaparece silenciosamente (§1.1.3).
4. **El render destruye formato intra-párrafo por diseño**: todos los runs se colapsan al run dominante (§1.1.6).
5. **La "conciencia de paginación" es una interpolación lineal**, no un mapeo real; el manejo de saltos de página internos reparte el texto corregido **por proporción de caracteres**, que es semánticamente arbitrario (§1.2.1).

Nada de esto es reparable con más parches locales. La sección 2 define la arquitectura objetivo (modelo de nodos documentales con identidad estable + motor de reconstrucción por diff de runs) y la sección 3 el plan de migración por fases sin congelar el producto.

---

# 1. Diagnóstico Arquitectónico y Estructural

## 1.1 Crítica del pipeline actual

### 1.1.1 Defecto raíz: tres modelos de documento sin clave de identidad común

El mismo documento existe simultáneamente como:

| Representación | Quién la crea | Clave | Persistencia |
|---|---|---|---|
| Bloques visuales PDF (bbox por página) | Etapa B, PyMuPDF ([extraction.py](backend/app/services/extraction.py)) | `(page_id, block_no)` | tabla `blocks` |
| Párrafos DOCX con location string | B.5 ([extraction_docx.py:95-155](backend/app/services/extraction_docx.py#L95-L155)) | `"body:N"`, `"table:T:R:C:P"` | columna `blocks.docx_location` |
| Índice plano `paragraph_index` | D, `_collect_all_paragraphs` ([correction.py:878-909](backend/app/services/correction.py#L878-L909)) | entero posicional sobre body+tablas+headers | `patches.paragraph_index`, JSON en MinIO |

Ninguna de las tres es la fuente de verdad. Las uniones entre ellas son **heurísticas de texto**:

- **B.5 → Block**: `_guess_location_for_block()` ([extraction_docx.py:846-884](backend/app/services/extraction_docx.py#L846-L884)) matchea por texto normalizado exacto → prefijo de 80 chars → containment. Es **O(blocks × items)** (escaneo lineal por cada block) y **colisiona con texto repetido**: dos celdas "Sí", dos ítems idénticos, encabezados repetidos por sección — el primero gana (`loc in matched_locations`, línea 760-762) y el segundo queda sin enriquecer o, peor, enriquecido con la location del otro.
- **Patch → Block**: `_find_best_block()` en `_persist_patches` ([tasks_pipeline.py:282-322](backend/app/workers/tasks_pipeline.py#L282-L322)) usa un índice por **prefijo de 50 caracteres** ("primer bloque con ese prefijo gana") y, en fallback, `SequenceMatcher` sobre una ventana de páginas **estimada por interpolación lineal** (`para_idx / total_paras * num_pages`). Cualquier documento con párrafos que comparten arranque ("El presente artículo…", celdas repetidas, ítems "Ver anexo") ancla patches al block equivocado. El último fallback (línea 318-321) asigna el patch al **primer bloque de la página estimada** aunque el score sea < 0.3, es decir: prefiere atar la corrección a un bloque arbitrario antes que admitir que no sabe dónde va.
- **Anotaciones visuales → PDF**: `_generate_annotated_previews` ([rendering.py:145-231](backend/app/services/rendering.py#L145-L231)) vuelve a buscar el texto corregido **por búsqueda de substring en el PDF** con prefijos progresivos (150/70/35 chars) sobre páginas estimadas linealmente. Texto repetido = highlight en la ocurrencia equivocada; texto partido por salto de línea/columna/guionado = no encontrado y la corrección desaparece del preview sin aviso.
- **location de los patches ni siquiera vive en la base de datos**: el modelo `Patch` no tiene columna `location`; se reconstruye en cada render descargando `patches_docx.json` de MinIO e indexando por la tupla `(paragraph_index, original_text[:50])` ([tasks_pipeline.py:513-526 y 611-626](backend/app/workers/tasks_pipeline.py#L513-L526)). MinIO es así una **segunda fuente de verdad** desincronizable de la primera.

**Consecuencia**: el requisito core #4 (Safe-Replace) y #6 (trazabilidad) son estructuralmente imposibles de garantizar. El sistema puede aplicar la corrección correcta al párrafo equivocado y reportarla como exitosa.

### 1.1.2 Pipeline monolítico, no idempotente y con doble contabilidad de estados

- `process_document_pipeline` ([tasks_pipeline.py:870+](backend/app/workers/tasks_pipeline.py#L870)) ejecuta A→E en **un solo task Celery** con `max_retries=3`. Un fallo en E (render) reintenta **desde A**, re-pagando todas las llamadas LLM de C y D. No hay checkpoints ni resumibilidad: el costo de un fallo tardío es el costo del documento entero.
- El "semáforo" de pipelines concurrentes es un `SET` de Redis con `expire` global de 2h ([tasks_pipeline.py:94-115](backend/app/workers/tasks_pipeline.py#L94-L115)): el `expire` renueva el TTL de **todo el set** con cada adquisición, y un worker muerto deja el slot ocupado hasta 2h. Es fail-open (correcto) pero también leak-by-design.
- `_last_progress_commit` es un dict **a nivel de módulo** ([tasks_pipeline.py:132](backend/app/workers/tasks_pipeline.py#L132)) que crece sin límite y sobrevive entre documentos dentro del worker prefork.
- Estados no canónicos: la etapa B.5 escribe `status="extracted_docx"` ([tasks_pipeline.py:1033](backend/app/workers/tasks_pipeline.py#L1033)), que no existe en la máquina de estados documentada en CLAUDE.md. El frontend que hace polling sobre `status` ve estados fantasma.
- `tempfile.mktemp` ([tasks_pipeline.py:720](backend/app/workers/tasks_pipeline.py#L720), [correction.py:591](backend/app/services/correction.py#L591)) es la API insegura y deprecada; debe ser `NamedTemporaryFile`/`mkstemp`.
- El re-procesamiento borra páginas (y por cascada blocks y patches) **antes** de saber si el nuevo run tendrá éxito ([tasks_pipeline.py:904-917](backend/app/workers/tasks_pipeline.py#L904-L917)): un reproceso fallido deja el documento sin su historia anterior.
- Si `original_format != "docx"` y hay patches, `_persist_patches` marca el documento `completed` y descarta todo ([tasks_pipeline.py:244-256](backend/app/workers/tasks_pipeline.py#L244-L256)): la ruta PDF es un camino muerto disfrazado de éxito.

### 1.1.3 Bifurcación secuencial/paralela incoherente: la ruta paralela ignora la conciencia estructural

Esta es una de las peores propiedades del diseño actual: existen **dos pipelines de corrección distintos** (secuencial y `parallel_correction_enabled`) que han divergido.

- En la ruta secuencial: B.5 calcula `_grouped_locations`, D los omite, y D.5 corrige los grupos ([tasks_pipeline.py:1058-1074, 1320, 1384-1404](backend/app/workers/tasks_pipeline.py#L1384-L1404)).
- En la ruta paralela: `_dispatch_parallel_correction` ([tasks_pipeline.py:694-863](backend/app/workers/tasks_pipeline.py#L694-L863)) **no calcula ni propaga índices agrupados** (no hay ninguna referencia a `grouped_paragraph_indexes` ni a `compute_grouped_paragraph_indexes_sync` en el archivo — verificado por búsqueda), y el callback `assemble_correction_results` **nunca invoca `correct_groups_for_doc_sync`** (única llamada en el archivo: línea 1386-1387, dentro de la ruta secuencial). Resultado con el flag activo: las listas y tablas se corrigen ítem a ítem sin contexto de conjunto (lo que B.5/D.5 existían para evitar) **y** la pasada grupal no ocurre. La función `compute_grouped_paragraph_indexes_sync` ([correction.py:1796-1822](backend/app/services/correction.py#L1796-L1822)) y el parámetro `grouped_paragraph_indexes` de `correct_batch_with_llm_sync` ([correction.py:1023](backend/app/services/correction.py#L1023)) son **código muerto** en producción paralela.
- La continuidad inter-lote es de juguete: el "seed" del lote N es el texto **post-LT (no post-LLM)** del último párrafo del lote N−1, truncado a **200 caracteres** ([tasks_pipeline.py:791-807](backend/app/workers/tasks_pipeline.py#L791-L807)). El `check_batch_boundaries` posterior re-corrige **solo el primer párrafo** de cada lote ([correction.py:1192-1327](backend/app/services/correction.py#L1192-L1327)); los párrafos 2..k del lote siguen habiendo sido corregidos con una ventana de contexto degradada y nadie lo audita.

### 1.1.4 Cadena de persistencia de patches: los patches grupales mueren entre D.5 y E

Cadena de defectos verificable leyendo `_persist_patches` → `_run_candidate_render` → `_run_stage_e`:

1. Los patches de D.5 salen con `paragraph_index=None` ([correction.py:1699](backend/app/services/correction.py#L1699)).
2. `_persist_patches` hace `para_idx = patch_data.get("paragraph_index", 0) or 0` ([tasks_pipeline.py:329](backend/app/workers/tasks_pipeline.py#L329)): **todos los patches grupales quedan persistidos con `paragraph_index=0`**.
3. `_run_candidate_render` deduplica patches por `paragraph_index` ("un dict por párrafo", [tasks_pipeline.py:490-511](backend/app/workers/tasks_pipeline.py#L490-L511)): todos los patches grupales colisionan en `pidx=0` con el eventual patch individual del párrafo 0 — **sobrevive uno, se descartan los demás** del render candidato.
4. La restitución de `location` desde MinIO indexa por `(sp.get("paragraph_index", 0), prefijo)`: en el JSON el valor es `None` (el `get` con default no aplica si la clave existe con valor `None`), en la BD es `0` → la clave nunca matchea → `location=""` → `_get_paragraph_by_location("")` retorna `None` → patch omitido como `no_paragraph` ([rendering.py:710-729](backend/app/services/rendering.py#L710-L729)).
5. En la Etapa E final, los dicts se reconstruyen desde la BD **sin `group_id`, `group_call_index` ni `structural_role`** ([tasks_pipeline.py:590-609](backend/app/workers/tasks_pipeline.py#L590-L609)), de modo que aunque la location se resolviera, el render los trataría como individuales: la sanitización de prefijos y el orden grupal de `_apply_group_patches` ([rendering.py:732-763](backend/app/services/rendering.py#L732-L763)) no se ejecutan jamás en el documento final.

Es decir: **toda la inversión de B.5 + D.5 (detección, prompts grupales, gates de paralelismo) produce patches que el usuario revisa en la UI pero que el motor de render final no puede aplicar correctamente**. El código de render group-aware solo es alcanzable desde el flujo en memoria del pipeline secuencial viejo, no desde el flujo persistido real (persist → candidate → review → finalize).

Defecto cosmético pero sintomático en el mismo archivo: el log de mismatch imprime `[...][:0]` — siempre cadena vacía ([rendering.py:806-810](backend/app/services/rendering.py#L806-L810)). El mensaje de diagnóstico clave del Safe-Replace lleva versiones sin mostrar el texto real.

### 1.1.5 Corrección grupal de tablas: desalineamiento de índices LLM ↔ blocks

`build_group_user_prompt_table` instruye al LLM: `"index" = fila * num_cols + columna` y etiqueta cada celda con ese índice absoluto ([prompt_builder.py:1061, 1071-1075](backend/app/services/prompt_builder.py#L1061)). Pero el parser hace `indexed.get(i)` con `i = enumerate(blocks)` ([correction.py:1554-1571, 1630](backend/app/services/correction.py#L1630)), donde `blocks` es la lista **compactada y ordenada row-major** de `group_collector` ([group_collector.py:59-67](backend/app/services/group_collector.py#L59-L67)). Las dos numeraciones solo coinciden si la tabla es perfecta. Casos reales:

- **Celda vacía** (sin Block): la enumeración se compacta, `i` deja de coincidir con `r*cols+c` para todas las celdas posteriores → **cada corrección se aplica a la celda anterior a la que el LLM corrigió**. Corrupción silenciosa de datos.
- **Celda multipárrafo** (`table:T:R:C:P` con P>0): dos blocks comparten `r*cols+c` → el prompt lista el mismo índice dos veces, la respuesta del LLM solo puede dirigirse a uno, y la deduplicación "primera ocurrencia gana" ([correction.py:1565-1571](backend/app/services/correction.py#L1565-L1571)) descarta el resto.
- **Tabla particionada** (`partition_table_group`, >60 celdas): los chunks 2+ contienen filas con `row_index` absoluto alto → el LLM devuelve índices `r*cols+c` ≥ `n` del chunk → **el filtro de rango `idx >= n` los descarta todos** ([correction.py:1563](backend/app/services/correction.py#L1563)). Las tablas grandes no se corrigen a partir del segundo chunk, y lo que sobreviva del primero puede estar desalineado.
- **Celdas verticalmente combinadas**: `python-docx` repite el mismo objeto celda en `row.cells` para celdas merged → B.5 genera locations distintas con el mismo texto, infla `item_count` y produce patches duplicados sobre el mismo párrafo subyacente.

Además, el docstring de `partition_table_group` promete "manteniendo header y totals al inicio/fin de cada sub-batch" ([group_collector.py:102-109](backend/app/services/group_collector.py#L102-L109)) y la implementación **no lo hace**: corta por rangos de filas contiguos sin replicar header ni totals. Los chunks 2+ pierden los encabezados de columna que el prompt necesita para la uniformidad.

### 1.1.6 Motor de reconstrucción (Etapa E): destructivo por diseño

`_apply_text_to_paragraph_runs` ([rendering.py:597-652](backend/app/services/rendering.py#L597-L652)):

- **Colapsa todos los runs en `runs[0]`** copiando el formato del "run dominante" (el de más caracteres). Un párrafo con una palabra en **negrita**, una *cursiva*, un superíndice o un cambio de fuente a mitad de frase pierde ese formato en cuanto el LLM toca **una sola coma**. Esto viola frontalmente el requisito "preserva formato original". El formato a nivel de párrafo sobrevive; el formato a nivel de carácter (rPr por run) se aplana sistemáticamente.
- Las referencias de **nota al pie** (`w:footnoteReference`), campos (`w:fldChar`/`instrText`, TOC, referencias cruzadas), marcas de comentario y `w:drawing` inline residen en runs intermedios. `_clear_run_text_preserve_breaks` solo elimina `w:t`, así que esos elementos sobreviven físicamente, pero **quedan reordenados respecto al texto**: la llamada a la nota al pie que estaba tras la palabra X queda ahora al final de un párrafo cuyo texto completo vive en el run 0.
- El check de seguridad `current_text != original_text → mismatch` ([rendering.py:723-725](backend/app/services/rendering.py#L723-L725)) compara con `.strip()` solo en un lado del primer operando (`paragraph.text.strip()` vs `original_text` sin strip — los patches guardan texto ya stripped, así que funciona de casualidad) y descarta silenciosamente; el patch queda en BD como `applied=True` igualmente, porque el `update` masivo de Etapa E marca aplicados **todos** los patches aceptados sin consultar el resultado real del render ([tasks_pipeline.py:653-661](backend/app/workers/tasks_pipeline.py#L653-L661)). **La BD afirma que se aplicaron correcciones que el render omitió.**
- El render se hace **siempre desde el DOCX original**: si el editor reabre y re-finaliza, no hay composición incremental de versiones; correcto como decisión, pero entonces `render_version` es decorativo.

### 1.1.7 Motor de prompts: parámetros muertos, contratos frágiles y contradicciones

Lo bueno: separación system/user cacheable, bloques declarativos por tipo, perfil data-driven. Lo malo:

1. **`block_meta`, `page_no` y `total_pages` de `build_user_prompt` no los pasa ningún caller real**: `_correct_single_paragraph` invoca sin ellos ([correction.py:361-375](backend/app/services/correction.py#L361-L375)). Conclusión grave: **toda la metadata estructural de B.5 (style_name, list_position/total, table_cell_role, niveles) jamás llega al prompt individual** — el "CONTEXTO ESTRUCTURAL DEL ELEMENTO" se construye con un meta vacío ([prompt_builder.py:370-382](backend/app/services/prompt_builder.py#L370-L382)) y solo emite reglas genéricas por tipo. La conciencia estructural a nivel 3 existe en la BD y muere ahí. Y la "conciencia de paginación" del prompt (`PÁGINA: N de M`) es **inalcanzable**: código muerto.
2. **El router hace inalcanzables ramas enteras del prompt builder**: `cita` → SKIP ([complexity_router.py:77-78](backend/app/services/complexity_router.py#L77-L78)), por lo que `_build_cita` (reglas de OCR/mojibake) **nunca se ejecuta**. Lo mismo para `titulo`/`subtitulo`/`encabezado`/`footer` (SKIP por `_SKIP_TYPES`): las reglas "NO añadir punto final", `rewrite_ratio > 0.10 → skip` etc. de `_build_titulo` son letra muerta — los títulos solo reciben LanguageTool, que sí puede introducir cambios que esas reglas pretendían vetar.
3. **Contradicción normativa entre rutas**: el prompt individual de ítem de lista ordena "Estandariza la numeración inicial… (ej. de '1.', '2)', '3.' a '1.', '2.', '3.')" ([prompt_builder.py:650](backend/app/services/prompt_builder.py#L650)), mientras el prompt grupal manual ordena "NO cambies '2)' a '2.'… respétalo" ([prompt_builder.py:987-993](backend/app/services/prompt_builder.py#L987-L993)). El mismo documento recibe políticas opuestas según qué pasada lo procese (y en modo paralelo, solo la individual existe — ver §1.1.3).
4. **Contrato de salida débil**: se usa `response_format={"type": "json_object"}` ([openai_client.py:195](backend/app/utils/openai_client.py#L195)), no Structured Outputs con `json_schema` + `strict:true`. El esquema es texto del system prompt; `correct_with_profile` hace `json.loads` directo (sin el `_safe_json_parse` tolerante que sí tiene la ruta grupal) y ante cualquier excepción retorna `None` → **fallback silencioso a solo-LT** registrado como warning. Los campos `confidence` y `rewrite_ratio` son **autoreportados por el modelo** y se persisten como si fueran métricas; el `rewrite_ratio` real se computa solo en gates con umbral fijo 0.35 desacoplado del `max_rewrite_ratio` del perfil.
5. **Presupuesto de tokens sin control**: los `protected_terms` se acumulan desde tres fuentes (perfil + análisis C con n-gramas de frecuencia ≥3 + C.6 globales, [tasks_pipeline.py:1158-1166, 1243-1250](backend/app/workers/tasks_pipeline.py#L1158-L1166)) y se inyectan **completos en cada prompt** (`PROTEGER TÉRMINOS: …`, [prompt_builder.py:317-319](backend/app/services/prompt_builder.py#L317-L319)). Un documento de 300 páginas puede meter cientos de bigramas ruidosos en cada una de miles de llamadas: costo cuadrático de contexto y dilución de la instrucción. Mientras tanto `openai_max_tokens=500` por defecto trunca la respuesta JSON de párrafos largos en ruta editorial → JSON inválido → fallback silencioso (combinación perversa de 4 y 5).
6. **`max_length` se valida post-hoc descartando todo** ([openai_client.py:230-238](backend/app/utils/openai_client.py#L230-L238)): si la corrección excede el ratio, se tira la corrección completa en lugar de pedir reintento o recorte. Con `max_expansion=1.15` y párrafos cortos, una corrección legítima de "Sr." → "Señor" puede superar el límite y perderse.
7. **El contexto previo es una ventana de texto crudo truncado** (200 chars por párrafo, [prompt_builder.py:404-440](backend/app/services/prompt_builder.py#L404-L440)) cuyo único propósito real es coherencia local, pero cuyo costo es lineal por llamada; no existe memoria de *decisiones* (qué término se normalizó a qué, qué grafía se eligió), que es lo que de verdad da consistencia inter-párrafo. La consistencia terminológica del documento depende de que el LLM la infiera de 15 fragmentos truncados.
8. **El system prompt mezcla el contrato individual y el grupal** ([prompt_builder.py:82-84](backend/app/services/prompt_builder.py#L82-L84)): describe el modo grupal dentro del prompt de párrafo individual, ruido permanente para el 95% de las llamadas.

### 1.1.8 Etapa C y router: clasificación heurística que decide gasto y conducta

- `classify_paragraph` es heurístico (ubicación, estilo, regex de captions); las clasificaciones gobiernan ruta (gasto LLM) y bloques de prompt, pero **no hay medición de su precisión** ni un gold-set. Un narrativo clasificado como `lista` recibe reglas de brevedad; una cita no detectada se reescribe.
- La extracción de términos por n-gramas frecuencia ≥3 ([analysis.py:226-309](backend/app/services/analysis.py#L226)) marca términos "protegidos" sin lematización ni filtro de stopwords sintácticas serias → contamina prompts y gates (`gate_protected_terms` puede rechazar correcciones legítimas porque un bigrama ruidoso cambió).
- Secciones fallback "cada ~30 párrafos" ([analysis.py:206](backend/app/services/analysis.py#L206)): los batch boundaries "alineados a secciones" del modo paralelo se alinean entonces a cortes arbitrarios.
- El router usa **una sola regex** de subordinadas para decidir EDITORIAL ([complexity_router.py:42-44](backend/app/services/complexity_router.py#L42-L44)); no considera perplejidad, densidad de errores LT por longitud, ni señal del análisis.

### 1.1.9 Modelo de datos: entidad quimera, duplicación y ausencia de migraciones

- **`Block` es una quimera**: nació como bloque visual PDF (bbox, font_info, page_id NOT NULL) y se le atornillaron 15 columnas estructurales DOCX. Los **blocks sintéticos** de B.5 se cuelgan de la página 1 con `bbox=(0,0,0,0)` ([extraction_docx.py:784-823](backend/app/services/extraction_docx.py#L784-L823)): mienten sobre su posición, contaminan cualquier consulta por página y obligan a recordar que "la asignación es solo administrativa".
- **`blocks.element_group_id` no tiene FK real** ("la integridad referencial se mantiene a nivel app", [block.py:85-90](backend/app/models/block.py#L85-L90)) — es decir, no se mantiene. Borrar un ElementGroup deja punteros colgantes.
- **`Patch` no tiene `doc_id` ni `location`**: toda consulta de correcciones de un documento es un triple join Patch→Block→Page; la location vive solo en MinIO (§1.1.1). Además `_persist_patches` crea **una fila Patch por cada "change" del LLM repitiendo el `corrected_text` completo** ([tasks_pipeline.py:361-394](backend/app/workers/tasks_pipeline.py#L361-L394)): la tabla se infla N× y el review granular es ilusorio — aceptar un change y rechazar otro del mismo párrafo es incoherente porque ambos portan el mismo texto final completo. El render con `accepted_only` aplicará el texto íntegro aunque el editor haya rechazado la mitad de los cambios de ese párrafo.
- **No hay sistema de migraciones**: `scripts/migrate_b5.py` ejecutado con `docker cp` a mano. Sin Alembic no hay reproducibilidad de esquema entre entornos ni reversibilidad.
- `llm_usage.paragraph_index=-1` como sentinel para grupos: el esquema codifica significado en valores mágicos.
- `correction_batches.results_json` y los JSON intermedios de MinIO (`lt_results.json`, `all_paragraphs.json`, `analysis.json`) duplican estado de BD sin TTL ni invalidación: basura acumulativa.

## 1.2 Brechas de contexto (dónde exactamente se pierde el hilo)

| # | Brecha | Punto exacto | Efecto |
|---|--------|--------------|--------|
| 1 | **Paginación ficticia** | `est_page = idx/total*num_pages` en `_find_best_block` ([tasks_pipeline.py:300](backend/app/workers/tasks_pipeline.py#L300)), `save_paragraph_locations_sync` ([correction.py:937-948](backend/app/services/correction.py#L937-L948), comentado como "heurística lineal"), y anotaciones ([rendering.py:155-156](backend/app/services/rendering.py#L155-L156)) | `paragraph_locations.page_start` es una invención persistida como dato; anotaciones buscan en páginas equivocadas; el requisito core #3 no está implementado, está simulado |
| 2 | **Saltos de página internos** | `_apply_text_with_page_break` divide el texto corregido por **fracción de caracteres** del original ([rendering.py:416-478](backend/app/services/rendering.py#L416-L478)) | El corte cae a mitad de cláusula reescrita; además solo cubre `w:br type="page"` manual — los saltos por reflujo (la inmensa mayoría) son invisibles para todo el sistema |
| 3 | **Párrafos partidos entre páginas del PDF** | Etapa B crea blocks por página; nunca se fusionan fragmentos del mismo párrafo entre páginas | El matching B.5↔Block falla justo en los párrafos que cruzan página (el caso que la "continuidad" debía proteger), forzando sintéticos o enriquecimiento perdido |
| 4 | **Contexto inter-lote degradado** | seeds post-LT truncados a 200 chars; corrección de frontera solo para el primer párrafo del lote (§1.1.3) | Tono/terminología derivan entre lotes; documentos largos (los que usan la ruta paralela) son los que peor coherencia reciben |
| 5 | **Elementos invisibles al parser** | `_collect_all_paragraphs` y B.5 solo ven `doc.paragraphs` + `doc.tables` top-level + headers/footers | **Cuadros de texto** (`w:txbxContent`), **tablas anidadas** (`cell.tables`), **footnotes/endnotes** (parts separadas), **content controls** (SDT) no se corrigen ni se cuentan; las locations `body:N` ni siquiera son estables si Word inserta un párrafo |
| 6 | **Listas interrumpidas** | la detección manual exige índices **contiguos en `items`** ([extraction_docx.py:326-366](backend/app/services/extraction_docx.py#L326-L366)), y `items` concatena body, luego tablas, luego headers | Una lista nativa partida por un párrafo intermedio se trocea en grupos; el contexto "preceding/following paragraph" del prompt grupal puede pertenecer a otra parte del documento |
| 7 | **El LLM nunca ve dónde está** | `page_no`/`block_meta` muertos (§1.1.7-1) | El requisito core #5 (cada fragmento sabe dónde está y qué función cumple) se cumple solo a nivel de `paragraph_type` heurístico |
| 8 | **Grupos vs pasada individual desincronizados en paralelo** | §1.1.3 | Doble política de corrección según una feature flag de rendimiento |

---

# 2. Diseño de la Nueva Arquitectura (el "deber ser")

## 2.1 Principio rector

**Una sola fuente de verdad estructural: el árbol de nodos del documento (Document AST), con identidad estable por nodo.** El PDF es una *proyección* (para layout y previews), nunca una fuente de identidad. Todo lo demás (patches, prompts, render, UI) referencia `node_id`, jamás texto ni índices posicionales.

## 2.2 Modelo de datos documental

### 2.2.1 Tabla central: `document_nodes`

```sql
CREATE TABLE document_nodes (
    id              UUID PRIMARY KEY,
    doc_id          UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    revision        INT  NOT NULL DEFAULT 1,          -- versión del parse
    parent_id       UUID REFERENCES document_nodes(id) ON DELETE CASCADE,
    node_type       TEXT NOT NULL,                    -- 'section'|'heading'|'paragraph'|'list'|'list_item'|'table'|'table_row'|'table_cell'|'figure'|'caption'|'footnote'|'textbox'|'header'|'footer'|'toc_field'
    order_key       TEXT NOT NULL,                    -- clave fraccional lexicográfica (orden total del documento)
    depth           INT  NOT NULL,
    -- ANCLA OXML: identidad física en el DOCX, NO texto
    oxml_anchor     JSONB NOT NULL,                   -- {part:'document'|'footnotes'|'header2', xpath_idx:[..], rsid?, paraId?}
    content_hash    CHAR(16) NOT NULL,                -- xxhash64 del texto normalizado (detección de drift, NO matching primario)
    text            TEXT,                             -- texto plano del nodo (NULL para contenedores)
    runs_json       JSONB,                            -- [{text, rpr_hash, flags:{bold,italic,...}, specials:['footnote_ref','field',...]}]
    attrs           JSONB NOT NULL DEFAULT '{}',      -- tipados por node_type: heading{level,style}, list_item{list_id,position,fmt,detection}, table_cell{row,col,role,colspan,rowspan,dtype}
    role            TEXT,                             -- clasificación editorial (paragraph_type), separada de node_type
    role_confidence REAL,
    page_start      INT, page_end       INT,          -- de la proyección PDF (ver 2.5), nullable
    protected       BOOLEAN NOT NULL DEFAULT FALSE,   -- citas, fórmulas, regiones marcadas
    UNIQUE (doc_id, revision, order_key)
);
CREATE INDEX ON document_nodes (doc_id, revision, node_type);
CREATE INDEX ON document_nodes (parent_id);
```

Decisiones clave:

- **`oxml_anchor`**: ruta posicional dentro del part OXML (índice de `w:p`/`w:tbl` en el body, índices anidados para celdas) **capturada en el mismo parse que produce el texto**. Como el DOCX original es inmutable durante el ciclo de corrección (se versiona en MinIO con hash del contenido), el anchor es determinista — se elimina el fuzzy matching por completo. `w14:paraId` (Word lo emite en documentos modernos) se guarda cuando existe como verificación adicional.
- **`content_hash`**: solo como *tripwire*: en el render, si el hash del párrafo destino no coincide con el del parse, el patch se aborta con error explícito (no silencioso) y el documento se marca para re-parse. Nunca se usa para "buscar" el párrafo.
- **`order_key` fraccional** (estilo LexoRank): orden total del documento que sobrevive a inserciones de nodos sintéticos sin renumerar, y resuelve la intercalación correcta body/tablas que hoy se pierde.
- **`runs_json`**: el mapa de runs con hash de `rPr` por run es lo que habilita el motor de reconstrucción no destructivo (§2.4).
- **`node_type` ≠ `role`**: la estructura física (es una celda) se separa de la función editorial (es un total). Hoy ambas cosas se mezclan en `paragraph_type`.
- **Listas y tablas son nodos contenedores** (`list`, `table`) con hijos: el `ElementGroup` actual desaparece como tabla aparte; un grupo es simplemente un subárbol, y "pertenece a un grupo" es `parent.node_type IN ('list','table_row')`. Imposible desincronizar.

### 2.2.2 `patches` rediseñada

```sql
CREATE TABLE patches (
    id              UUID PRIMARY KEY,
    doc_id          UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    node_id         UUID NOT NULL REFERENCES document_nodes(id) ON DELETE CASCADE,
    node_revision   INT  NOT NULL,
    original_text   TEXT NOT NULL,
    corrected_text  TEXT NOT NULL,
    changes         JSONB NOT NULL DEFAULT '[]',      -- TODOS los cambios del nodo en UNA fila
    edit_ops        JSONB,                            -- opcodes del diff (para render por runs y para review granular)
    source          TEXT NOT NULL,                    -- 'lt'|'llm'|'lt+llm'|'substitution'|'llm-group'|'audit'
    route_taken     TEXT, model_used TEXT,
    group_call_id   TEXT,                             -- id de la llamada grupal compartida (trazabilidad), SIN semántica de render
    confidence_reported REAL, rewrite_ratio_computed REAL,
    gate_results    JSONB, review_status TEXT NOT NULL DEFAULT 'pending',
    review_reason   TEXT, edited_text TEXT,
    applied_at      TIMESTAMPTZ,                      -- NULL hasta verificación real post-render
    apply_result    TEXT,                             -- 'ok'|'hash_mismatch'|'node_missing'|... escrito por el renderer
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ON patches (node_id, node_revision);  -- 1 patch vigente por nodo
```

- **Una fila por nodo**, con `changes[]` dentro: el review granular acepta/rechaza *changes* y el sistema recompone `corrected_text` desde `edit_ops` filtrados — review parcial real, no ilusorio.
- `applied_at`/`apply_result` los escribe **el renderer tras verificar** (round-trip: releer el párrafo y comparar). Se acaba el "applied=True" optimista.
- MinIO deja de almacenar patches: solo artefactos binarios (DOCX, PDF, PNG).

### 2.2.3 Otras tablas

- `node_classifications` (histórico de clasificación con fuente y confianza) si se quiere auditar el clasificador; si no, `role` en el nodo basta.
- `term_decisions (doc_id, surface, normalized, decision, decided_by)`: memoria de **decisiones** terminológicas que se inyecta a prompts (§2.6.4), reemplaza el volcado de n-gramas.
- `pipeline_runs (doc_id, run_id, stage, status, checkpoint_json, cost_usd)`: checkpoints por etapa para resumibilidad e idempotencia.
- Eliminar: `element_groups` (subsumida por el árbol), `paragraph_locations` (subsumida por `page_start/page_end` del nodo), `correction_batches` (reemplazada por `pipeline_runs`).

## 2.3 Orquestación de sub-pipelines

```
                    ┌────────────────────────────────────────────────┐
                    │ A. INGESTA  (docx inmutable + hash → MinIO)    │
                    └───────────────┬────────────────────────────────┘
                                    ▼
                    ┌────────────────────────────────────────────────┐
                    │ B. PARSE ESTRUCTURAL ÚNICO (lxml sobre OXML)   │
                    │  body+tablas anidadas+textboxes+footnotes+h/f  │
                    │  → document_nodes (árbol completo, anclado)    │
                    └───────────────┬────────────────────────────────┘
                                    ▼
        ┌──────────────────────────┼──────────────────────────────┐
        ▼                          ▼                              ▼
┌───────────────┐        ┌─────────────────┐            ┌─────────────────┐
│ B2. PROYECCIÓN│        │ C. ANÁLISIS      │            │ C2. CLASIFICACIÓN│
│ PDF (LibreOff)│        │ secciones/perfil │            │ role por nodo    │
│ alineación    │        │ global (C.6)     │            │ (reglas+LLM batch)│
│ texto↔página  │        └────────┬─────────┘            └────────┬────────┘
│ → page_start  │                 └──────────────┬────────────────┘
└───────┬───────┘                                ▼
        │                ┌────────────────────────────────────────────────┐
        └───────────────▶│ D. PLANNER DE CORRECCIÓN (un solo router)      │
                         │ asigna cada nodo a UN work-item:               │
                         │   skip | lt_only | para_cheap | para_editorial │
                         │   | list_group(subárbol) | table_group(subárbol)│
                         │   | protected                                  │
                         │ work-items → cola Celery (paralelo por diseño) │
                         └───────────────┬────────────────────────────────┘
                                         ▼
              ┌────────────── workers por tipo de work-item ──────────────┐
              │ LT pass (stateless, paralelo total)                       │
              │ LLM párrafo (contexto = resumen sección + decisiones)     │
              │ LLM grupo lista (subárbol, node_id por ítem)              │
              │ LLM grupo tabla (subárbol, dirección por node_id)         │
              │ Auditoría P2 (solo work-items con riesgo)                 │
              └───────────────┬───────────────────────────────────────────┘
                              ▼
                  ┌────────────────────────────┐
                  │ GATES + persistencia patch │  (1 fila/nodo, transaccional)
                  └─────────────┬──────────────┘
                                ▼
                  ┌────────────────────────────┐
                  │ E. RENDER (diff por runs)  │ → verificación → applied
                  └────────────────────────────┘
```

Reglas de orquestación:

1. **Un único planner**: la dicotomía secuencial/paralela desaparece. El planner emite work-items independientes; el paralelismo es la forma natural, no una rama aparte. La dependencia secuencial artificial (ventana de contexto de texto corregido) se elimina sustituyéndola por contexto *precomputado* (resumen de sección + decisiones terminológicas + fingerprint global), que no depende del resultado de párrafos anteriores. La coherencia inter-párrafo se garantiza por **contrato** (decisiones registradas) y se verifica por **pasada de consistencia** final barata (un LLM call por sección sobre la lista de términos/grafías usados), no por serialización.
2. **Los grupos se dirigen por `node_id` en el prompt y en la respuesta** (§2.6.3): el desalineamiento de §1.1.5 se vuelve imposible.
3. Cada work-item es **idempotente y reanudable**: clave `(doc_id, run_id, node_id)`; reintento de Celery re-ejecuta solo work-items sin resultado.
4. Nodos `protected=TRUE` (citas, fórmulas, regiones de usuario) jamás entran a un work-item LLM; LT con reglas mínimas o nada. Hoy esa garantía depende de prompts que pueden ignorarse.

## 2.4 Motor de reconstrucción (Safe-Replace real)

El renderer actual reescribe párrafos; el nuevo aplica **ediciones a nivel de run**:

```
aplicar_patch(nodo, edit_ops):
  1. p = resolver_por_anchor(nodo.oxml_anchor)          # determinista, sin búsqueda
  2. assert xxhash(p.texto_normalizado) == nodo.content_hash
       → si falla: apply_result='hash_mismatch', NO tocar, alertar
  3. construir mapa run_spans = [(run_i, start, end)] del texto vigente
  4. para cada opcode (equal/replace/insert/delete) de edit_ops (orden inverso):
       - localizar runs afectados por [start,end)
       - si la edición cae DENTRO de un run: editar w:t in place
       - si cruza frontera de runs: dividir el texto editado proporcionalmente
         a los spans ORIGINALES de cada run (no proporción global), de modo que
         cada run conserva su rPr y los elementos no-texto (footnoteReference,
         fldChar, drawing) conservan su posición relativa exacta
       - nunca eliminar runs; runs que quedan sin texto conservan sus
         elementos estructurales
  5. releer p.text y verificar == corrected_text esperado
       → apply_result='ok' | revertir part y reportar
```

- Los `edit_ops` se computan al persistir el patch (`SequenceMatcher`/diff-match-patch a nivel palabra), así el renderer no recalcula diffs y el review granular reusa los mismos opcodes.
- Saltos de página manuales (`w:br type="page"`): al estar el `w:br` dentro de un run con posición conocida en `run_spans`, las ediciones lo tratan como un elemento no-texto más — desaparece la repartición proporcional arbitraria.
- Hipervínculos: los runs dentro de `w:hyperlink` participan del mapa de spans; una edición que intersecta el rango del hyperlink se aplica **dentro** del hyperlink (editar el texto del link es legítimo) salvo que el opcode lo elimine completo, caso que se degrada a `manual_review`. Hoy se omite el párrafo entero.
- **Test de invariante obligatorio** (CI): para todo DOCX del corpus, `aplicar_patches(docx, [])` produce bytes OXML idénticos (round-trip de identidad), y `aplicar_patches` con ediciones sintéticas preserva: nº de footnotes, nº de campos, nº de drawings, rPr por posición relativa, numIds. Esto es lo que hoy no existe y permitiría detectar el aplanado de runs en el primer commit.

## 2.5 Paginación y continuidad reales

1. La proyección PDF (LibreOffice) se genera una vez. Se extrae el texto por página con PyMuPDF **y se alinea globalmente** contra la secuencia de nodos con un algoritmo de alineación de secuencias (Needleman-Wunsch sobre tokens normalizados, ventana deslizante; `rapidfuzz` para el scoring). Resultado: `page_start/page_end` reales por nodo, calculados **una vez y para todos**, en lugar de N búsquedas por substring por patch. Los nodos que cruzan página quedan marcados (`page_start < page_end`) — eso es la detección real de "texto dividido entre páginas".
2. Los nodos que cruzan página reciben en su prompt el bloque de continuidad (frase cortada, no alterar la oración que cruza) — hoy ese bloque existe (`has_page_break`) pero solo para saltos manuales.
3. Las anotaciones de preview se generan desde la alineación (nodo → página → quads del rango alineado), no re-buscando texto: el highlight cae siempre en la ocurrencia correcta incluso con texto repetido.
4. Tras el render final se regenera el PDF y se re-alinea (es barato) para que `page_*` del documento corregido sean también reales.

## 2.6 Motor de prompts rediseñado

### 2.6.1 Contrato de salida

- Migrar a **Structured Outputs** (`response_format={"type":"json_schema", "json_schema":{..., "strict": true}}`): elimina el JSON inválido, los índices string, los campos faltantes y la mitad del código defensivo de parsing (`_safe_json_parse`, coerciones de tipo de `confidence`/`rewrite_ratio`).
- El modelo **no autoreporta métricas**: `rewrite_ratio` se computa server-side; `confidence` se conserva solo como señal blanda etiquetada `confidence_reported`.
- Para párrafos: el modelo devuelve **operaciones ancladas** (`{find, replace, category, explanation}` con `find` literal del texto) además del texto completo; el server valida que cada `find` exista y que aplicar las operaciones reproduzca `corrected_text` — si no, gate crítico. Esto hace los `changes` verificables (hoy son prosa decorativa).

### 2.6.2 Presupuesto y composición

- Presupuesto explícito por bloque (tokens): perfil ≤150, contexto global ≤200, estructura ≤150, contexto local ≤400, términos ≤30 ítems **relevantes al nodo** (filtrados por aparición en el texto del nodo o su sección, no el glosario entero).
- `max_completion_tokens` dimensionado por `len(texto)` del nodo (p.ej. `min(4096, 2.2 × tokens_estimados + 300)`), nunca un 500 fijo.
- Un solo system prompt por *clase de work-item* (párrafo / grupo-lista / grupo-tabla / auditoría): se elimina la mezcla de contratos.

### 2.6.3 Prompts grupales dirigidos por identidad

```json
// respuesta esperada (json_schema strict)
{"items": [
  {"node_id": "a1b2…", "action": "correct", "corrected_text": "…", "changes": [...]}
]}
```

Cada ítem del prompt se etiqueta con su `node_id` corto (8 hex). El parser mapea por `node_id` exacto: celdas vacías, multipárrafo, merges y particiones dejan de poder desalinear nada. Las particiones de tabla replican fila header (y totals si aplica) como contexto de solo-lectura marcado `"readonly": true`.

### 2.6.4 Consistencia inter-párrafo por decisiones, no por ventana

- Cada work-item LLM que normaliza un término/grafía registra la decisión (`term_decisions`). Los prompts posteriores reciben el bloque `DECISIONES YA TOMADAS EN ESTE DOCUMENTO` (compacto, las K relevantes al texto). Es más barato que 15 párrafos truncados y ataca el problema real (consistencia de decisiones), no su sombra (similitud superficial).
- La ventana de texto corregido se conserva solo para `narrativo`/`dialogo` con tamaño 3 (no 15) y solo cuando el planner ejecuta la sección en orden (work-items de una misma sección se procesan en serie *dentro* de la sección, secciones en paralelo entre sí: paralelismo con coherencia local, sin seeds aproximados ni boundary checks).

### 2.6.5 Coherencia router ↔ prompts

- Si un tipo es SKIP para LLM, sus reglas se implementan como **validadores deterministas post-LT** (p.ej. "título no termina en punto" como gate sobre la corrección LT), no como prompt muerto.
- Una sola política de numeración de listas (nativa: sin prefijo; manual: preservar prefijo) definida en un módulo de política y referenciada por *ambos* caminos (individual y grupal) — la contradicción actual es imposible por construcción porque el camino individual para ítems de lista deja de existir: un ítem de lista siempre se corrige en su grupo (subárbol).

## 2.7 Trazabilidad y revisión

- `patches.edit_ops` + `changes` verificados habilitan UI de review por *cambio* con recomposición server-side del texto final según lo aceptado.
- `llm_audit_log` se mantiene (es de lo mejor del sistema actual) añadiendo `node_id` y `work_item_id`.
- Toda omisión deja de ser un `logger.warning`: se persiste (`apply_result`, `skip_reason` en work-items) y se expone en `/documents/{id}/corrections` — el editor ve también lo que el sistema **no** pudo hacer, que hoy es invisible.

---

# 3. Plan de Acción Hiperdetallado

Principios: (a) primero la red de seguridad (tests de invariantes), (b) después la identidad (nodos anclados), (c) después render no destructivo, (d) después orquestación y prompts. Cada fase deja el sistema funcionando. Estimaciones en jornadas-persona efectivas.

## Fase 0 — Red de seguridad y triaje de bugs activos (3-5 días)

> Sin tocar arquitectura. Detener la pérdida de datos en curso.

1. **Corpus dorado** (`tests/corpus/`): 12-15 DOCX reales que cubran: runs mixtos (negrita parcial), footnotes, hipervínculos, listas nativas/manuales/interrumpidas, tabla con celda vacía, tabla >60 celdas, celdas merged, celda multipárrafo, textbox, salto de página manual, encabezados repetidos, texto duplicado.
2. **Test de invariante de render**: `_apply_docx_patches(docx, [])` → comparar XML canónico de `word/document.xml` antes/después. Hoy pasa; quedará como guardia.
3. **Hotfix H1 — patches grupales** (§1.1.4): persistir `location` y `group_id`/`structural_role` como columnas de `Patch` (migración mínima), poblarlas en `_persist_patches`, y reconstruir los dicts de `_run_candidate_render`/`_run_stage_e` desde BD sin pasar por el JSON de MinIO. Asignar `paragraph_index` sintético único a patches grupales (o deduplicar por `id`, no por `paragraph_index`).
4. **Hotfix H2 — índices de tabla** (§1.1.5): cambiar el contrato del prompt grupal de tabla a índice = posición de enumeración (`[i]` secuencial con `r,c` informativos), y en particiones re-numerar desde 0. Es el fix barato previo al direccionamiento por `node_id`.
5. **Hotfix H3 — paralelo sin grupos** (§1.1.3): en `_dispatch_parallel_correction`, computar `grouped_paragraph_indexes` y pasarlo a los batch tasks; invocar `correct_groups_for_doc_sync` en `assemble_correction_results`. Alternativa más honesta si no se quiere invertir: desactivar `parallel_correction_enabled` hasta Fase 4 y documentarlo.
6. **Hotfix H4 — `applied` veraz**: marcar `applied=True` solo con el resultado real de `_apply_individual_patch` (devolver lista de aplicados desde el renderer).
7. Fix del log `[:0]` ([rendering.py:809](backend/app/services/rendering.py#L809)) y sustitución de `tempfile.mktemp`.
8. **Instrumentación de matching**: contadores persistidos de `no_paragraph`/`mismatch`/`fallback_first_block` por documento. Es el dato que cuantificará la mejora de las fases siguientes.

## Fase 1 — Cimientos de datos (4-6 días)

1. **Alembic** desde el esquema actual (autogenerate baseline). Prohibir cambios de esquema fuera de migraciones. Eliminar `scripts/migrate_b5.py` del flujo.
2. Crear `document_nodes`, `patches_v2`, `term_decisions`, `pipeline_runs` (DDL de §2.2) coexistiendo con las tablas viejas.
3. FK real para `element_group_id` mientras viva (con `ON DELETE SET NULL`).
4. Utilidades: `order_key` fraccional (implementación propia ~80 líneas o port de LexoRank), `xxhash` (`pip install xxhash`) para `content_hash`.

## Fase 2 — Parser estructural único (B nuevo) (8-12 días)

1. Nuevo servicio `services/document_parser.py` sobre **lxml directo** (no la API de alto nivel de python-docx, que oculta orden e interleaving):
   - Iterar `document.xml` body en **orden real del documento** (`w:p` y `w:tbl` intercalados — `body.iterchildren()`), capturando `oxml_anchor` posicional en el mismo recorrido.
   - Descender: tablas → filas → celdas (con `gridSpan`/`vMerge` para colspan/rowspan reales; celdas merged = un solo nodo) → párrafos de celda → **tablas anidadas** (recursión).
   - Parts adicionales: `footnotes.xml`, `endnotes.xml`, headers/footers por sección, `w:txbxContent` (textboxes), SDT (`w:sdtContent` transparente).
   - Por párrafo: `runs_json` (texto + hash de `rPr` + flags + elementos especiales con posición), `numPr` resuelto contra `numbering.xml` (reusar `_resolve_numfmt_from_numbering`, que está bien).
   - Construcción de contenedores: nodos `list` agrupando `list_item` consecutivos **en orden de documento** (corrige §1.2.6); detección manual portada desde `extraction_docx.py` con sus heurísticas anti-falso-positivo (son razonables) pero operando sobre la secuencia ordenada real.
2. Poblar `document_nodes` en B; mantener B.5 escribiendo en `blocks` en paralelo (shadow mode) durante una versión.
3. **Tests**: por cada DOCX del corpus, snapshot del árbol (tipo, order, attrs) y propiedad: concatenación de textos de nodos hoja == texto extraído por python-docx + footnotes + textboxes.
4. **Clasificación (C2)**: `role` por nodo. Reglas deterministas primero (estilo Heading → heading; celda → cell; numPr → list_item); LLM **en batch por lotes de 40 previews** solo para hojas ambiguas (narrativo/dialogo/cita/explicacion_tecnica), con `role_confidence`. Medir contra un gold-set etiquetado a mano (≥300 nodos) antes de dejar que gobierne rutas de gasto.

## Fase 3 — Proyección PDF y paginación real (5-8 días)

1. `services/page_alignment.py`: extracción de texto por página (PyMuPDF, ya existe) + **alineación global tokens-página ↔ tokens-nodos**. Librerías: `rapidfuzz` (scoring C++), alineación banda-diagonal propia (los textos son casi idénticos; es alineación de secuencias casi triviales, no NW completo). Salida: `page_start/page_end` por nodo + offsets de carácter del cruce de página.
2. Reemplazar las tres estimaciones lineales (§1.2.1) por lookups a `document_nodes.page_*`. Borrar `paragraph_locations`.
3. Anotaciones de preview generadas desde la alineación: por nodo corregido, quads del rango de página alineado; diff de palabras (reusar `_compute_changed_phrases_in_corrected`) restringido a ese rango, no a todo el PDF.
4. Test: en el corpus, ≥98% de nodos con página asignada y verificación manual de los que cruzan página.

## Fase 4 — Planner y workers (el fin de la bifurcación) (8-12 días)

1. `services/correction_planner.py`: consulta `document_nodes`, aplica el router (portar `route_paragraph`, mejorándolo con: densidad de errores LT/100 palabras, `role_confidence` baja → editorial, longitud) y emite `work_items` a `pipeline_runs.checkpoint_json` + cola Celery. Listas/tablas → un work-item por subárbol (particionado por presupuesto de tokens, no por "60 celdas").
2. Workers: `lt_worker` (paralelo puro, reusar pool httpx existente), `paragraph_worker`, `group_worker`, `audit_worker`. Cada uno: idempotente por `(run_id, node_id)`, persiste patch v2 transaccionalmente, registra `term_decisions`.
3. Scheduling con coherencia local: work-items de párrafo de una misma sección encadenados (Celery `chain`), secciones en `group`. Eliminar: seeds, `context_seed_window`, `check_batch_boundaries`, `correction_batches`, la rama `parallel_correction_enabled` y la secuencial vieja (queda **un** camino).
4. Checkpoints: si el run muere, `process_document_pipeline` re-emite solo work-items sin resultado. Retries de Celery dejan de re-pagar el documento.
5. Presupuesto/kill-switch por documento: tope de `cost_usd` por run en `pipeline_runs`, abortable.

## Fase 5 — Motor de prompts v2 (6-9 días)

1. **Structured Outputs** en `openai_client` (`json_schema` strict por clase de work-item; pydantic → schema). Eliminar parsing defensivo. Mantener `llm_audit_log`.
2. System prompts separados: `PARAGRAPH_SYSTEM`, `GROUP_LIST_SYSTEM`, `GROUP_TABLE_SYSTEM`, `AUDIT_SYSTEM`. Quitar del prompt de párrafo toda mención al modo grupal.
3. User prompt de párrafo: pasar **de verdad** `block_meta` (attrs del nodo) y `page` (ya reales); presupuesto por bloque (§2.6.2); términos protegidos filtrados por relevancia al nodo; bloque `DECISIONES YA TOMADAS`.
4. Prompts grupales dirigidos por `node_id` (§2.6.3); particiones con header/totals readonly.
5. `changes` como operaciones ancladas verificadas server-side; `rewrite_ratio` computado; gate de coherencia ops↔texto.
6. Política única de prefijos de lista en `services/list_policy.py` consumida por prompts, gates y renderer.
7. Validadores deterministas para tipos SKIP (título sin punto final, caption con etiqueta intacta) aplicados al resultado de LT.

## Fase 6 — Renderer v2 (Safe-Replace) (8-12 días)

1. `services/renderer_v2.py` según §2.4: resolución por `oxml_anchor`, verificación por `content_hash`, aplicación de `edit_ops` sobre el mapa de run-spans, verificación post-aplicación, `apply_result` persistido.
2. Casos especiales con tests dedicados del corpus: footnoteReference en medio de edición, hyperlink editado, `w:br` page manual, run vacío con drawing, celda merged.
3. Suite de invariantes (§2.4 último punto) en CI obligatoria.
4. Conversión a PDF y previews sin cambios (LibreOffice), pero anotaciones desde la alineación (Fase 3).
5. Decomisar `_apply_text_to_paragraph_runs`, `_apply_text_with_page_break`, `_find_best_block`, `_guess_location_for_block`, blocks sintéticos y `patches_docx.json`.

## Fase 7 — Limpieza, observabilidad y endurecimiento (4-6 días)

1. Borrar tablas/columnas muertas (migración destructiva tras 2 versiones de convivencia): columnas estructurales de `blocks`, `element_groups`, `correction_batches`, `paragraph_locations`, `patches` v1.
2. Métricas por documento expuestas en API: % nodos corregidos, % `apply_result != ok`, costo por etapa, precisión del clasificador (muestreo), latencia por work-item. Alertar si `hash_mismatch > 0` (no debería ocurrir nunca con DOCX inmutable).
3. Máquina de estados única y validada (enum + transiciones permitidas) compartida backend/frontend.
4. Semáforo de pipelines con claves por-documento y TTL individual (`SET key EX`), no un set global.
5. Documentación: actualizar CLAUDE.md/CLAUDE-LOGIC.md al modelo de nodos (el actual describirá un sistema que ya no existe).

## Riesgos y mitigaciones del plan

| Riesgo | Mitigación |
|---|---|
| Regresión funcional durante convivencia v1/v2 | Shadow mode en Fases 2-3 (escribir ambos modelos, comparar), corpus dorado en CI desde Fase 0 |
| lxml directo más frágil que python-docx | python-docx *es* lxml con azúcar; se reusa su carga de package y se opera sobre `element` — mismo runtime, menos abstracción mentirosa |
| Structured Outputs no disponible en algún modelo configurado | fallback automático a `json_object` + validación pydantic con reparación de un reintento |
| Costo del refactor vs. roadmap (PDF/OCR fase 3+) | El modelo de nodos es **prerequisito** del soporte PDF/OCR serio: un PDF parseado también produce `document_nodes` (con anchors de página/bbox en vez de OXML). Hacer PDF sobre la arquitectura actual duplicaría todo el fuzzy matching |

## Orden de prioridad si solo se puede hacer una cosa por sprint

1. Fase 0 (hay pérdida de datos activa: H1-H4).
2. Fase 2 + Fase 6 (identidad + render no destructivo): es el 70% del valor — Safe-Replace real.
3. Fase 4 (un solo pipeline, resumible).
4. Fase 5 (prompts v2).
5. Fase 3 (paginación real).
6. Fases 1 y 7 transversales.

---

*Fin del diagnóstico. Cada referencia archivo:línea corresponde al estado del repositorio en el commit `6861ab6`.*
