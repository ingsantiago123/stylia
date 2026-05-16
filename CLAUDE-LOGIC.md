# CLAUDE-LOGIC.md — Lógica, Workflow y Flujo de Datos

Complemento de `CLAUDE.md` enfocado en el **cómo funciona internamente**: flujo de datos, decisiones de diseño, algoritmos paso a paso y detalles de implementación que no encajan en la referencia rápida.

---

## 1. Flujo completo del usuario

```
USUARIO                     FRONTEND                         BACKEND                          SERVICIOS
  │                            │                                │                                │
  │ 1. Arrastra .docx          │                                │                                │
  │ ───────────────────────→   │ 2. POST /upload                │                                │
  │                            │ ──────────────────────────────→│ 3. Valida + guarda MinIO       │→ MinIO
  │                            │                                │ 4. Crea Document (uploaded)    │→ PostgreSQL
  │                            │ ← {id, status: uploaded}       │                                │
  │ 5. Selecciona perfil       │                                │                                │
  │ ───────────────────────→   │ 6. POST /profile               │                                │
  │                            │ ──────────────────────────────→│ 7. Guarda DocumentProfile      │→ PostgreSQL
  │                            │                                │   (con prompt_blocks optional)  │
  │ 8. Click "Procesar"        │                                │                                │
  │ ───────────────────────→   │ 9. POST /process               │                                │
  │                            │ ──────────────────────────────→│ 10. Lanza Celery task          │→ Redis
  │                            │                                │ 11. Worker: A→B→B.5→C→D→D.5→E │
  │                            │ 12. Polling GET /documents      │                                │
  │                            │ ←──────────────────────────────│ heartbeat cada 4s              │
  │ 13. Ve progreso por etapa  │                                │                                │
  │ ←───────────────────────   │ 14. candidate_ready            │                                │
  │                            │ ←──────────────────────────────│                                │
  │ 15. Abre documento         │                                │                                │
  │ ───────────────────────→   │ GET /documents/{id}            │                                │
  │                            │ GET /corrections               │                                │
  │                            │ GET /analysis                  │                                │
  │                            │ GET /structure                 │                                │
  │ 16. Ve 5 tabs + árbol      │ ←──────────────────────────────│                                │
  │ [Revisión HITL opcional]   │                                │                                │
  │ 17. Finaliza               │ POST /finalize                 │                                │
  │ ───────────────────────→   │ ──────────────────────────────→│ 18. Rerender + completed       │→ MinIO/PostgreSQL
  │ 19. Descarga               │ GET /download/pdf              │                                │
  │ ───────────────────────→   │ ──────────────────────────────→│ 20. Stream MinIO               │→ MinIO
```

---

## 2. Pipeline de procesamiento — etapa por etapa

### ETAPA A: Ingesta (`services/ingestion.py`)

**Entrada**: doc_id, source_key (MinIO), filename
**Salida**: {pdf_uri, total_pages}

```
1. Descargar DOCX de MinIO → bytes en memoria
2. Escribir a archivo temporal
3. soffice --headless --convert-to pdf --outdir {tmpdir} {docx_path} (timeout 300s)
4. Contar páginas: len(fitz.open(pdf_bytes))
5. Subir PDF: pdf/{doc_id}/{stem}.pdf
6. Limpiar temporales
```

DB: `Document.status = converting → extracting`, `Document.pdf_uri`, `Document.total_pages`

---

### ETAPA B: Extracción (`services/extraction.py`)

**Entrada**: doc_id, pdf_uri
**Salida por página**: {layout_uri, text_uri, preview_uri, blocks[]}

```
Por cada página:
1. Descargar PDF de MinIO
2. page.get_text("dict", sort=True)
   → {"blocks": [{type, bbox, lines: [{spans: [{text, font, size, color}]}]}]}
3. Clasificar: type=0 → "text", type=1 → "image"
4. page.get_pixmap(dpi=150) → PNG
5. Subir: layout/{page_no}.json, text/{page_no}.txt, preview/{page_no}.png
6. Crear Block records en DB (uno por bloque PyMuPDF)
```

