# Plan v3 — Reestructuración Arquitectónica del Pipeline de Corrección Stylia

## Context — Por qué este rediseño

La iteración v2 introdujo cambios que **rompieron el sistema**: gates demasiado estrictos descartaban casi todas las correcciones, falsos positivos en clasificación de captions, y rendering que omitía cualquier párrafo con un hipervínculo. El usuario reporta: *"todo se está enviando por LanguageTool ignorando la IA, se pierde el contexto estructural y se rompe la continuidad entre páginas"*.

El análisis exhaustivo de **todo el código fuente** (modelos BD, schemas, endpoints, frontend completo, extracción PyMuPDF, manejo DOCX, prompt builder, rendering, complexity router) revela 3 deficiencias arquitectónicas estructurales que ningún parche puntual puede resolver:

1. **No existe mapeo `paragraph_index → page_no`**: solo una estimación lineal heurística en `rendering.py:101` que asume distribución uniforme (incorrecta). El modelo `Block` ni siquiera tiene `paragraph_index`.
2. **El LLM opera ciegamente respecto a estructura espacial**: parámetros como `has_page_break` están definidos en la firma pero **nunca se computan ni pasan**.
3. **LanguageTool y LLM se pisan mutuamente**: LT corre primero como text-replacement de bajo nivel; el LLM recibe texto ya modificado sin saber qué cambió. No hay reglas de exclusión para nombres propios, terminología técnica, ni estilo.

**Objetivo**: Reestructurar el pipeline siguiendo principios de un Arquitecto Senior:
- Estado canónico inmutable de la estructura del documento (single source of truth)
- Inyección rica de metadatos espaciales en cada llamada al LLM
- Orquestación dual con reglas explícitas (no implícitas)
- Capa de pruebas que valida cada componente aisladamente
- Backend → Frontend coherente con los nuevos metadatos

---

## Diagnóstico — Estado actual del sistema (auditado)

### Modelos de BD (auditoría completa)
- **Document** — completo, con tracking de progreso/timing/costos
- **Page** — sin `first_paragraph_index` / `last_paragraph_index`
- **Block** — sin `paragraph_index`, sin posición relativa en página (top/middle/bottom), sin flag `is_continuation`
- **Patch** — tiene `paragraph_index` pero no `page_no` directo (requiere joins via Block→Page)
- **SectionSummary** — usa `start_paragraph` / `end_paragraph` (sólidos, no tocar)

### Mapeo paragraph_index ↔ page_no — INEXISTENTE
La estimación actual en `rendering.py:101`:
```python
est_page = min(int(para_idx / total_paragraphs * total_pages), total_pages - 1)
```
asume distribución uniforme. Falla con párrafos largos/cortos mezclados, tablas, encabezados.

### Continuidad cross-page — NO DETECTADA
- python-docx atomiza párrafos: si un párrafo tiene `<w:br w:type="page"/>` interno, sigue siendo UN párrafo
- `correction.py:_collect_all_paragraphs()` no detecta `w:br`
- `prompt_builder.py:175` define `has_page_break` pero `correction.py:318` nunca lo pasa
- El LLM recibe el texto completo sin advertencia → puede reescribir y eliminar el salto

### LanguageTool vs LLM — sin reglas de orquestación
- **Orden actual**: LT primero (text-level), LLM después con texto ya modificado
- **Sin protección de nombres propios**: LT puede "corregir" nombres como "Villanueva" → "Villanueva" (pasa), pero al pasarlo al LLM ya viene normalizado
- **Sin marcado de regiones intocables**: terminología técnica, citas, referencias bibliográficas
- **Sin trazabilidad**: no se sabe qué cambios son de LT vs LLM en el patch final salvo por `source` (string concatenado)

