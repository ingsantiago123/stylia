# Plan: Conciencia estructural por tipo de elemento en STYLIA

## Contexto

STYLIA hoy infiere el `paragraph_type` (11 categorías) en la Etapa C y se lo inyecta al LLM como un **hint textual de una o dos líneas** ([prompt_builder.py:183-198](backend/app/services/prompt_builder.py#L183-L198)). El sistema no entiende la *estructura* del elemento que está corrigiendo: procesa ítems de lista uno por uno sin ver los hermanos, procesa celdas de tabla sin agrupar la tabla, y no almacena en `Block` la información jerárquica del DOCX (`para.style.name`, numId, table_id, row/col_index). El resultado: 87% de aciertos en errores estándar, pero fallos sistemáticos en consistencia entre ítems de lista, en convenciones de título, en uniformidad de celdas y en redundancias semánticas que requieren entender el rol del elemento.

Este plan dota al pipeline de **conciencia estructural completa**: persistir metadatos del DOCX, emitir prompts especializados por tipo, agrupar listas y tablas en una sola llamada al LLM, y validar con gates específicos por rol. Es genérico (no hardcodea casos del documento de prueba) y compatible con lo que ya funciona (ortografía, puntuación, celdas individuales) porque toda la nueva información es aditiva y se aplica en bloques 2.5 y gates extra.

Tres decisiones de alcance validadas con el usuario:
1. Implementar **los tres niveles** (prompts, agrupación, sub-etapa B.5 con modelo nuevo).
2. Listas y tablas se corrigen en **una sola llamada por grupo**, parseando la respuesta para crear N patches con `group_id` común.
3. **Nueva sub-etapa B.5** `extraction_docx` entre B (PDF) y C (análisis), persistiendo metadatos en `Block` y en una tabla nueva `element_groups`.

---

## Hallazgos del diagnóstico (qué está roto y dónde)

| # | Brecha | Evidencia | Impacto |
|---|---|---|---|
| 1 | El `Block` no persiste estructura DOCX: faltan `style_name`, `list_id`, `list_position`, `table_id`, `row_index`, `column_index` | [models/block.py:15-73](backend/app/models/block.py#L15-L73) | Etapa C lee `para.style.name` ([analysis.py:483-524](backend/app/services/analysis.py#L483-L524)) pero lo descarta tras clasificar |
| 2 | Etapa B trabaja solo sobre PDF (PyMuPDF), pierde estilos DOCX | [extraction.py:36-127](backend/app/services/extraction.py#L36-L127) | Detección de tipo depende de heurísticas frágiles |
| 3 | Prompts: el "type hint" son 1-2 líneas genéricas por tipo, sin reglas por rol | [prompt_builder.py:183-198](backend/app/services/prompt_builder.py#L183-L198) | El LLM no recibe "los títulos no llevan punto", "las celdas mantienen capitalización de columna", "los ítems siguen el formato del primero" |
| 4 | Ítems de lista y celdas de tabla se envían **individualmente** al LLM, nunca como unidad | [correction.py:638-704](backend/app/services/correction.py#L638-L704) | El LLM no puede detectar `1./2)/3-` mezclados ni paralelismo gramatical |
| 5 | `validate_correction()` ignora `paragraph_type` por diseño (umbrales globales causaban descartes masivos) | [quality_gates.py:290](backend/app/services/quality_gates.py#L290) | Sin gates por rol (título-sin-punto, celda-uniforme, lista-consistente) |
| 6 | Rendering aplica patches sin diferenciación de tipo | [rendering.py:689-735](backend/app/services/rendering.py#L689-L735) | Si el LLM devuelve "1. Item" para un ítem de lista, duplica viñeta |
| 7 | Frontend tiene `PARA_TYPE_COLORS` pero no lo usa: ni badges ni filtro por tipo | [CorrectionHistory.tsx:49-61](frontend/src/components/CorrectionHistory.tsx#L49-L61) | El revisor humano no puede auditar correcciones por rol |

---

## Diseño técnico

### A. Modelo de datos (Nivel 3)

#### A.1 Campos nuevos en `Block` (todos `nullable=True`, retrocompatible)

Archivo: [backend/app/models/block.py](backend/app/models/block.py)

```python
# === Sub-etapa B.5 extraction_docx — Conciencia estructural ===
style_name:        Mapped[str | None] = mapped_column(String(80), nullable=True)
style_level:       Mapped[int | None] = mapped_column(Integer, nullable=True)

# Listas
list_id:           Mapped[str | None] = mapped_column(String(40), nullable=True)
list_position:     Mapped[int | None] = mapped_column(Integer, nullable=True)
list_total:        Mapped[int | None] = mapped_column(Integer, nullable=True)
list_format_type:  Mapped[str | None] = mapped_column(String(20), nullable=True)
# 'bullet'|'decimal'|'lowerLetter'|'upperLetter'|'lowerRoman'|'upperRoman'|'mixed'
list_level:        Mapped[int | None] = mapped_column(Integer, nullable=True)

# Tablas
table_id:          Mapped[str | None] = mapped_column(String(40), nullable=True)
row_index:         Mapped[int | None] = mapped_column(Integer, nullable=True)
column_index:      Mapped[int | None] = mapped_column(Integer, nullable=True)
row_total:         Mapped[int | None] = mapped_column(Integer, nullable=True)
col_total:         Mapped[int | None] = mapped_column(Integer, nullable=True)
table_cell_role:   Mapped[str | None] = mapped_column(String(15), nullable=True)
# 'header'|'data'|'total'|'caption_row'

element_group_id:  Mapped[UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("element_groups.id", ondelete="SET NULL"), nullable=True
)
```

Índices: `idx_blocks_list`, `idx_blocks_table`, `idx_blocks_group`, `idx_blocks_style`.

#### A.2 Tabla nueva `element_groups`

Archivo nuevo: `backend/app/models/element_group.py`

```python
class ElementGroup(Base):
    __tablename__ = "element_groups"
    id:              UUID, PK
    document_id:     UUID, FK(documents.id, ondelete=CASCADE)
    group_type:      String(10)   # 'list'|'table'
    docx_native_id:  String(40)   # 'numId_3' o 'table_2'
    item_count:      Integer
    metadata_json:   JSONB
    # Lista: {format_type, level, first_item_pos_tag, parallel_structure_hint,
    #         ending_punct_majority, capitalization_majority}
    # Tabla: {num_rows, num_cols, header_row, has_totals_row,
    #         column_data_type_hints: ['number','text','date',...]}
    section_id:        UUID, FK(section_summaries.id, ondelete=SET NULL)
    correction_status: String(15) default='pending'
    # 'pending'|'in_progress'|'completed'|'partial_failure'
    created_at:        DateTime tz
```

#### A.3 Campos nuevos en `Patch`

Archivo: [backend/app/models/patch.py](backend/app/models/patch.py)

```python
group_id:           Mapped[UUID | None] = ForeignKey(element_groups.id, ondelete=SET_NULL)
group_call_index:   Mapped[int | None] = Integer  # 0..N-1 dentro del grupo
group_call_id:      Mapped[str | None] = String(50)  # ID llamada LLM grupal (audit)
structural_role:    Mapped[str | None] = String(30)  # 'list_item:decimal','table_cell:header'
```

#### A.4 Migración

- **MVP**: script idempotente `scripts/migrate_b5.py` con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` y `CREATE TABLE IF NOT EXISTS element_groups (...)`. Compatible con `Base.metadata.create_all` para entornos nuevos.
- **Producción futura**: revisión Alembic `<ts>_b5_structural_awareness.py`.

---

### B. Sub-etapa B.5 `extraction_docx.py` (Nivel 3)

Archivo nuevo: `backend/app/services/extraction_docx.py`

**Función pública:**
```python
def extract_docx_structure_sync(
    doc_id: str, docx_uri: str, session: Session,
    docx_bytes_cached: bytes | None = None,
) -> dict:
    """Lee el DOCX con python-docx y enriquece los Block ya creados por
    Etapa B (PDF) con metadatos estructurales. Crea ElementGroup por
    cada lista y tabla detectada."""
```

**Algoritmo:**
1. Descargar/leer DOCX, abrir con `DocxDocument`.
2. Recolectar todos los párrafos con metadata native (`_collect_all_paragraphs(doc)`), produciendo `{text, location, style_name, numId, ilvl, table_idx, row, col}`.
3. **Detectar grupos de lista**: secuencias consecutivas con el mismo `numId` (`_detect_list_groups`).
4. **Detectar tablas**: `for t_idx, table in enumerate(doc.tables)`, leyendo `table.rows × table.columns` (`_detect_table_groups`).
5. Persistir `ElementGroup` por cada grupo detectado.
6. Recorrer los `Block` ya existentes (matcheados por `location` que ya produce extraction.py) y completar:
   - `style_name`, `style_level` desde `para.style.name`
   - `list_id`, `list_position`, `list_total`, `list_format_type`, `list_level`, `element_group_id`
   - `table_id`, `row_index`, `column_index`, `row_total`, `col_total`, `table_cell_role`, `element_group_id`

**python-docx APIs clave:**
```python
para.style.name                                   # 'Heading 1', 'List Bullet'
ppr = para._element.pPr; numPr = ppr.numPr        # XML directo
numId = int(numPr.numId.val); ilvl = int(numPr.ilvl.val)
# doc.part.numbering_part.element → numFmt: 'decimal'|'lowerLetter'|'bullet'
for t_idx, table in enumerate(doc.tables):
    for r, row in enumerate(table.rows):
        for c, cell in enumerate(row.cells):
            for p_idx, para in enumerate(cell.paragraphs): ...
```

**Detección de `list_format_type`**: usar `numFmt` del XML del numbering part; si no se puede resolver, regex sobre el primer ítem (`^\d+[.)]`→decimal, `^[a-z][.)]`→lowerLetter, `^[ivx]+`→lowerRoman, `^[•·▪‒–—●\-\*]`→bullet). Si los ítems hijos cambian de formato → `mixed`.

**Detección de `table_cell_role`**: primera fila con `bold=True` mayoritario o estilo `Header` → `r=0` es `header`; última fila con "TOTAL"/"Suma" → `total`; resto → `data`.

**Integración en `tasks_pipeline.py`:**
```python
@celery_app.task(name="pipeline.extract_docx")
def extract_docx_structure_task(self, doc_id: str): ...
# Cadena: chain(ingest, extract, extract_docx, analyze, correct, render)
```
Nuevo estado canónico `extracted_docx` entre `extracted` y `analyzed`.

---

### C. Cambios en Etapa C `analysis.py` (Nivel 2 provisional → Nivel 3 definitivo)

Archivo: [backend/app/services/analysis.py](backend/app/services/analysis.py)

`classify_paragraph` ahora acepta `block: Block | None` y usa los datos persistidos por B.5 como **señal primaria**:

```python
def classify_paragraph(text, location, style_name=None, is_in_table=False,
                      glossary_terms=None, block: Block | None = None):
    if block is not None:
        if block.style_name:
            sl = block.style_name.lower()
            if "heading" in sl or "título" in sl:
                return ("titulo" if (block.style_level or 2) == 1 else "subtitulo"), False
            if "quote"   in sl: return "cita", False
            if "caption" in sl: return "pie_imagen", True
            if "footnote" in sl: return "nota_pie", True
        if block.list_id:   return "lista", True
        if block.table_id:
            role = block.table_cell_role
            if role == "header": return "celda_tabla_header", True
            if role == "total":  return "celda_tabla_total",  True
            return "celda_tabla", True
    # FALLBACK: heurísticas actuales sin tocar
    return _classify_heuristic(text, location, style_name, is_in_table, glossary_terms)
```

Añadir nuevo tipo `"nota_pie"` a `_CHEAP_TYPES` (en [complexity_router.py](backend/app/services/complexity_router.py)).

**Variante Nivel 2 (transitoria, sin B.5):** ejecutar una pasada ligera `_enrich_blocks_with_docx()` dentro de `analyze_document_sync` que lea el DOCX y complete los campos `Block` directamente. Se deprecia al activar Nivel 3.

---

### D. Prompts especializados por tipo estructural (Nivel 1)

Archivo: [backend/app/services/prompt_builder.py](backend/app/services/prompt_builder.py)

#### D.1 Modificar `SYSTEM_PROMPT` ([líneas 28-66](backend/app/services/prompt_builder.py#L28-L66))

Insertar **entre CATEGORÍAS y SEVERIDADES** (sin tocar bloques existentes):

```
ADAPTACIÓN POR TIPO ESTRUCTURAL:
Cada párrafo viene con un bloque "CONTEXTO ESTRUCTURAL DEL ELEMENTO" que
indica su rol en el documento (título, subtítulo, ítem de lista, celda de
tabla, cita, pie de figura, nota al pie, diálogo, etc.). DEBES respetar las
"REGLAS PARA ESTE ELEMENTO" listadas en ese bloque por encima de las reglas
generales cuando entren en conflicto, salvo si contradicen REGLAS DE
CORRECCIÓN 1, 2 o 3 (preservación de significado, tono y términos protegidos).

En modo grupal (lista o tabla completa), se enviarán varios ítems en una sola
llamada con el formato indicado al final del bloque estructural. Devuelve UN
objeto JSON con un array "items" donde cada elemento incluya su "index".
```

#### D.2 Nuevo BLOQUE 2.5 — `build_structural_block(block_meta, neighbors)`

Función nueva en `prompt_builder.py`. Se invoca **inmediatamente después del BLOQUE 2** (UBICACIÓN ESTRUCTURAL) en `build_user_prompt`:

```python
def build_structural_block(block: dict, neighbors: dict | None = None) -> str:
    ptype = block.get("paragraph_type")
    builder = _STRUCTURAL_BUILDERS.get(ptype, _build_default)
    return builder(block, neighbors or {})

# En build_user_prompt, tras BLOQUE 2:
struct_block = build_structural_block(block_meta, neighbors)
if struct_block:
    parts.append(struct_block)
```

#### D.3 Plantillas literales por tipo

**TÍTULO**
```
═══ ELEMENTO: TÍTULO (nivel {style_level}) ═══
ESTILO DOCX: {style_name}
POSICIÓN: encabeza la sección "{section_title}" (de {total_sections})
TÍTULOS HERMANOS: {sibling_titles_truncated}

REGLAS PARA ESTE ELEMENTO:
- NO añadir punto final ni dos puntos.
- NO reformular: solo ortografía, tildes y mayúsculas iniciales.
- NO convertir a oración completa si el original es nominal.
- Mantener exactamente la estructura sintáctica (nominal/verbal).
- Si rewrite_ratio > 0.10, usa action="skip".
═══════════════════════════════════════════
```

**SUBTÍTULO** — idéntico al de TÍTULO, añadiendo `BAJO TÍTULO PRINCIPAL: "{parent_title}"` y mismo conjunto de reglas.

**PÁRRAFO NARRATIVO**
```
═══ ELEMENTO: PÁRRAFO NARRATIVO ═══
POSICIÓN EN SECCIÓN: {section_position} (first|middle|last) de {section_total}
LONGITUD: {char_count} car, {word_count} pal, {sentence_count} oraciones
VECINOS: anterior={prev_type}, siguiente={next_type}

REGLAS PARA ESTE ELEMENTO:
- Priorizar fluidez, cohesión y eliminación de redundancias semánticas.
- Si es apertura/cierre de sección, cuidar la transición.
- Mantener la voz del autor.
- Evitar fragmentar oraciones si el doc promedia {avg_sentence_length} pal/oración.
═══════════════════════════════════════════
```

**ÍTEM DE LISTA (modo individual)** — usado si el grupo no se procesa colectivamente:
```
═══ ELEMENTO: ÍTEM DE LISTA ═══
LISTA: {list_id} | FORMATO: {list_format_type} | NIVEL: {list_level}
POSICIÓN: ítem {list_position} de {list_total}
PRIMER ÍTEM (referencia): "{first_item_text_truncated}"
ÚLTIMO ÍTEM (referencia): "{last_item_text_truncated}"
PATRÓN DETECTADO:
  - Inicio mayoritario: {capitalization_majority}
  - Cierre mayoritario: {ending_punct_majority}
  - Estructura: {parallel_structure_hint}

REGLAS PARA ESTE ELEMENTO:
- Preservar el formato detectado (capitalización inicial, puntuación final).
- Mantener paralelismo gramatical con los hermanos.
- NO eliminar la viñeta/numeración: la gestiona el DOCX. Escribe SOLO el texto.
- Brevedad: NO añadir conectores ni transiciones de párrafo.
═══════════════════════════════════════════
```

**LISTA COMPLETA (modo grupo — única llamada al LLM)**
```
═══ ELEMENTO: LISTA COMPLETA (modo grupal) ═══
LISTA: {list_id} | FORMATO: {list_format_type} | NIVEL: {list_level}
N ÍTEMS: {list_total}
PATRÓN DETECTADO:
  - Inicio: {capitalization_majority}
  - Cierre: {ending_punct_majority}
  - Estructura: {parallel_structure_hint}
CONTEXTO PREVIO A LA LISTA: "{preceding_paragraph_truncated}"
CONTEXTO POSTERIOR: "{following_paragraph_truncated}"

REGLAS PARA ESTE ELEMENTO:
- Corrige los ítems UNO A UNO devolviendo un array "items" con "index" 0..N-1.
- Cada ítem se evalúa individualmente, pero las correcciones deben ARMONIZARLOS:
  todos terminan con la misma puntuación, comienzan con el mismo tipo de palabra
  (sustantivo/verbo) y respetan la capitalización mayoritaria.
- Si un ítem rompe el paralelismo, alinéalo a la mayoría (no al revés).
- NO añadas ni elimines ítems; el conteo es inalterable.
- Si un ítem no necesita cambios, inclúyelo con action="skip".

ÍTEMS:
[0] "{item_0_text}"
[1] "{item_1_text}"
...
[{N-1}] "{item_N-1_text}"

FORMATO DE RESPUESTA (grupo):
{
  "items": [
    {"index": 0, "action": "correct"|"skip"|"flag", "corrected_text": "...",
     "changes": [...], "confidence": 0.0-1.0, "rewrite_ratio": 0.0-1.0},
    ...
  ]
}
═══════════════════════════════════════════
```

**CELDA DE TABLA (modo individual)**
```
═══ ELEMENTO: CELDA DE TABLA ═══
TABLA: {table_id} | DIMENSIÓN: {row_total} × {col_total}
POSICIÓN: fila {row_index}, columna {column_index}
ROL: {table_cell_role}  (header|data|total)
ENCABEZADO COLUMNA: "{column_header}"
OTRAS CELDAS COLUMNA (muestra): {sibling_cells_truncated}
TIPO DATO COLUMNA: {column_data_type_hint}

REGLAS PARA ESTE ELEMENTO:
- Concisión extrema. NO añadidos retóricos.
- Preservar uniformidad con la columna: capitalización inicial, puntuación
  final, formato numérico/fecha.
- NO convertir números, fechas, símbolos monetarios ni porcentajes.
- Si es header: nominal, sin punto final.
- Si es totales: NO modificar valores.
═══════════════════════════════════════════
```

**TABLA COMPLETA (modo grupo)** — análoga a LISTA COMPLETA. Headers de columna y `column_data_type_hints` en el bloque. `index = row * col_total + col`. Mismo schema de respuesta.

**CITA TEXTUAL, PIE DE FIGURA, NOTA AL PIE, ENCABEZADO/FOOTER, DIÁLOGO, EXPLICACIÓN TÉCNICA** — bloques en el mismo formato (encabezado `═══`, REGLAS PARA ESTE ELEMENTO), completos en el apéndice del Plan-agent embebido. Reglas clave:

- **Cita**: solo OCR mojibake; default `action="skip"`.
- **Pie de figura**: preservar exactamente "Figura N.", "Tabla N.".
- **Nota al pie**: preservar refs bibliográficas (autor, año, página).
- **Encabezado/Footer**: solo errores ortográficos obvios; `skip` si rewrite_ratio > 0.05.
- **Diálogo**: preservar voz/coloquialismos/regionalismos; corregir solo acotaciones del narrador.
- **Explicación técnica**: precisión > fluidez; no sustituir términos, fórmulas, símbolos.

---

### E. Agrupación de listas y tablas (Nivel 2)

Archivo nuevo: `backend/app/services/group_collector.py`

```python
@dataclass
class ElementGroupBatch:
    group_id: UUID
    group_type: str          # 'list' | 'table'
    blocks: list[Block]      # orden lineal
    metadata: dict           # ElementGroup.metadata_json
    neighbors: dict          # {preceding_paragraph, following_paragraph}

def collect_groups_for_document(session, doc_id) -> list[ElementGroupBatch]:
    """Agrupa Block por element_group_id, en orden."""
```

**Orquestador grupal en `correction.py`:**
```python
def correct_group_with_llm_sync(batch, profile, global_context, llm_client) -> list[Patch]:
    sys_prompt  = build_system_prompt()
    user_prompt = build_group_user_prompt(batch, profile, global_context)
    raw    = llm_client.complete(sys_prompt, user_prompt,
                                  model=settings.openai_editorial_model)
    parsed = _safe_json_parse(raw)
    items  = parsed.get("items", [])
    indexed = {it["index"]: it for it in items if isinstance(it.get("index"), int)}
    missing = [i for i in range(len(batch.blocks)) if i not in indexed]
    call_id = uuid.uuid4().hex[:12]
    patches = []
    for i, blk in enumerate(batch.blocks):
        item = indexed.get(i)
        if item is None or item.get("action") == "skip":
            continue
        corrected   = _strip_list_prefix(item["corrected_text"])  # sanitización
        gate_results = validate_correction_for_group(blk, corrected, item, batch, profile)
        review = "auto_accepted" if all(g.passed for g in gate_results if g.critical) \
                                 else "gate_rejected"
        patches.append(Patch(
            block_id=blk.id, source="llm-group", original_text=blk.original_text,
            corrected_text=corrected, group_id=batch.group_id,
            group_call_index=i, group_call_id=call_id,
            structural_role=_role_for(blk), review_status=review,
            ...
        ))
    # Fallback parcial: ítems faltantes se corrigen individualmente
    for i in missing:
        fb = correct_single_block_sync(batch.blocks[i], profile, global_context, llm_client)
        if fb:
            fb.group_id = batch.group_id; fb.group_call_index = i
            patches.append(fb)
    eg = session.get(ElementGroup, batch.group_id)
    eg.correction_status = "completed" if not missing else "partial_failure"
    return patches
```

**Schema JSON de respuesta grupal:**
```json
{ "items": [
    { "index": 0, "action": "correct", "corrected_text": "...",
      "changes": [{"original_fragment": "...", "corrected_fragment": "...",
                   "category": "claridad", "severity": "importante",
                   "explanation": "..."}],
      "confidence": 0.88, "rewrite_ratio": 0.12 },
    { "index": 1, "action": "skip", "corrected_text": "", "changes": [],
      "confidence": 0.95, "rewrite_ratio": 0.0 }
]}
```

**Manejo de errores del LLM:**
| Error | Detección | Mitigación |
|---|---|---|
| N-1 ítems | `len(items) < N` | Fallback individual a los faltantes |
| `index` duplicado | conteo | Tomar primera ocurrencia + fallback al otro |
| `index` fuera de rango | `>= N or < 0` | Descartar, log |
| JSON truncado | `JSONDecodeError` | Reintentar con `max_tokens × 1.5`; si falla, fallback individual de todo el grupo |
| `corrected_text` con prefijo "1." o "- " | regex de sanitización antes del gate | `_strip_list_prefix` quita prefijos conocidos |

---

### F. Router de complejidad (Nivel 2)

Archivo: [backend/app/services/complexity_router.py](backend/app/services/complexity_router.py)

Añadir rutas:
```python
class CorrectionRoute(Enum):
    SKIP = "skip"; CHEAP = "cheap"; EDITORIAL = "editorial"
    GROUP_LIST = "group_list"; GROUP_TABLE = "group_table"

def route_group(batch: ElementGroupBatch, profile: dict) -> RouteDecision:
    intervention = (profile or {}).get("intervention_level", "moderada")
    if batch.group_type == "list":
        if batch.metadata.get("parallel_structure_hint") == "consistent" \
           and sum(len(b.original_text or "") for b in batch.blocks) < 600 \
           and intervention != "agresiva":
            return RouteDecision(CorrectionRoute.GROUP_LIST, "cheap_group")
        return RouteDecision(CorrectionRoute.GROUP_LIST, "editorial_group")
    if batch.group_type == "table":
        cells = batch.metadata.get("num_rows",1) * batch.metadata.get("num_cols",1)
        if cells > 60:
            return RouteDecision(CorrectionRoute.GROUP_TABLE, "editorial_group_partitioned")
        return RouteDecision(CorrectionRoute.GROUP_TABLE, "editorial_group")
    return RouteDecision(CorrectionRoute.CHEAP, "fallback")
```

**Importante:** en el flujo individual de `correct_batch_with_llm_sync`, **saltar** Block con `element_group_id IS NOT NULL` para evitar doble corrección:
```python
if block.element_group_id is not None:
    continue  # ya se procesará en pasada grupal
```

Tablas grandes (>60 celdas) se particionan en sub-batches con `_partition_table_group(...)`.

---

### G. Quality gates por tipo (Nivel 1 + Nivel 2)

Archivo: [backend/app/services/quality_gates.py](backend/app/services/quality_gates.py)

**Gates individuales (Nivel 1):**

```python
def gate_title_no_final_period(corrected, paragraph_type):
    """Títulos/subtítulos NO terminan en punto. No crítico."""
    if paragraph_type not in ("titulo", "subtitulo"):
        return GateResult(True, "title_no_final_period", 1.0, 1.0, "N/A", critical=False)
    s = corrected.rstrip()
    has_period = s.endswith(".") and not s.endswith("...")
    return GateResult(not has_period, "title_no_final_period",
                      0.0 if has_period else 1.0, 1.0,
                      "Título termina en punto" if has_period else "",
                      critical=False)

def gate_table_cell_uniform_capitalization(corrected, sibling_cells):
    """Verifica capitalización inicial coincide con la mayoría de su columna."""
    if not sibling_cells:
        return GateResult(True, "cell_uniform_capitalization", 1.0, 1.0, "N/A", critical=False)
    def upper(s): return bool(s) and s.lstrip()[:1].isupper()
    majority = sum(1 for s in sibling_cells if upper(s)) >= len(sibling_cells)/2
    ok = upper(corrected) == majority
    return GateResult(ok, "cell_uniform_capitalization",
                      1.0 if ok else 0.0, 1.0,
                      "" if ok else "Capitalización inconsistente con columna",
                      critical=False)

def gate_caption_starts_with_label(original, corrected, paragraph_type):
    """Pie de figura/tabla NO puede perder su etiqueta 'Figura N.' / 'Tabla N.'."""
    if paragraph_type != "pie_imagen":
        return GateResult(True, "caption_starts_with_label", 1.0, 1.0, "N/A", critical=True)
    _LABEL = re.compile(r'^(figura|fig\.?|tabla|cuadro|imagen|gr[áa]fico|mapa)\s+\d+', re.I)
    had = bool(_LABEL.match(original.strip()))
    has = bool(_LABEL.match(corrected.strip()))
    if had and not has:
        return GateResult(False, "caption_starts_with_label", 0.0, 1.0,
                          "Pie perdió etiqueta numerada", critical=True)
    return GateResult(True, "caption_starts_with_label", 1.0, 1.0, "OK", critical=True)
```

**Gates grupales (Nivel 2)** — invocados desde `correct_group_with_llm_sync`:

```python
def gate_list_format_consistent(corrected_items: list[str]) -> list[GateResult]:
    """Todos los ítems deben tener mismo inicio (mayús/minús) y mismo cierre."""
    initials = [s.lstrip()[:1].isupper() for s in corrected_items if s.strip()]
    endings  = [_classify_ending(s) for s in corrected_items if s.strip()]
    return [
        GateResult(len(set(initials)) <= 1, "list_format_consistent_initial", ...),
        GateResult(len(set(endings))  <= 1, "list_format_consistent_ending",  ...),
    ]

_VERB_INF = re.compile(r"^\s*\w+(ar|er|ir)\b", re.I)
def gate_list_parallel_structure(corrected_items: list[str]) -> GateResult:
    """≥75% de los ítems empiezan por mismo tipo gramatical (verbo inf / sustantivo / artículo)."""
    def cls(s):
        w = s.strip().split()[0] if s.strip() else ""
        if _VERB_INF.match(w): return "verb_inf"
        if w.lower() in {"el","la","los","las","un","una","unos","unas"}: return "article"
        return "other"
    classes = [cls(s) for s in corrected_items if s.strip()]
    majority = Counter(classes).most_common(1)[0][1] / len(classes)
    return GateResult(majority >= 0.75, "list_parallel_structure",
                      round(majority,4), 0.75,
                      "" if majority>=0.75 else f"Solo {majority:.0%} mismo tipo",
                      critical=False)
```

**Orquestador** en `validate_correction`:
```python
# Tras los 5 gates universales actuales:
gates.append(gate_title_no_final_period(corrected, paragraph_type))
gates.append(gate_caption_starts_with_label(original, corrected, paragraph_type))
if paragraph_type in ("celda_tabla", "celda_tabla_header", "celda_tabla_total"):
    gates.append(gate_table_cell_uniform_capitalization(
        corrected, kwargs.get("sibling_cells", [])))
```

---

### H. Rendering (Etapa E) — Nivel 2

Archivo: [backend/app/services/rendering.py](backend/app/services/rendering.py)

`_apply_docx_patches` se reescribe para particionar grupos y aplicar primero:

```python
def _apply_docx_patches(docx_path, patches):
    doc = DocxDocument(docx_path)
    grouped = defaultdict(list); individual = []
    for p in patches:
        (grouped[p["group_id"]] if p.get("group_id") else individual).append(p)
    for gid, gpatches in grouped.items():
        gpatches.sort(key=lambda x: x.get("group_call_index", 0))
        _apply_group_patches(doc, gid, gpatches)
    for patch in individual:
        _apply_individual_patch(doc, patch)  # lógica existente intacta
    doc.save(output_path); return output_path

_LIST_PREFIX = re.compile(r'^\s*(?:[•·▪‒–—●\-\*]|\d{1,3}[.)]|[a-zA-Z][.)]|[ivxIVX]+[.)])\s+')
def _strip_list_prefix(text):
    return _LIST_PREFIX.sub("", text, count=1)

def _apply_group_patches(doc, group_id, patches):
    for patch in patches:
        paragraph = _get_paragraph_by_location(doc, patch["location"])
        if paragraph is None: continue
        corrected = _strip_list_prefix(patch["corrected_text"])
        if paragraph.text.strip() != patch["original_text"]:
            continue  # mismatch pre-apply
        _apply_text_to_paragraph_runs(paragraph, corrected)
```

La sanitización de prefijos es defensiva: el prompt grupal pide "escribe SOLO el texto del ítem", pero si el LLM falla no duplicaremos viñetas en el DOCX.

---

### I. Frontend (Nivel 1 + Nivel 3)

#### I.1 `CorrectionHistory.tsx` (Nivel 1)

Archivo: [frontend/src/components/CorrectionHistory.tsx](frontend/src/components/CorrectionHistory.tsx)

- Renderizar **badge `paragraph_type`** en cada fila usando `PARA_TYPE_COLORS` ya definido en [líneas 49-61](frontend/src/components/CorrectionHistory.tsx#L49-L61).
- Añadir filtro `paragraphTypeFilter: string | "all"` análogo a `categoryFilter`, `severityFilter`, `routeFilter`.
- Cuando ≥2 patches consecutivos tienen el mismo `group_id`, **colapsar en card grupal expansible**: encabezado "Lista de 6 ítems" o "Tabla 4×3", contador "5/6 aceptados", acción bulk "Aceptar todos los del grupo", expansión muestra los patches individuales con `group_call_index` visible.

API: serializer de Patch debe incluir `paragraph_type`, `group_id`, `group_call_index` (cambio simple en [backend/app/schemas/patch.py](backend/app/schemas/patch.py)).

#### I.2 Vista de árbol estructural (Nivel 3)

Nuevo componente `StructuralTree.tsx` en pestaña Análisis:
```
Documento
├─ Sección 1: "Introducción"  (12 párrafos)
│  ├─ Lista "Objetivos" (5 ítems, formato decimal)   → link a sus patches
│  └─ Tabla "Resumen" (3×4)                           → link a sus patches
└─ Sección 2: "Metodología"
   ├─ Subsección 2.1
   │  └─ Lista (3 ítems, viñeta)
   └─ Subsección 2.2
```

Nuevo endpoint en [backend/app/api/v1/documents.py](backend/app/api/v1/documents.py):
```python
@router.get("/{doc_id}/structure")
def get_document_structure(doc_id: str, session = Depends(get_session)):
    sections = session.query(SectionSummary).filter_by(document_id=doc_id)\
                      .order_by(SectionSummary.section_index).all()
    groups   = session.query(ElementGroup).filter_by(document_id=doc_id).all()
    return _build_tree(sections, groups)
```

---

## Plan de implementación priorizado

### Nivel 1 — Prompts + gates + UI (3–5 días, sin migración de BD)

| Cambio | Archivo | Función | Esfuerzo |
|---|---|---|---|
| Sección "ADAPTACIÓN POR TIPO ESTRUCTURAL" en SYSTEM_PROMPT | `prompt_builder.py` | `SYSTEM_PROMPT` | 0.5 d |
| 13 builders por tipo + `build_structural_block` | `prompt_builder.py` | nuevas funciones | 1.5 d |
| Inyectar BLOQUE 2.5 en `build_user_prompt` | `prompt_builder.py` | `build_user_prompt` | 0.25 d |
| `gate_title_no_final_period`, `gate_caption_starts_with_label`, `gate_table_cell_uniform_capitalization` | `quality_gates.py` | nuevas + `validate_correction` | 0.75 d |
| Badge `paragraph_type` + filtro en historial | `CorrectionHistory.tsx` | render + filtro | 0.5 d |
| Incluir `paragraph_type`, `group_id` en serializer Patch | `schemas/patch.py` | response schema | 0.25 d |

**Verificación:** snapshot del prompt por tipo (test unitario), tests de gates, E2E manual del filtro UI. Sin tocar el documento de prueba a propósito (todas las soluciones son genéricas).

### Nivel 2 — Agrupación + lectura DOCX provisional (10 días)

| Cambio | Archivo | Esfuerzo |
|---|---|---|
| Campos nullable en `Block` (list_*, table_*, style_*) | `models/block.py` + migración | 0.5 d |
| Campos nullable en `Patch` (group_id sin FK aún, group_call_index, structural_role) | `models/patch.py` + migración | 0.25 d |
| `_enrich_blocks_with_docx` dentro de `analysis.py` (transitorio) | `analysis.py` | 2 d |
| `group_collector.py` | nuevo | 1 d |
| `correct_group_with_llm_sync` con parsing robusto y fallback parcial | `correction.py` | 2 d |
| Prompts LISTA COMPLETA, TABLA COMPLETA | `prompt_builder.py` | 1 d |
| Skip de bloques con `group_id` en flujo paralelo | `correction.py` + `complexity_router.py` | 0.5 d |
| `gate_list_format_consistent`, `gate_list_parallel_structure` | `quality_gates.py` | 0.75 d |
| `_apply_group_patches` + `_strip_list_prefix` | `rendering.py` | 1 d |
| Card grupal expansible en historial | `CorrectionHistory.tsx` | 1 d |

### Nivel 3 — Sub-etapa B.5 + `element_groups` (12 días)

| Cambio | Archivo | Esfuerzo |
|---|---|---|
| Modelo `ElementGroup` + FK reales en Block.element_group_id, Patch.group_id | `models/element_group.py`, migración | 1 d |
| `extraction_docx.py` completo (numbering XML, header detection) | servicio nuevo | 3 d |
| Estado `extracted_docx` + tarea Celery en cadena | `tasks_pipeline.py` | 0.5 d |
| Refactor `classify_paragraph` para usar `block` directamente | `analysis.py` | 1 d |
| `route_group` + partition de tablas grandes | `complexity_router.py` + `correction.py` | 2 d |
| Endpoint `/structure` | `api/v1/documents.py` | 0.75 d |
| `StructuralTree.tsx` en pestaña Análisis | nuevo | 2 d |
| Migración idempotente dev (`scripts/migrate_b5.py` + Alembic) | scripts | 1 d |
| Deprecar `_enrich_blocks_with_docx` provisional | `analysis.py` | 0.5 d |

**Orden recomendado:** Nivel 1 → desplegar y medir → Nivel 2 → desplegar tras staging → Nivel 3 en ventana de mantenimiento.

---

## Archivos críticos a modificar

**Nivel 1:**
- [backend/app/services/prompt_builder.py](backend/app/services/prompt_builder.py) — SYSTEM_PROMPT, builders por tipo, BLOQUE 2.5
- [backend/app/services/quality_gates.py](backend/app/services/quality_gates.py) — 3 gates individuales nuevos
- [backend/app/schemas/patch.py](backend/app/schemas/patch.py) — exponer `paragraph_type`, `group_id`
- [frontend/src/components/CorrectionHistory.tsx](frontend/src/components/CorrectionHistory.tsx) — badge + filtro

**Nivel 2 (suma a Nivel 1):**
- [backend/app/models/block.py](backend/app/models/block.py), [backend/app/models/patch.py](backend/app/models/patch.py) — columnas nuevas
- [backend/app/services/analysis.py](backend/app/services/analysis.py) — enrichment transitorio
- [backend/app/services/correction.py](backend/app/services/correction.py) — orquestador grupal + skip de bloques en grupo
- [backend/app/services/rendering.py](backend/app/services/rendering.py) — `_apply_group_patches`
- [backend/app/services/complexity_router.py](backend/app/services/complexity_router.py) — `route_group`
- `backend/app/services/group_collector.py` — **nuevo**

**Nivel 3 (suma a Nivel 2):**
- `backend/app/models/element_group.py` — **nuevo**
- `backend/app/services/extraction_docx.py` — **nuevo**
- [backend/app/workers/tasks_pipeline.py](backend/app/workers/tasks_pipeline.py) — nueva tarea Celery
- [backend/app/api/v1/documents.py](backend/app/api/v1/documents.py) — endpoint `/structure`
- `frontend/src/components/StructuralTree.tsx` — **nuevo**
- `scripts/migrate_b5.py` — **nuevo**

**NO se modifica:**
- LanguageTool integration, OpenAI client, ingestion.py, contextos previos, gates universales actuales (no_empty, expansion, rewrite, protected_terms, language_preserved), perfiles editoriales existentes.

---

## Verificación

### Métricas cuantitativas pre/post

| Métrica | Cómo medir | Objetivo |
|---|---|---|
| % títulos sin punto final | regex sobre `Patch.corrected_text` con `paragraph_type ∈ {titulo,subtitulo}` | ≥ 98% |
| % listas con formato uniforme | `gate_list_format_consistent_*` pasa | ≥ 90% |
| % celdas con capitalización uniforme | `gate_cell_uniform_capitalization` pasa | ≥ 95% |
| Caption con etiqueta preservada | `gate_caption_starts_with_label` (crítico) | 100% |
| Redundancias detectadas | conteo de `category="redundancia"` / total | +30% vs baseline |
| Coste tokens/documento | Σ `LlmUsage.total_tokens` | ≤ baseline × 1.10 (BLOQUE 2.5 vs reducción por grupal) |
| Llamadas LLM / documento | conteo `LlmUsage` | ↓ 30% en docs con listas/tablas |
| % patches grupales auto_accepted | `Patch.group_id IS NOT NULL & review_status="auto_accepted"` | ≥ 80% |

### Corpus de prueba (5 documentos)

1. **Doc baseline** (5 págs, ya usado) — control de regresión.
2. **Doc académico** — headers numerados, citas, glosario denso, notas al pie.
3. **Doc técnico/manual** — listas anidadas heterogéneas + tablas con totales.
4. **Doc narrativo** — diálogo extenso, sin tablas (verifica que flujo individual no degrada).
5. **Doc empresarial** — tabla grande (>60 celdas) para particionado.

### Protocolo

1. Antes del Nivel 1: ejecutar pipeline actual sobre los 5 docs, snapshot baseline de Patches + métricas + coste.
2. Tras cada nivel: re-ejecutar, comparar:
   - **No-regresión**: las correcciones que hoy pasan, deben seguir pasando.
   - Métricas listadas mejoran o se mantienen.
   - El caso "anterioridad previa" debe seguir siendo capturable tras Nivel 1 (la regla genérica de redundancia no cambia; el bloque NARRATIVO refuerza "eliminación de redundancias semánticas").
3. Test de coste: dump de `LlmUsage` con `model_used`; el aumento por BLOQUE 2.5 debe quedar compensado por la reducción de llamadas grupales en docs con listas/tablas.
4. Validación end-to-end: `docker-compose up --build`, subir cada doc, recorrer las 5 pestañas, descargar DOCX/PDF, abrir en Word/LibreOffice, verificar formato.

---

## Restricciones respetadas

- **Soluciones genéricas**: ningún regex/lista de pleonasmos hardcoded; la detección de tipo de lista usa el XML numbering del DOCX o regex genérico de prefijos universales; los gates verifican propiedades estructurales (mayúscula inicial, cierre de oración, paralelismo) no patrones de error.
- **No degradar lo que funciona**: gates universales actuales se preservan, gates nuevos son aditivos. Patches existentes siguen rindiéndose con la misma lógica si `group_id` es null.
- **Patrones existentes**: los bloques nuevos siguen el formato `═══` ya usado y se inyectan dentro de `build_user_prompt` siguiendo el patrón numerado actual.
- **Eficiencia de tokens**: agrupar listas/tablas reduce llamadas (un solo SYSTEM + UN payload grupal vs N llamadas independientes). El BLOQUE 2.5 añade ~150-300 tokens por llamada, compensado por la reducción global.
- **Compatibilidad**: todos los campos nuevos en `Block` y `Patch` son `nullable`. Documentos viejos sin esos datos siguen procesándose por el camino actual.