**Limitación conocida**: PyMuPDF extrae bloques del PDF renderizado, no del DOCX original. Fragmenta párrafos, colapsa celdas de tabla. Por eso B.5 existe: para leer la estructura real del DOCX.

---

### ETAPA B.5: Extracción Estructural DOCX (`services/extraction_docx.py`)

Sub-etapa **no bloqueante** (si falla, D continúa sin conciencia estructural).

**Entrada**: doc_id, docx_uri, DB session
**Salida**: {n_lists, n_tables, n_blocks_updated, n_synthetic_blocks}

#### Paso 1: Abrir DOCX con python-docx

```python
docx_bytes = minio_client.download_file(docx_uri)
doc = DocxDocument(io.BytesIO(docx_bytes))
```

#### Paso 2: Detectar grupos de listas

```
_detect_list_groups(doc):

A. Listas nativas (numPr en XML):
   Para cada párrafo:
     numPr = párrafo.element.find(".//numPr") 
     si existe → numId = numPr.find("numId").val
     Agrupar todos los párrafos con mismo numId
     Si grupo >= 2 ítems → ElementGroup(type='list', docx_native_id=f"numId_{numId}")
     style_name del párrafo determina format_type (Bullet → bullet, List Number → decimal, etc.)

B. Listas manuales (regex sobre texto):
   _is_list_like_text(text):
     Patrón: ^\s*(?:[•\-–*]|\d{1,3}[.)]\s|[a-zA-Z][.)]\s)
     Cuerpo después del prefijo >= 4 chars
     → True si hay match y cuerpo sustancial
   
   _looks_like_numbered_heading(text, style_name):
     Texto corto (< 60 chars) + sin puntuación final + estilo Heading → True
     → excluir: "1. Introducción", "2. Marco teórico"
   
   Scanear doc.paragraphs secuencialmente:
     Si is_list_like AND NOT looks_like_heading AND estilo NOT Heading:
       Acumular en lista temporal
     Si no → cerrar lista acumulada (>= 2 ítems → ElementGroup manual)
   
   Detectar format_type:
     decimal_dot: "1.", "2.", ...
     decimal_paren: "1)", "2)", ...
     bullet: "•", "-", "–", ...
     Si mezcla → "mixed"
```

#### Paso 3: Detectar grupos de tablas

```
_detect_table_groups(doc):

Para cada tabla (con índice i):
  n_rows = len(table.rows), n_cols = max(len(r.cells) for r in rows)
  non_empty = número de celdas con texto
  
  Filtros anti-decorativas:
    Si n_rows==1 AND n_cols==1 → skip (tabla de un solo elemento)
    Si non_empty < 2 → skip (tabla casi vacía)
    Si n_cols==1 AND n_rows <= 3 → skip (lista disfrazada de tabla pequeña)
  
  → ElementGroup(type='table', docx_native_id=f"table_{i}", item_count=non_empty)
  
  Para cada celda:
    row 0 → table_cell_role = "header"
    row last AND texto numérico → table_cell_role = "total"
    resto → table_cell_role = "data"
```

#### Paso 4: Sincronizar con Blocks existentes en DB

```
_guess_location_for_block(text, existing_blocks):

1. Normalizar: strip().lower().replace múltiples espacios
2. Pass 1 — match exacto normalizado
3. Pass 2 — match por prefijo 80 chars
4. Pass 3 — containment (item en block o block en item, > 70% overlap)
→ Retorna block_id si encontrado, else None
```

#### Paso 5: Enriquecer Blocks existentes y crear sintéticos

```
Para cada ítem de cada grupo:
  block = _guess_location_for_block(item_text, db_blocks)
  
  Si block encontrado:
    block.list_id = group.docx_native_id  (o table_id)
    block.list_position = posición_en_grupo
    block.list_total = total_ítems
    block.list_format_type = "decimal_dot" | "bullet" | etc.
    block.style_name = párrafo.style.name
    block.style_level = heading_level (si aplica)
    block.docx_location = location_string (body:N, table:T:R:C:P)
    block.element_group_id = group.id
    block.table_cell_role = "header" | "data" | "total"
  
  Si NO encontrado:
    Crear Block sintético:
      block_type = "docx_synthetic"
      original_text = item_text
      docx_location = location_string
      element_group_id = group.id
      ... (todos los campos de metadata)
```