### Frontend
- `CorrectionHistory` muestra `block_no` pero NO `paragraph_type`, NO `page_no`, NO `route_taken` con detalle
- `DiffCompareView` muestra annotations sobre PDF vía coordenadas %, pero el mapping al párrafo es por similitud textual
- No hay vista de "continuidad" — un párrafo cross-page se ve como dos cosas separadas
- No se distingue visualmente texto en tabla vs texto en figura

### Tests — NO EXISTEN
Directorio `backend/tests/` está vacío.

---

## PILAR 1 — Validación y Rediseño del Pipeline de Extracción y Ensamblaje

### 1.1 Single Source of Truth: tabla `paragraph_index_map`

**Nueva tabla BD** `paragraph_locations`:
| Campo | Tipo | Propósito |
|-------|------|-----------|
| `id` | UUID PK | |
| `doc_id` | UUID FK | |
| `paragraph_index` | int | Índice global DOCX (0-based) |
| `location` | str(100) | `body:N`, `table:T:R:C:P`, etc. |
| `page_start` | int | Primera página visible donde aparece (1-based) |
| `page_end` | int | Última página visible donde aparece (igual a page_start si no cruza) |
| `position_in_page` | str(10) | `top` / `middle` / `bottom` (basado en bbox) |
| `is_continuation_from_prev_page` | bool | Si el párrafo empieza en una página y viene de la anterior |
| `has_internal_page_break` | bool | Si contiene `<w:br type="page"/>` interno |
| `paragraph_type` | str(30) | Pre-cómputo del clasificador |
| `block_id` | UUID FK Block, nullable | Bloque PDF correspondiente |

**Cómo se llena**: durante Etapa B (extracción) y C (análisis). Una vez creada, se referencia desde Patch, LlmUsage, y prompt builder.

**Reemplaza la heurística actual** (`int(para_idx / total_paragraphs * total_pages)`).

### 1.2 Detección de continuidad cross-page

**En `extraction.py`** (Etapa B), después de extraer todas las páginas:
- Para cada página `n`, mirar el último bloque y su `bbox_y1`
- Si `bbox_y1 > 0.85 * page_height` → marcar `last_block.touches_bottom = True`
- Para cada página `n+1`, mirar el primer bloque y su `bbox_y0`
- Si `bbox_y0 < 0.15 * page_height` → marcar `first_block.touches_top = True`
- Si ambos: comparar primer trigrama del bloque inferior con últimos trigramas del bloque superior
- Si match parcial → marcar `first_block.is_continuation_from_prev_page = True`

**En `correction.py:_collect_all_paragraphs()`**: detectar saltos internos
```python
def _has_internal_page_break(para) -> bool:
    return bool(para._p.findall('.//' + qn('w:br') + '[@w:type="page"]'))
```

### 1.3 Ensamblaje robusto que preserva saltos de página

**Reescribir `rendering._apply_text_to_paragraph_runs()`**:
1. Si el párrafo NO tiene `w:br type="page"` → comportamiento actual (run-safe simple)
2. Si SÍ tiene salto de página interno:
   - Localizar el run que contiene `w:br type="page"`
   - Dividir `corrected_text` en dos partes según la proporción del split original
   - Aplicar parte 1 al texto antes del `w:br`, parte 2 al texto después
   - Preservar el `w:br` exactamente en su posición
3. Si tiene hipervínculos:
   - Calcular cuáles palabras están en `<w:hyperlink>` (rangos de offset)
   - Hacer `difflib.SequenceMatcher` entre original y corregido
   - Si los segmentos modificados NO solapan con rangos de hyperlink → aplicar normal
   - Si SÍ solapan → `review_status = "manual_review"` con razón clara, no skip silencioso

### 1.4 Reglas de continuidad para el LLM

Cuando un párrafo tenga `is_continuation_from_prev_page=True` o `has_internal_page_break=True`:
- Pasar al prompt: `"Este párrafo cruza un salto de página. NO modifiques la longitud relativa antes/después del corte."`
- Reducir `max_expansion_ratio` a 1.05 SOLO para esos párrafos (no para celdas de tabla en general)

**Archivos a modificar**:
- `backend/app/utils/pdf_utils.py` — añadir cálculo de Y-position relativa
- `backend/app/services/extraction.py` — guardar `paragraph_locations`
- `backend/app/services/correction.py` — detectar `w:br type="page"` y pasar `has_page_break` al prompt
- `backend/app/services/rendering.py` — reescribir aplicación de patches respetando estructura
- `backend/app/models/paragraph_location.py` — nuevo modelo

---

## PILAR 2 — Enriquecimiento del Contexto Estructural y Espacial

### 2.1 Metadatos enviados al LLM en cada llamada

**Reestructurar `prompt_builder.build_user_prompt()`** con bloque estructural explícito:

```
═══ UBICACIÓN ESTRUCTURAL ═══
TIPO: {paragraph_type}                  # narrativo | titulo | celda_tabla | pie_imagen | etc.
SECCIÓN: {section_title} (párrafo X de Y en sección)
PÁGINA: {page_no} de {total_pages} (posición {top|middle|bottom})
{si has_internal_page_break}: ⚠ Este párrafo CRUZA un salto de página
{si is_continuation_from_prev_page}: ⚠ Este párrafo continúa desde página anterior
{si table_context}: TABLA: columna "{header}" de N columnas, fila R
{si is_caption}: PIE DE FIGURA — preservar numeración exacta

═══ CONTEXTO PREVIO (últimos 3 corregidos, con tipos) ═══
[PÁRRAFO N-3, tipo: titulo]      "..."
[PÁRRAFO N-2, tipo: narrativo]   "..." (termina sin punto: posible continuación)
[PÁRRAFO N-1, tipo: celda_tabla] "..."

═══ TEXTO A CORREGIR ═══
{texto post-LanguageTool con marcas de protección}

═══ REGIONES PROTEGIDAS (NO MODIFICAR) ═══
- "Dra. Carmen Villanueva Ríos" (offset 12-38): nombre propio
- "ISBN 978-84..." (offset 102-115): identificador técnico
- "machine learning editorial" (offset 200-225): término del glosario
```

### 2.2 Historial enriquecido de contexto

Reemplazar `corrected_context: list[str]` por `corrected_context: list[ParagraphMeta]`:
```python
@dataclass
class ParagraphMeta:
    paragraph_index: int
    location: str
    paragraph_type: str
    page_no: int
    text: str
    last_correction_categories: list[str]  # ["redundancia", "claridad"] — qué se cambió
    ends_abruptly: bool                     # último char no es .?!:")
    has_protected_terms: bool
```

El LLM ahora ve no solo qué se corrigió antes, sino **qué tipo de cambios se hicieron**. Esto le permite mantener consistencia: si en el párrafo anterior se eliminó la muletilla "en este sentido", evita reintroducirla.

### 2.3 Detección y marcado de regiones protegidas

**Nueva función `_detect_protected_regions(text, profile, term_registry)`**:
- Escanea el texto buscando:
  - Términos en `profile.protected_terms`
  - Términos en `term_registry` con `is_protected=True`
  - Patrones reservados: ISBN, DOI, URLs, citas APA `(Apellido, año)`, fechas formales
  - Nombres propios detectados por NER ligero (regex: secuencias de palabras capitalizadas)
- Retorna lista de `(start_offset, end_offset, reason)` que se inyecta al prompt

### 2.4 Posición espacial granular

`Block` recibe nuevos campos opcionales (no rompe migraciones):
- `position_in_page: str` — `top` (Y0 < 20%), `middle`, `bottom` (Y1 > 80%)
- `is_isolated: bool` — bloque rodeado de espacio en blanco (probable título o caption)
- `font_dominance: float` — tamaño relativo al promedio de la página (>1.3 = posible título)