#### Paso 6: Calcular grouped_locations

Después de B.5, en `tasks_pipeline.py`:

```python
_grouped_locations = {
    block.docx_location
    for block in db.query(Block.docx_location)
        .join(Page).filter(Page.doc_id == doc_id, Block.element_group_id.isnot(None))
    if block.docx_location
}
# Se pasa a correct_docx_sync como grouped_locations=_grouped_locations
```

---

### ETAPA C: Análisis Editorial (`services/analysis.py`)

**Sub-etapas**: C.1 (inferencia perfil) → C.2 (validación perfil) → C.3 (secciones) → C.4 (glosario) → C.5 (clasificación) → C.6 (contexto global)

#### C.5: Clasificación de párrafos por tipo

```python
classify_paragraph(text, location, style_name, is_in_table, glossary_terms, block=None):

# Señal primaria: metadata B.5 del Block (si disponible)
if block:
    if block.style_name contains "heading"/"título" → ("titulo"|"subtitulo", False)
    if block.list_id → ("lista", True)
    if block.table_id:
        role = block.table_cell_role
        "header" → ("celda_tabla_header", True)
        "total"  → ("celda_tabla_total", False)  # no modificar totales
        else     → ("celda_tabla", True)

# Señal secundaria: location string
if location starts "table:" → ("celda_tabla", True)
if location starts "header:" → ("encabezado", False)
if location starts "footer:" → ("pie_pagina", False)

# Señal terciaria: heurísticas sobre el texto
if style_name contains "Heading" → nivel → titulo/subtitulo
if starts LIST_PATTERN → ("lista", True)
if starts DIALOGUE_PATTERN → ("dialogo", True)
if contains FIGURE_PATTERN → ("pie_figura", True)
...
```

**11 tipos**: `titulo`, `subtitulo`, `narrativo`, `explicacion_tecnica`, `dialogo`, `cita`, `lista`, `celda_tabla`, `celda_tabla_header`, `celda_tabla_total`, `pie_figura`, `nota_pie`, `encabezado`, `pie_pagina`, `vacio`

#### Escritura de paragraph_type a blocks

Después de C.5, `tasks_pipeline.py` escribe paragraph_type a la DB:

```python
loc_to_ptype = {pc["location"]: pc["paragraph_type"] for pc in classifications}
blocks = db.query(Block).join(Page).filter(Page.doc_id == doc_id).all()
for blk in blocks:
    ptype = loc_to_ptype.get(blk.docx_location)
    if ptype:
        blk.paragraph_type = ptype
db.flush()
```

Matching: `block.docx_location` (string de B.5) == `pc["location"]` (string del análisis DOCX).

#### C.6: Contexto global (ADN editorial)

```
Muestreo estratificado:
  - 3 párrafos del inicio (body:0, body:1, body:2)
  - 3 párrafos del medio
  - 3 párrafos del final

Llamada LLM → {
  global_summary: resumen editorial
  dominant_voice: primera/tercera persona, impersonal
  dominant_register: formal/semiformal/coloquial/técnico
  key_themes_json: ["tema1", "tema2"]
  protected_globals_json: [{"term": "X", "reason": "Y"}]
  style_fingerprint_json: {puntuacion, estructura_oraciones, ...}
}
→ Guardado en DocumentGlobalContext
→ Términos globales protegidos se agregan al perfil
```

---

### ETAPA D: Corrección Individual (`services/correction.py → correct_docx_sync`)

**Entrada**: docx_uri, profile, analysis_data, global_context, `grouped_locations: set[str]`