**Archivos a modificar**:
- `backend/app/services/prompt_builder.py` — reestructurar bloques del prompt
- `backend/app/services/correction.py` — construir `ParagraphMeta` y `protected_regions`
- `backend/app/utils/openai_client.py` — opcional: log del prompt completo en modo DEBUG
- `backend/app/models/block.py` — añadir campos `position_in_page`, `is_isolated`, `font_dominance`

---

## PILAR 3 — Orquestación del Motor Dual (LLM ⟷ LanguageTool)

### 3.1 Reglas estrictas de no-colisión

**Nuevo orquestador `engine_router.py`** que reemplaza el flujo lineal LT→LLM. Reglas:

| Regla | LanguageTool | LLM |
|-------|--------------|-----|
| Ortografía simple (sin contexto) | ✓ aplica | ✗ ignora si LT ya corrigió |
| Gramática básica (concordancia) | ✓ aplica | ✗ ignora si LT ya corrigió |
| Nombres propios | ✗ disabled rule | ✗ regiones protegidas |
| Terminología técnica del glosario | ✗ disabled rule | ✗ regiones protegidas |
| Citas textuales `«...»` o `"..."` | ✗ disabled rule | ✗ regiones protegidas |
| URLs, ISBN, DOI, fechas | ✗ disabled rule | ✗ regiones protegidas |
| Estilo (redundancia, claridad, ritmo) | ✗ no aplica | ✓ aplica |
| Cohesión inter-párrafo | ✗ no aplica | ✓ aplica |
| Reescritura de muletillas | ✗ no aplica | ✓ aplica |

**Implementación**:
1. Antes de llamar a LT, calcular regiones protegidas (Pilar 2.3)
2. Pasar a LT con `disabledRules` extendido (estilo + reglas que afecten regiones protegidas)
3. Después de LT, **conservar el original como `pre_lt_text`** y registrar las correcciones LT
4. Al pasar al LLM, enviar:
   - `original_text` (sin tocar)
   - `lt_corrections` (qué hizo LT y por qué)
   - `protected_regions` (lo que NO debe modificar)
5. Si el LLM decide cambiar algo en una región protegida → quality gate crítico falla

### 3.2 Reglas de momento de actuación

**Etapa D rediseñada**:
```
Para cada párrafo:
  Step 1: Detectar regiones protegidas
  Step 2: LanguageTool (con reglas filtradas) → corrige solo errores claros
  Step 3: Si hay cambios LT en regiones protegidas → REVERTIR esos cambios específicos
  Step 4: Decisión de routing:
          - SKIP   → no llamar LLM (títulos, listas vacías, etc.)
          - CHEAP  → llamar LLM con prompt simple
          - EDITORIAL → llamar LLM con prompt completo
  Step 5: LLM devuelve corrected_text + change_log
  Step 6: Validar que LLM no tocó regiones protegidas
  Step 7: Quality gates (sin gate_structure_markers, sin expansión 1.05 forzada)
  Step 8: Crear patch con audit trail (qué hizo LT, qué hizo LLM, qué se rechazó)
```

### 3.3 Patch con audit trail completo

**Extender modelo `Patch`** con:
- `lt_corrections_json` (JSONB) — lista de correcciones LT aplicadas: `[{offset, original, replacement, rule_id}]`
- `llm_change_log_json` (JSONB) — lista de cambios del LLM con categoría y razón
- `reverted_lt_changes_json` (JSONB) — correcciones LT revertidas por colisión con regiones protegidas
- `protected_regions_snapshot` (JSONB) — qué se protegió en este párrafo

Esto permite al revisor humano ver exactamente la trazabilidad completa.

**Archivos a modificar**:
- `backend/app/services/correction.py` — reordenar pipeline interno
- `backend/app/services/engine_router.py` — NUEVO: lógica de orquestación dual
- `backend/app/services/protected_regions.py` — NUEVO: detección de regiones intocables
- `backend/app/models/patch.py` — añadir 4 columnas de audit
- `backend/app/services/quality_gates.py` — nuevo gate `gate_protected_regions_intact`

---

## PILAR 4 — Impacto Full-Stack (Backend y UI)

### 4.1 Migración de BD

**Generar primera migración Alembic** (hoy las tablas se crean con `Base.metadata.create_all`):
- `paragraph_locations` — nueva tabla
- `blocks.position_in_page`, `blocks.is_isolated`, `blocks.font_dominance` — nuevas columnas
- `patches.lt_corrections_json`, `patches.llm_change_log_json`, `patches.reverted_lt_changes_json`, `patches.protected_regions_snapshot` — nuevas columnas

Pasos: introducir Alembic en el repo (`alembic init alembic`), generar migración inicial con esquema actual + delta nuevo.

### 4.2 Schemas Pydantic actualizados

`PatchListItem` y `PatchDetail` exponen los nuevos campos. Frontend recibe:
```typescript
interface PatchDetail {
  // ...existentes
  paragraph_type: string;          // narrativo | titulo | celda_tabla | etc.
  page_no: number;                  // página visible
  position_in_page: 'top'|'middle'|'bottom';
  is_continuation_from_prev_page: boolean;
  has_internal_page_break: boolean;
  protected_regions: Array<{start: number, end: number, reason: string}>;
  lt_corrections: Array<LTCorrection>;
  llm_change_log: Array<LLMChange>;
  reverted_lt_changes: Array<RevertedChange>;
}
```

### 4.3 Nuevos endpoints

| Endpoint | Propósito |
|----------|-----------|
| `GET /documents/{id}/structural-map` | Devuelve el mapa completo `paragraph_locations` (para visualización) |
| `GET /documents/{id}/cross-page-paragraphs` | Lista solo párrafos que cruzan páginas |
| `GET /health/llm` | Test de conectividad LLM (modelo, latencia, error si lo hay) |
| `GET /health/languagetool` | Test de conectividad LT |

### 4.4 Cambios en el Frontend

**`CorrectionHistory.tsx`**:
- Nueva columna **"Página"** (page_no)
- Badge de **paragraph_type** (color por tipo: titulo=morado, narrativo=azul, celda_tabla=naranja, pie_imagen=verde)
- Badge **"Cruza página"** para párrafos con `has_internal_page_break`
- Filtro adicional: por tipo de párrafo, por página
- En la vista expandida: mostrar `protected_regions` resaltadas en amarillo, `lt_corrections` y `llm_change_log` en columnas separadas

**`DiffCompareView.tsx`**:
- Visualización especial para párrafos cross-page: línea punteada conectando el final de una página con el inicio de la siguiente
- Tooltip enriquecido: muestra "Continúa en página X" o "Viene de página X"

**Nueva pestaña "Estructura"** (componente `DocumentStructureView.tsx`):
- Tree-view del documento: secciones → párrafos → tipo
- Heat-map por página: cuántas correcciones hay, ruta tomada (skip/cheap/editorial), tipo de cambios
- Vista de "regiones protegidas": muestra un párrafo con highlighting de zonas que NO se tocaron

**`PipelineFlow.tsx`**:
- Mostrar sub-etapas dentro de "correcting": Step1 protección, Step2 LT, Step3 LLM, Step4 gates
- Indicador visual de "modo dual" funcionando correctamente

**Archivos a modificar**:
- `frontend/src/components/CorrectionHistory.tsx` — añadir columnas y filtros
- `frontend/src/components/DiffCompareView.tsx` — visualización cross-page
- `frontend/src/components/DocumentStructureView.tsx` — NUEVO
- `frontend/src/lib/api.ts` — nuevos métodos y tipos
- `frontend/src/app/documents/[id]/page.tsx` — integrar nueva pestaña

---

## PILAR 5 — Plan de Pruebas Unitarias e Integración

### 5.1 Estructura de tests