```
1. Descargar DOCX → DocxDocument
2. _collect_all_paragraphs(doc):
   - doc.paragraphs → "body:0", "body:1", ...
   - doc.tables[t].rows[r].cells[c].paragraphs[p] → "table:0:1:2:0"
   - doc.sections[s].header/footer → "header:0:0", "footer:0:0"
   Retorna: [(text, location, has_page_break), ...]

3. Para cada (text, location, has_page_break) con len(text) >= 3:

   ⬛ SKIP si location in grouped_locations
     → Este párrafo se procesa en D.5 como parte de un grupo
     → No añadir a corrected_context tampoco (evita contaminar contexto)

   ⬛ Determinar classification = para_classifications.get(idx, {})
     paragraph_type = classification.get("paragraph_type")

   ⬛ Construir context_prev:
     Ventana de 15 párrafos (settings.context_window_size)
     corrected_meta[-15:] → lista de {text, type, location}

   ⬛ Lookahead: tipo del párrafo siguiente

   ⬛ Contexto de tabla (si location starts "table:"):
     table_context_map[f"table:{idx}"] → {headers, similar_cells, ...}

   ⬛ _correct_single_paragraph(idx, text, location, ...):
     → Pasada 1: LanguageTool + ChatGPT (build_user_prompt)
     → Pasada 2: Auditoría contextual (si global_context disponible)
     → Quality gates (ver sección)
     → Retorna patch_data, usage_record, final_text, route_taken

   ⬛ Acumular contexto:
     corrected_context.append(final_text)
     corrected_meta.append({"text": final_text, "type": paragraph_type, "location": location})
```

**Rutas en el router**:
| Ruta | Criterio | Modelo |
|------|---------|--------|
| `skip` | párrafo vacio, muy corto, sin errores, en lista nativa sin LT | ninguno |
| `cheap` | párrafo corto o tipo de baja complejidad (encabezado, pie, nota) | gpt-4o-mini (cheap) |
| `editorial` | párrafo largo, complejo, intervención profunda, sección principal | gpt-4o-mini (editorial) |
| `group_list` | ítems de lista → pasan a D.5 | (no aplica en D) |
| `group_table` | celdas de tabla → pasan a D.5 | (no aplica en D) |

---

### ETAPA D.5: Corrección Grupal (`services/correction.py → correct_groups_for_doc_sync`)

**Entrada**: doc_id, DB session, profile, global_context

```
1. Cargar todos los ElementGroup del documento
2. Por cada grupo:
   
   A. Recolectar ítems del grupo:
      SELECT blocks WHERE element_group_id = group.id ORDER BY list_position / (row_index, col_index)
      Filtrar: block.original_text con len >= 1

   B. Decidir ruta:
      route_group(batch, profile):
        Si group_type == 'list' → GROUP_LIST
        Si group_type == 'table' → GROUP_TABLE
        (puede ser SKIP si intervention_level == "ortografico")

   C. Construir prompt grupal:
      Lista: build_group_user_prompt_list(items, list_metadata, neighbors, profile, global_context)
      Tabla: build_group_user_prompt_table(cells, table_metadata, neighbors, profile, global_context)
      
      neighbors incluye:
        preceding_paragraph: párrafo inmediatamente antes del grupo
        following_paragraph: párrafo inmediatamente después del grupo
        capitalization_majority: "mayúscula" | "minúscula" (analizado sobre los ítems)
        ending_punct_majority: "punto" | "nada" | "coma"
        parallel_structure_hint: "nominal" | "verbal" | "adjetival"

   D. Llamar LLM:
      correct_group_with_llm_sync(items, prompt, profile):
        messages = [SYSTEM_PROMPT, user_prompt]
        response = openai.chat.completions.create(model=model, max_completion_tokens=...)
        
        Parsear JSON robusto:
          data = json.loads(response.content)
          items_list = data.get("items", data) si es lista directa
          Para cada item:
            idx = int(item["index"]) si válido y en rango
            action = item.get("action", "correct")
            corrected_text = item.get("corrected_text", "")

   E. Generar patches:
      Para cada corrección recibida:
        patch = {
          "location": block.docx_location,
          "original_text": block.original_text,
          "corrected_text": corrected_text,
          "route_taken": "group_list" | "group_table",
          "group_id": str(group.id),
          "group_call_index": idx,
          "group_call_id": str(uuid.uuid4()),
          "structural_role": _role_for(block, detection),
          ...
        }
      
      structural_role ejemplos:
        list_item:bullet:manual  → ítem de lista manual con viñeta
        list_item:mixed:native   → ítem de lista nativa con formato mixto
        table_cell:header        → celda de encabezado de tabla
        table_cell:data          → celda de datos de tabla
        table_cell:total         → celda de totales (no se modifica)

   F. Actualizar grupo:
      group.correction_status = "completed" | "partial_failure"
      partial_failure si #patches < #items_esperados
```