```
backend/tests/
├── unit/
│   ├── test_protected_regions.py     # Detección de nombres, ISBN, citas
│   ├── test_engine_router.py          # Reglas LT/LLM
│   ├── test_complexity_router.py      # Routing por tipo
│   ├── test_prompt_builder.py         # Bloques estructurales del prompt
│   ├── test_quality_gates.py          # Gates individuales
│   ├── test_paragraph_collection.py   # _collect_all_paragraphs incluyendo w:br
│   ├── test_run_safe_rendering.py     # Aplicación de patches preservando estructura
│   └── test_table_context.py          # _build_table_context_map
├── integration/
│   ├── test_extraction_pipeline.py    # PDF → bloques → paragraph_locations
│   ├── test_correction_dual_engine.py # LT + LLM con regiones protegidas
│   ├── test_cross_page_continuity.py  # Párrafo con w:br type=page
│   ├── test_full_pipeline_small_doc.py # E2E con doc de prueba pequeño
│   └── test_recorrection_loop.py      # HITL: edit, recorrect, finalize
├── fixtures/
│   ├── test_doc_clean.docx            # Generado con prompt #1
│   ├── test_doc_with_errors.docx      # Generado con prompt #2
│   ├── errores_introducidos.json      # Lista de errores conocidos
│   └── expected_corrections.json      # Correcciones esperadas
└── conftest.py                         # Fixtures pytest, mock OpenAI/LT
```

### 5.2 Tests específicos por componente

**`test_protected_regions.py`**:
```python
def test_detects_isbn():
    text = "El libro tiene ISBN 978-84-376-0494-7."
    regions = detect_protected_regions(text, profile={}, term_registry=[])
    assert any(r.reason == "isbn" for r in regions)

def test_detects_proper_names():
    text = "La Dra. Carmen Villanueva Ríos presentó."
    regions = detect_protected_regions(text, profile={}, term_registry=[])
    assert any("Villanueva" in r.span for r in regions)

def test_detects_glossary_terms():
    registry = [TermRegistry(term="machine learning editorial", is_protected=True)]
    text = "El machine learning editorial es clave."
    regions = detect_protected_regions(text, profile={}, term_registry=registry)
    assert len(regions) == 1
```

**`test_engine_router.py`**:
```python
def test_lt_corrects_simple_typo():
    result = run_languagetool("Esto es un eror.", protected_regions=[])
    assert result.corrected_text == "Esto es un error."

def test_lt_does_not_touch_protected_region():
    text = "El libro Villanueva tiene un eror."
    protected = [Region(start=9, end=19, reason="proper_name")]
    result = run_languagetool(text, protected_regions=protected)
    assert "Villanueva" in result.corrected_text  # nombre intacto
    assert "error" in result.corrected_text       # typo corregido

def test_llm_receives_lt_audit():
    # mock LLM
    capture = MockLLMCapture()
    correct_paragraph(text, lt_corrections=[...], capture=capture)
    assert "lt_corrections" in capture.last_prompt
```

**`test_cross_page_continuity.py`**:
```python
def test_detects_internal_page_break():
    doc = create_doc_with_internal_page_break()
    paragraphs = _collect_all_paragraphs(doc)
    para_meta = build_paragraph_meta(doc, paragraphs)
    assert any(p.has_internal_page_break for p in para_meta)

def test_prompt_includes_continuity_warning():
    para = ParagraphMeta(has_internal_page_break=True, ...)
    prompt = build_user_prompt(text="...", para_meta=para)
    assert "CRUZA un salto de página" in prompt

def test_rendering_preserves_page_break():
    doc = create_doc_with_internal_page_break()
    apply_corrections(doc, [...])
    saved = save_and_reload(doc)
    assert has_w_br_page_at_position(saved, expected_position)
```