---

### ETAPA E: Renderizado (`services/rendering.py`)

**Entrada**: doc_id, docx_uri, all_patches (individuales + grupales)

```
_apply_docx_patches(doc, patches):

1. Separar patches:
   group_patches = [p for p in patches if p.get("group_id")]
   individual_patches = [p for p in patches if not p.get("group_id")]

2. Aplicar grupales primero (ordenados por group_call_index):
   _apply_group_patches(doc, group_patches)
   Para cada patch:
     paragraph = _get_paragraph_by_location(doc, location)
     is_manual = ":manual" in (structural_role or "")
     
     Si is_manual:
       Aplicar corrected_text CON prefijo tal como está
       (No strip del prefijo — el usuario lo escribió a mano)
     Si nativo:
       corrected = _strip_list_prefix(corrected_text)
       Aplicar sin el prefijo (el DOCX lo añade automáticamente)
     
     _apply_individual_patch(paragraph, original, corrected)

3. Aplicar individuales:
   Para cada patch:
     paragraph = _get_paragraph_by_location(doc, location)
     Verificar: paragraph.text.strip() == original_text (o tolerancia de ~90%)
     Si coincide → aplicar
     Si no → skip con warning (texto ya modificado por patch grupal previo o cambio manual)

_apply_individual_patch(paragraph, original, corrected):
  runs = paragraph.runs
  runs[0].text = corrected_text   # todo el texto en primer run
  for run in runs[1:]:
    run.text = ""                  # vaciar resto
  # Preserva formato de runs[0] (font, bold, italic, size, color)
```

---

## 3. Construcción del prompt LLM

### Sistema de bloques

El prompt para cada párrafo se construye en `prompt_builder.py → build_user_prompt()`:

```python
# 1. Determinar qué bloques aplican según el tipo de elemento
applicable = _blocks_for_paragraph_type(paragraph_type)
# Ej: "titulo" → {"global_context", "profile_header", "ubicacion", "structural_rules", "register_constraints"}
# Ej: "lista"  → {"global_context", ..., "context_prev", "idiolect_protections", "protected_regions"}

# 2. Por cada bloque, check combinado: tipo_aplica AND flag_de_usuario
def emit(name: str) -> bool:
    type_ok = name in applicable
    user_flag = prompt_blocks.get(name)  # None = no configurado = usar default
    user_on = True if user_flag is None else bool(user_flag)
    return type_ok and user_on

# 3. Construir partes del prompt
parts = []
if emit("global_context"):   parts.append(build_global_context_block(global_context))
if emit("profile_header"):   parts.append(build_profile_header(profile))
if emit("ubicacion"):        parts.append(build_location_block(location, section, next_type))
if emit("structural_rules"): parts.append(build_structural_rules(paragraph_type))
if emit("context_prev"):     parts.append(build_context_prev(corrected_meta[-15:]))
...
```

### System prompt (cacheable)

`SYSTEM_PROMPT` en `prompt_builder.py` — no tiene variables, se puede cachear por OpenAI:

```
Eres un corrector de estilo profesional en español.

PRINCIPIOS:
- Corrige lo que tiene evidencia de error; preserva lo que está bien.
- La coherencia entre párrafos es tan importante como la corrección individual.
- La redundancia conceptual (repetir una idea con distintas palabras en el mismo fragmento)
  es un defecto a corregir: "llegó tarde pero pudo revisarse" no necesita aclaración añadida.
- Devuelve SIEMPRE JSON válido. Nunca texto libre.
```

### User prompt — estructura por bloques activos

```
[CONTEXTO GLOBAL DEL DOCUMENTO]          ← si emit("global_context")
  register=..., voice=..., themes=...

[PERFIL EDITORIAL]                        ← si emit("profile_header")
  PERFIL: registro=formal | intervención=profunda | audiencia=académica...
  PRIORIDADES: claridad, cohesion, precision_lexica
  PROTEGER TÉRMINOS: "STYLIA", "ChatGPT"

[UBICACIÓN ESTRUCTURAL]                   ← si emit("ubicacion")
  UBICACIÓN: sección=2 (Marco teórico) | página=3/12 | tipo=narrativo
  SIGUIENTE: subtitulo

[REGLAS ESTRUCTURALES]                    ← si emit("structural_rules")
  TIPO: titulo
  REGLAS: No añadir punto final. No alterar mayúsculas del título.

[CONTEXTO PREVIO]                         ← si emit("context_prev")
  CONTEXTO PREVIO (últimos 15 párrafos corregidos):
  [1] [tipo: narrativo] "primer párrafo corregido..."
  [2] [tipo: narrativo] "segundo párrafo corregido..."
  ...

[RESTRICCIONES DE REGISTRO]              ← si emit("register_constraints")
  RESTRICCIONES DE REGISTRO: lenguaje_inclusivo, sin_anglicismos

[IDIOLECTOS PROTEGIDOS]                  ← si emit("idiolect_protections")
  IDIOLECTOS PROTEGIDOS (no corregir aunque parezcan errores):
  - narrador: "pos" (habla del personaje campesino)

[REGIONES PROTEGIDAS]                    ← si emit("protected_regions")
  REGIONES PROTEGIDAS: no tocar código, citas directas entre «»

[PÁRRAFO A CORREGIR]                      ← siempre
══════════════════════════════════════════════════════
Texto a corregir:
"El texto que se va a corregir aquí."

Devuelve JSON:
{"corrected_text": "...", "changes": [...], "confidence": 0.0-1.0, "rewrite_ratio": 0.0-1.0}
══════════════════════════════════════════════════════
```

---

## 4. Contexto acumulado: ventana de 15 párrafos

```
Párrafo 0:  corregido SIN contexto
            corrected_meta = [{text, type, loc}]

Párrafo 1:  corregido con context_prev = [meta_0]
            corrected_meta = [meta_0, meta_1]

Párrafo 14: corregido con context_prev = [meta_0..meta_13]
            corrected_meta = [meta_0..meta_14]

Párrafo 15: context_prev = [meta_1..meta_14]  ← ventana deslizante de 15
Párrafo N:  context_prev = [meta_{N-15}..meta_{N-1}]

Nota: Párrafos en grupos (group_list/group_table) NO se añaden a corrected_meta.
      Esto evita que el texto de ítems de lista contamine el contexto narrativo.
```

Implementado con: `corrected_meta[-settings.context_window_size:]` donde `context_window_size = 15`

El contexto enriquecido incluye tipo de elemento: `[tipo: titulo]`, `[tipo: narrativo]` — permite al LLM saber si el contexto previo era un título o un párrafo narrativo para ajustar el estilo de la corrección.

---

## 5. Quality gates

Cada corrección pasa por `validate_correction()` en `quality_gates.py`:

### Gates originales (Lote 5)

| Gate | Tipo | Criterio | En fallo |
|------|------|---------|----------|
| `not_empty` | CRÍTICO | len(corrected) > 0 | gate_rejected |
| `expansion_ratio` | CRÍTICO | len(corrected) ≤ len(original) * 1.15 | gate_rejected |
| `protected_terms` | CRÍTICO | todos los términos protegidos presentes en corrected | gate_rejected |
| `rewrite_ratio` | no-crítico | distancia_edición_normalizada ≤ max_rewrite_ratio | manual_review |
| `language_preserved` | no-crítico | proporción de chars españoles ≥ 0.8 | manual_review |
| `readability_inflesz` | no-crítico | INFLESZ en rango [target_min, target_max] | manual_review |

### Gates estructurales (Structural Awareness)