**`test_table_context.py`**:
```python
def test_builds_correct_table_context():
    doc = create_doc_with_3x4_table()
    ctx_map = _build_table_context_map(doc)
    assert "table:0" in ctx_map
    assert ctx_map["table:0"]["num_cols"] == 4
    assert "Región" in ctx_map["table:0"]["header_row"]
```

### 5.3 Tests de integración con mocks

Mock OpenAI usando `responses` library: capturar todos los prompts enviados, verificar que contienen los bloques estructurales correctos.

Mock LanguageTool con respuestas grabadas (cassettes) para offline.

### 5.4 Test E2E con documentos reales

Usar los documentos generados por los prompts ya creados:
- `stylia_test_documento_limpio.docx` — debe pasar sin descartes masivos
- `stylia_test_documento_con_errores.docx` — debe corregir todos los errores listados en `errores_introducidos.json` con tasa ≥ 80%

**Métricas de aceptación**:
- ≥ 80% de errores deliberados detectados y corregidos
- 0 falsos positivos en regiones protegidas (ISBN, nombres propios)
- 100% de párrafos con `w:br type="page"` preservan el salto en el output
- 0% de hipervínculos rotos en el DOCX corregido
- Tiempo total de pipeline ≤ 2x del baseline actual

### 5.5 CI Setup

`.github/workflows/test.yml`:
- `pytest backend/tests/unit/` (rápido, en cada PR)
- `pytest backend/tests/integration/ -m "not e2e"` (en cada PR)
- `pytest backend/tests/integration/ -m e2e` (solo en main, con docker-compose up)

---

## Archivos a Crear y Modificar (Resumen)

### NUEVOS archivos
| Archivo | Propósito |
|---------|-----------|
| `backend/app/models/paragraph_location.py` | Single source of truth para mapping |
| `backend/app/services/engine_router.py` | Orquestador dual LT/LLM |
| `backend/app/services/protected_regions.py` | Detección de regiones intocables |
| `backend/app/services/structural_metadata.py` | Cálculo de page_no, position_in_page por párrafo |
| `backend/alembic/` | Sistema de migraciones (no existía) |
| `backend/tests/unit/*.py` | Tests unitarios (8 archivos) |
| `backend/tests/integration/*.py` | Tests integración (5 archivos) |
| `backend/tests/fixtures/` | DOCX, JSONs de referencia |
| `frontend/src/components/DocumentStructureView.tsx` | Nueva pestaña Estructura |

### MODIFICADOS
| Archivo | Cambios |
|---------|---------|
| `backend/app/services/correction.py` | Pipeline rediseñado con engine_router |
| `backend/app/services/prompt_builder.py` | Bloques estructurales explícitos |
| `backend/app/services/quality_gates.py` | Eliminar gate_structure_markers, eliminar regla 1.05 forzada para tablas, añadir gate_protected_regions_intact, añadir gate_page_break_preserved |
| `backend/app/services/extraction.py` | Calcular paragraph_locations |
| `backend/app/services/analysis.py` | Revertir detección agresiva de captions |
| `backend/app/services/rendering.py` | Aplicación de patches respetando w:br y hyperlinks |
| `backend/app/models/block.py` | +position_in_page, +is_isolated, +font_dominance |
| `backend/app/models/patch.py` | +4 columnas de audit |
| `backend/app/utils/pdf_utils.py` | Calcular Y-position relativa |
| `backend/app/api/v1/documents.py` | +endpoints structural-map, /health/llm, /health/languagetool |
| `backend/app/schemas/patch.py` | Nuevos campos en respuesta |
| `frontend/src/lib/api.ts` | Nuevos tipos y métodos |
| `frontend/src/components/CorrectionHistory.tsx` | Nuevas columnas, filtros, badges |
| `frontend/src/components/DiffCompareView.tsx` | Visualización cross-page |
| `frontend/src/app/documents/[id]/page.tsx` | Pestaña Estructura |

---

## Orden de Implementación (sprints)