| Gate | Aplica a | Criterio | Tipo |
|------|---------|---------|------|
| `title_no_final_period` | `titulo`, `subtitulo` | corrected no termina con `.` | no-crítico |
| `caption_starts_with_label` | `pie_figura` | corrected empieza con "Figura/Fig./Imagen/Tabla N" | CRÍTICO |
| `table_cell_uniform_capitalization` | `celda_tabla` | capitalización consistente con celdas hermanas | no-crítico |
| `list_format_consistent` | grupos de lista | todos los ítems tienen mismo tipo de puntuación final | no-crítico |
| `list_parallel_structure` | grupos de lista | ≥ 75% de ítems inician con el mismo tipo gramatical | no-crítico |

### Decisión de gate

```
gate_results = validate_correction(original, corrected, profile, paragraph_type, sibling_cells)

failed_critical = [g for g in gate_results if not g.passed and g.is_critical]
failed_soft     = [g for g in gate_results if not g.passed and not g.is_critical]

if failed_critical:
    → usar original (corrected descartado)
    → review_status = "gate_rejected"
    → review_reason = descripción del gate fallido

elif failed_soft:
    → usar corrected (se aplica)
    → review_status = "manual_review"
    → review_reason = descripción de los gates no-críticos fallidos

else:
    → usar corrected
    → review_status = None
```

---

## 6. Cómo se editan los documentos (preservación de formato)

### El problema de los runs

Un párrafo en python-docx tiene **runs** (fragmentos con formato individual):
```
Párrafo: "Este texto tiene negrita y normal"
Run 0: "Este texto tiene "  (Times 12pt, normal)
Run 1: "negrita"             (Times 12pt, bold=True)
Run 2: " y normal"           (Times 12pt, normal)
```

### Solución actual

```python
def _apply_text_to_paragraph_runs(paragraph, new_text):
    runs = paragraph.runs
    if not runs:
        return
    runs[0].text = new_text  # todo el texto en primer run
    for run in runs[1:]:
        run.text = ""         # vaciar resto
    # Preserva: font family, size, color, bold, italic del run[0]
    # Pierde: formatos en runs 1..N (negrita parcial, cursiva, etc.)
```

**Limitación aceptable en MVP**: la mayoría de párrafos editoriales tienen formato uniforme. Preservar formato parcial requiere diff character-level (planificado para fases futuras).

### Matching de párrafo por location string

```python
def _get_paragraph_by_location(doc, location):
    if location.startswith("body:"):
        idx = int(location.split(":")[1])
        return doc.paragraphs[idx]
    
    elif location.startswith("table:"):
        _, t, r, c, p = location.split(":")
        return doc.tables[int(t)].rows[int(r)].cells[int(c)].paragraphs[int(p)]
    
    elif location.startswith("header:"):
        _, s, p = location.split(":")
        return doc.sections[int(s)].header.paragraphs[int(p)]
    
    elif location.startswith("footer:"):
        _, s, p = location.split(":")
        return doc.sections[int(s)].footer.paragraphs[int(p)]
```

### Verificación previa a aplicar

```python
actual_text = paragraph.text.strip()
if actual_text != original_text:
    # Puede haber sido modificado por un patch grupal anterior
    logger.warning(f"Texto no coincide, skip: '{actual_text[:50]}' != '{original_text[:50]}'")
    return False, "text_mismatch"
```

---

## 7. Flujo de datos de archivos en MinIO

```
source/{doc_id}/{filename}                    # DOCX original (subido por usuario)
pdf/{doc_id}/{stem}.pdf                        # PDF convertido por LibreOffice
pages/{doc_id}/layout/{page_no}.json           # Bloques PyMuPDF por página
pages/{doc_id}/text/{page_no}.txt              # Texto plano por página
pages/{doc_id}/preview/{page_no}.png           # Preview PNG 150dpi
pages/{doc_id}/preview_candidate/{no}.png      # Preview con marcas de corrección
pages/{doc_id}/annotations_candidate/{no}.json # Posiciones de correcciones en página
pages/{doc_id}/annotations_original/{no}.json  # Posiciones en original
analysis/{doc_id}/classifications.json         # paragraph_classifications de Etapa C
docx/{doc_id}/patches_docx.json               # TODOS los patches (individual + grupal)
docx/{doc_id}/{stem}_corrected.docx           # DOCX corregido candidato
final/{doc_id}/{stem}_corrected.pdf           # PDF corregido candidato
```

---

## 8. Manejo de errores y fallbacks