### Sprint 1 (Reset + cimientos) — DESBLOQUEAR EL SISTEMA
1. **Revertir gates dañinos** (gate_structure_markers, expansión 1.05 forzada)
2. **Suavizar detección de hipervínculos** en rendering (no skip total)
3. **Revertir detección agresiva de captions**
4. **Verificar que el LLM recibe llamadas** (logging WARNING si falla)

→ Sistema vuelve a un estado "funciona como antes" pero con bugs conocidos del baseline anterior.

### Sprint 2 (Estructura espacial)
1. Modelo `paragraph_locations` + migración Alembic
2. Cálculo durante extracción
3. Detección de `w:br type="page"` en `_collect_all_paragraphs`
4. Pasar `has_page_break` al prompt builder
5. Tests unitarios `test_paragraph_collection.py`, `test_cross_page_continuity.py`

### Sprint 3 (Orquestación dual)
1. `protected_regions.py` con detectores básicos (ISBN, nombres, glosario)
2. `engine_router.py` con reglas explícitas
3. Audit trail en Patch (4 columnas)
4. Tests `test_protected_regions.py`, `test_engine_router.py`

### Sprint 4 (Prompt enriquecido)
1. `prompt_builder.py` con bloques estructurales explícitos
2. `corrected_context: list[ParagraphMeta]` en lugar de strings
3. Tests `test_prompt_builder.py`

### Sprint 5 (Rendering robusto)
1. Reescribir `_apply_text_to_paragraph_runs` para `w:br type=page`
2. Detección quirúrgica de hyperlinks con difflib
3. Tests `test_run_safe_rendering.py`

### Sprint 6 (Backend → Frontend)
1. Schemas Pydantic actualizados
2. Endpoints `/structural-map`, `/health/llm`, `/health/languagetool`
3. Frontend: badges, filtros, columna página
4. Pestaña "Estructura"

### Sprint 7 (E2E + CI)
1. Tests E2E con documentos generados
2. CI workflow GitHub Actions
3. Métricas de aceptación validadas

---

## Verificación End-to-End

1. **Generar documentos de prueba** con los prompts ya entregados
2. **Subir documento con errores**, seleccionar perfil "Académico formal", procesar
3. **Verificar en logs del worker**:
   - Aparecen mensajes `Párrafo N: LLM (cheap|editorial) → X cambios`
   - NO aparece masivamente `gate_rejected` en patches
4. **Verificar en BD**:
   - Tabla `paragraph_locations` poblada con `page_no` correcto
   - Patches con `lt_corrections_json` y `llm_change_log_json` no vacíos
   - Patches en regiones de nombres propios tienen `protected_regions_snapshot` no vacío y NO modifican esos nombres
5. **Verificar en frontend**:
   - Tab "Correcciones": columna Página visible, badges de tipo de párrafo
   - Tab "Estructura": tree-view muestra secciones correctamente
   - Tab "Comparar": párrafos cross-page tienen línea conectora visual
6. **Descargar DOCX corregido y abrir en Word**:
   - Hipervínculos siguen funcionando
   - Saltos de página están en su lugar
   - Tablas no desbordan
   - Nombres propios intactos
   - Errores deliberados corregidos (≥ 80%)
7. **Health checks**:
   - `GET /health/llm` retorna 200 con modelo y latencia
   - `GET /health/languagetool` retorna 200

---

## Riesgos asumidos

- **Migración Alembic** introduce complejidad operacional (necesita coordinación con datos existentes)
- **Tests E2E** requieren OpenAI key activa o cassettes pre-grabadas (decidir en Sprint 7)
- **Frontend pestaña Estructura** es scope ambicioso — puede dejarse para Sprint 8 si Sprint 6 se sobreextiende
- **Detección de nombres propios** sin NER es heurística (mayúsculas) — puede tener falsos positivos en inicio de oración
- **No se aborda OCR** ni texto en imágenes (sigue como deuda técnica explícita)