| Escenario | Comportamiento |
|-----------|---------------|
| OpenAI API sin key | `_simulate_correction()`: reemplazos hardcoded básicos |
| OpenAI `max_tokens` obsoleto | Se usa `max_completion_tokens` en la nueva SDK |
| OpenAI respuesta excede max_expansion | Se descarta, se usa texto post-LT |
| LanguageTool timeout | Retorna texto original sin correcciones LT |
| B.5 falla (exception) | No bloqueante: pipeline continúa sin conciencia estructural |
| D.5 falla (exception) | No bloqueante: solo patches individuales persisten |
| Grupo parcialmente corregido | `correction_status = partial_failure`; ítems faltantes sin patch |
| Texto no coincide al aplicar patch | Skip silencioso con warning (protege integridad del doc) |
| LibreOffice conversión falla | RuntimeError → pipeline falla, retry con backoff exponencial |
| Celery task falla | Retry x3 con backoff (30s, 90s, 270s), luego status=failed |

---

## 9. Interfaz de usuario: componentes clave

### PromptBlocksPanel

9 toggles para activar/desactivar bloques del prompt. Ubicaciones:
1. **ProfileEditor** (antes de procesar): colapsable "Configuración avanzada del prompt"
2. **EditorialProfilePanel** (después de procesar): visible si el doc no está locked

Lógica: `dirty = drafts differ from initial` → habilita "Guardar cambios" → `onSave({prompt_blocks: draft})`

### CorrectionHistory con GroupCard

```
Renderizado de correcciones:
1. Filtrar por categoría/severidad/ruta/tipo
2. Agrupar correcciones consecutivas con mismo group_id → GroupCard
3. GroupCard colapsa los ítems del grupo en una sola card expandible
4. Cada item dentro muestra diff individual
```

`GroupCard` muestra: tipo de grupo (Lista / Tabla), N ítems, structural_role, indicador "grupal"

### StructuralTree

Árbol visual en tab Análisis:
```
Documento
├── Sección 1: Introducción (párrafos 0-12)
│   └── 📋 Lista "manual_list_0" — 3 ítems — completed
├── Sección 2: Marco teórico (párrafos 13-45)
│   ├── 📊 Tabla "table_1" 4×3 — 10 celdas — completed
│   └── 📋 Lista "numId_2" — 5 ítems — partial_failure
└── Sección 3: Conclusiones (párrafos 46-72)
    └── 📊 Tabla "table_4" 6×2 — 12 celdas — completed
```

Datos de `GET /documents/{id}/structure`.

---

## 10. Decisiones de diseño clave

| Decisión | Razón |
|----------|-------|
| B.5 no bloqueante | La conciencia estructural mejora la calidad pero no es requisito para corregir. Si B.5 falla, D funciona como antes. |
| Grupos en D.5, no en D | D es secuencial con contexto acumulado. Procesar grupos ahí complejiza el flujo. D.5 es una pasada separada sin dependencia de contexto acumulado. |
| grouped_locations como set de strings | Evita necesidad de pasar session DB a correct_docx_sync. Calculado una vez después de B.5 y reutilizado. |
| Formato manual preservado (no normalizar) | "2)" y "2." son decisiones del autor, no errores. El LLM solo corrige el contenido. |
| context_window = 15 (triplicado de 5) | Más contexto reduce redundancias entre párrafos distantes y mejora la coherencia en documentos largos. El costo marginal por token es bajo en gpt-4o-mini. |
| paragraph_type escrito en blocks DESPUÉS de C | B.5 enriquece blocks con metadata DOCX (list_id, table_id). C clasifica usando esa metadata. Escribir paragraph_type al final de C garantiza que use los datos de B.5. |
| Block sintético (`docx_synthetic`) | PyMuPDF a veces no extrae bloques que sí existen en el DOCX (ej: celdas vacías, tablas complejas). Los sintéticos garantizan que D.5 tenga un block_id para guardar el patch. |
| Patches grupales tienen prioridad en render | El renderizador aplica grupos primero. Si un ítem individual también tiene patch (edge case con duplicados históricos), el grupal gana porque fue generado con más contexto. |
