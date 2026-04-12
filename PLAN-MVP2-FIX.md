# PLAN-MVP2-FIX: Corrección Integral del Motor Editorial STYLIA

> **Generado**: 2026-04-08  
> **Base**: Auditoría de código real + `correccion de estilos funcionamiento real.md` + `motoreditoria.md`  
> **Principio rector**: Solo se documenta lo que falta. Lo que ya funciona se marca como ✅.

---

## Estado Real del Sistema (Verificado contra código)

### ✅ Lo que SÍ funciona hoy
- Pipeline A→B→C→D→E ejecuta en Celery con etapa C (análisis) activa
- Queue routing separado (pipeline/batch) con `task_acks_late` y prefetch configurable
- Cache Redis de DOCX entre etapas (TTL 2h)
- Detección básica de tablas por ubicación (`table:T:R:C:P`) y `is_in_table` en analysis
- Router de complejidad con 3 rutas (SKIP/CHEAP/EDITORIAL)
- Quality gates: 5 gates + INFLESZ implementado
- Prompt parametrizado con perfil, contexto de sección, términos activos
- Rendering preserva runs (no sobrescribe `paragraph.text`)
- 10 perfiles editoriales predeterminados
- Patches enriquecidos: category, severity, explanation, confidence, route_taken, gate_results

### ❌ Lo que NO funciona o falta (22 brechas críticas)

| # | Brecha | Impacto | Severidad |
|---|--------|---------|-----------|
| 1 | No hay endpoints accept/reject de correcciones | Usuario no puede decidir qué se aplica | P0 |
| 2 | Rendering aplica TODOS los patches sin filtrar por review_status | gate_rejected se aplica igual | P0 |
| 3 | No hay estado PENDING_APPROVAL en documento | No hay pausa para revisión humana | P0 |
| 4 | Tablas se envían al LLM como texto plano sin contexto de celda | LLM expande texto y rompe tablas | P0 |
| 5 | Modelos cheap/editorial son idénticos (ambos gpt-4o-mini) | No hay diferenciación real de calidad | P1 |
| 6 | No hay pasada multi-nivel (léxico → estilo separados) | Todo se corrige en una sola llamada | P1 |
| 7 | Figuras/imágenes/captions completamente ignorados | Texto de captions se corrige sin contexto | P1 |
| 8 | No hay saneamiento de páginas en blanco en PDF | LibreOffice genera páginas vacías | P1 |
| 9 | Protected terms usa substring naive | "plan" matchea en "explanation" | P1 |
| 10 | INFLESZ gate deshabilitado por defecto (sin targets en perfiles) | Nunca valida legibilidad | P1 |
| 11 | No hay track changes en DOCX de salida | No hay capa de sugerencias profesional | P1 |
| 12 | No usa Structured Outputs de OpenAI (solo JSON mode) | Riesgo de schema roto | P2 |
| 13 | No hay suite de tests | Sin validación de regresión | P2 |
| 14 | Formato de runs se pierde parcialmente (primer run hereda todo) | Negritas/itálicas internas destruidas | P2 |
| 15 | No hay ejemplos negativos en prompts | LLM sobre-corrige texto correcto | P2 |
| 16 | Clasificación de párrafos es solo heurística | No distingue tipo semántico real | P2 |
| 17 | No hay pasada de verificación de transiciones | Coherencia entre párrafos no validada | P2 |
| 18 | Ventana de contexto solo envía 1 párrafo anterior (no 3) | Insuficiente para coherencia | P2 |
| 19 | No hay registro de decisiones estilísticas acumulado | Inconsistencia a lo largo del documento | P2 |
| 20 | Section summary truncado a 30 palabras | Pierde contexto crítico | P3 |
| 21 | No hay cross-references (Tabla X, Figura Y) | LLM no sabe qué referencia | P3 |
| 22 | No hay limpieza de MinIO al eliminar documento | Archivos huérfanos | P3 |

---

## Plan de Implementación por Fases

### FASE 1: Human-in-the-Loop (P0) — Control humano real
**Objetivo**: El usuario decide qué correcciones se aplican antes de generar el documento final.

#### 1.1 Nuevo estado de documento: `pending_review`
**Archivo**: `backend/app/models/document.py`

```
Estados actuales: uploaded→converting→extracting→analyzing→correcting→rendering→completed→failed
Nuevo flujo:     uploaded→converting→extracting→analyzing→correcting→pending_review→rendering→completed→failed
```

- Agregar `"pending_review"` al comentario de estados válidos
- En `tasks_pipeline.py`: después de etapa D (corrección), cambiar estado a `pending_review` en lugar de pasar directo a etapa E
- La etapa E (rendering) se ejecuta SOLO cuando el usuario lo solicita vía nuevo endpoint

#### 1.2 Endpoints de revisión de correcciones
**Archivo**: `backend/app/api/v1/documents.py`

Nuevos endpoints:

| Método | Ruta | Función |
|--------|------|---------|
| `PATCH` | `/documents/{id}/corrections/{patch_id}` | Aceptar/rechazar un patch individual |
| `POST` | `/documents/{id}/corrections/bulk-action` | Aceptar/rechazar múltiples patches |
| `POST` | `/documents/{id}/finalize` | Aplicar patches aceptados y lanzar rendering |
| `GET` | `/documents/{id}/corrections?review_status=pending` | Filtrar por estado de revisión |

**Schema de entrada** (`backend/app/schemas/`):
```python
class PatchAction(BaseModel):
    action: Literal["accepted", "rejected"]
    user_note: Optional[str] = None  # Nota del revisor

class BulkPatchAction(BaseModel):
    patch_ids: list[UUID]
    action: Literal["accepted", "rejected"]
    user_note: Optional[str] = None

class FinalizeRequest(BaseModel):
    apply_mode: Literal["accepted_only", "accepted_and_auto"] = "accepted_and_auto"
    # accepted_only: solo patches que el usuario aceptó explícitamente
    # accepted_and_auto: patches aceptados + auto_accepted (que pasaron todos los gates)
```

#### 1.3 Modelo Patch: campos de auditoría
**Archivo**: `backend/app/models/patch.py`

Agregar campos:
```python
reviewed_at = Column(DateTime, nullable=True)          # Cuándo se revisó
reviewer_note = Column(Text, nullable=True)            # Nota del revisor
decision_source = Column(String(20), default="system") # "system" | "human"
```

#### 1.4 Rendering filtrado por review_status
**Archivo**: `backend/app/services/rendering.py`

En `_apply_docx_patches()`: filtrar patches antes de aplicar.

```python
# ANTES (actual): aplica todos
for patch in patches:
    _apply_single_patch(doc, patch)

# DESPUÉS: solo los aprobados
approved_statuses = {"accepted", "auto_accepted"} if apply_mode == "accepted_and_auto" else {"accepted"}
filtered = [p for p in patches if p["review_status"] in approved_statuses]
for patch in filtered:
    _apply_single_patch(doc, patch)
```

#### 1.5 Frontend: acciones de revisión
**Archivos**: `frontend/src/lib/api.ts`, `frontend/src/components/CorrectionHistory.tsx`

- `api.ts`: agregar `patchCorrection()`, `bulkPatchAction()`, `finalizeDocument()`
- `CorrectionHistory.tsx`: botones Aceptar/Rechazar por corrección individual + selección múltiple + botón "Finalizar documento"
- Nuevo componente `ReviewToolbar.tsx`: barra superior con contadores (aceptados/rechazados/pendientes) + acciones bulk

#### 1.6 Pipeline: separar corrección de rendering
**Archivo**: `backend/app/workers/tasks_pipeline.py`

```python
# Etapa D termina así:
document.status = "pending_review"
session.commit()
# NO llamar a etapa E automáticamente
# Etapa E se lanza desde endpoint POST /documents/{id}/finalize
```

Nueva tarea Celery `render_approved_patches`:
```python
@celery_app.task(bind=True, queue="pipeline")
def render_approved_patches(self, doc_id: str, apply_mode: str = "accepted_and_auto"):
    # 1. Cargar patches filtrados por review_status
    # 2. Ejecutar rendering.render_docx_first_sync() con patches filtrados
    # 3. Generar PDF + previews anotados
    # 4. Actualizar estado a completed
```

---

### FASE 2: Contexto Estructural Inteligente (P0/P1) — Tablas, figuras, formato

#### 2.1 Contexto de tabla para el LLM
**Archivos**: `backend/app/services/correction.py`, `backend/app/services/prompt_builder.py`

**Problema**: Cuando el LLM recibe texto de una celda de tabla, no sabe que está en una tabla, ni qué hay en las celdas adyacentes. Resultado: expande texto, destruye layout.

**Solución**: Al recolectar párrafos en `_collect_all_paragraphs()`, extraer contexto de tabla:

```python
# Para cada párrafo con location "table:T:R:C:P":
table_context = {
    "is_table_cell": True,
    "table_index": T,
    "row": R,
    "col": C,
    "total_rows": len(table.rows),
    "total_cols": len(table.columns),
    "row_header": table.rows[0].cells[C].text[:50],  # Header de la columna
    "col_header": table.rows[R].cells[0].text[:50],   # Header de la fila
    "cell_neighbors": {
        "above": table.rows[R-1].cells[C].text[:30] if R > 0 else None,
        "left": table.rows[R].cells[C-1].text[:30] if C > 0 else None,
    }
}
```

**En prompt_builder.py**, agregar bloque condicional:
```
## RESTRICCIÓN DE TABLA
Este texto está en la celda [fila {R}, columna {C}] de una tabla.
- Columna: "{row_header}"
- Fila: "{col_header}"
- PROHIBIDO expandir el texto. Máximo {len(original)} caracteres.
- Solo corregir errores ortográficos evidentes.
- NO añadir conectores, artículos ni explicaciones.
- Si el texto es un dato (número, nombre, código), NO modificar.
```

#### 2.2 Detección y protección de figuras/captions
**Archivos**: `backend/app/services/correction.py`, `backend/app/services/analysis.py`

**Problema**: Captions de figuras ("Figura 3: Distribución de...") se corrigen como párrafos normales.

**Solución en analysis.py** — ampliar `classify_paragraph()`:
```python
# Patrones de caption
CAPTION_PATTERNS = [
    r'^(?:Figura|Fig\.|Tabla|Cuadro|Gráfico|Gráf\.|Imagen|Ilustración|Mapa|Esquema)\s*\d+',
    r'^(?:Fuente|Nota|Elaboración propia)',
]

# En classify_paragraph():
for pattern in CAPTION_PATTERNS:
    if re.match(pattern, text.strip(), re.IGNORECASE):
        return "pie_imagen"  # Ya existe este tipo
```

**Solución en prompt_builder.py** — instrucción específica:
```
## CAPTION DE FIGURA/TABLA
Este texto es un pie de figura o tabla. 
- Solo corregir errores ortográficos.
- NO reformular ni expandir.
- Preservar numeración y formato exacto.
```

#### 2.3 Cross-references contextuales
**Archivo**: `backend/app/services/correction.py`

Al encontrar referencias como "ver Tabla 2", "como muestra la Figura 5":
```python
CROSS_REF_PATTERN = r'(?:ver|véase|como (?:muestra|indica|se (?:observa|aprecia) en))\s+(?:la\s+)?(?:Tabla|Figura|Cuadro|Gráfico)\s+\d+'

# Extraer el texto referenciado del caption correspondiente
# Inyectar en prompt: "El párrafo referencia la Tabla 2 cuyo título es: '{caption_text}'"
```

#### 2.4 Mejora de preservación de formato de runs
**Archivo**: `backend/app/services/rendering.py`

**Problema actual**: `_apply_text_to_paragraph_runs()` pone todo el texto en `runs[0]` y vacía el resto. Esto destruye negritas/itálicas internas.

**Solución**: Algoritmo de mapeo de runs mejorado:

```python
def _apply_text_preserving_runs(paragraph, corrected_text, original_text):
    """
    Estrategia:
    1. Si la corrección solo cambió algunas palabras y la longitud es similar (±10%),
       intentar mapear cambios a runs específicos
    2. Si la reestructuración es profunda, usar run[0] con estilo dominante (actual)
    """
    runs = paragraph.runs
    if not runs:
        return
    
    # Calcular si el cambio es localizado o global
    import difflib
    ratio = difflib.SequenceMatcher(None, original_text, corrected_text).ratio()
    
    if ratio > 0.85 and len(runs) > 1:
        # Cambio localizado: intentar mapear a runs específicos
        _apply_surgical_run_edit(runs, original_text, corrected_text)
    else:
        # Cambio profundo: estilo dominante en run[0] (comportamiento actual)
        _apply_text_to_paragraph_runs(paragraph, corrected_text)
```

`_apply_surgical_run_edit`: usa `difflib.SequenceMatcher.get_opcodes()` para identificar qué runs contienen el texto cambiado y solo modificar esos runs, preservando `rPr` de los demás.

---

### FASE 3: Pipeline Multi-Pasada Real (P1) — Corrección profesional

#### 3.1 Separar pasadas léxica y estilística
**Archivos**: `backend/app/services/correction.py`, `backend/app/services/prompt_builder.py`, `backend/app/config.py`

**Estado actual**: Una sola llamada LLM hace todo (léxico + estilo + coherencia).  
**Objetivo**: Replicar el proceso editorial profesional.

```
Pasada 1: LanguageTool (ya existe) → ortografía, gramática, puntuación
Pasada 2: LLM barato (gpt-4o-mini) → léxico: muletillas, redundancias, repeticiones
Pasada 3: LLM potente (gpt-4o / claude-sonnet) → estilo: coherencia, tono, registro, fluidez
```

**Implementación en correction.py**:

```python
def _correct_single_paragraph_multipass(
    text: str,
    paragraph_info: dict,
    profile: dict,
    context: dict,
    analysis_data: dict,
    route: str,  # SKIP | CHEAP | EDITORIAL
) -> dict:
    """
    SKIP: solo LanguageTool (pasada 1)
    CHEAP: LanguageTool + pasada léxica (pasadas 1-2)
    EDITORIAL: LanguageTool + pasada léxica + pasada estilística (pasadas 1-2-3)
    """
    # Pasada 1: LanguageTool (ya existe)
    text_after_lt = correct_text_with_languagetool(text)
    lt_patches = [...]
    
    if route == "SKIP":
        return {"corrected": text_after_lt, "patches": lt_patches, "passes": 1}
    
    # Pasada 2: Léxico (modelo barato)
    text_after_lexical = _run_lexical_pass(text_after_lt, profile, context)
    lexical_patches = [...]
    
    if route == "CHEAP":
        return {"corrected": text_after_lexical, "patches": lt_patches + lexical_patches, "passes": 2}
    
    # Pasada 3: Estilo (modelo potente) — solo para EDITORIAL
    text_after_style = _run_style_pass(text_after_lexical, profile, context, analysis_data)
    style_patches = [...]
    
    return {"corrected": text_after_style, "patches": lt_patches + lexical_patches + style_patches, "passes": 3}
```

**Prompts separados en prompt_builder.py**:

```python
def build_lexical_system_prompt() -> str:
    """Pasada 2: Solo léxico. Cacheable."""
    return """Eres un corrector léxico de español. Tu ÚNICA tarea es:
    1. Detectar y corregir muletillas ("es decir", "en este sentido", "cabe destacar")
    2. Eliminar redundancias y pleonasmos ("subir arriba", "lapso de tiempo")
    3. Sustituir palabras repetidas por sinónimos adecuados al registro
    4. Eliminar palabras vacías que no aportan significado
    
    NO modificar: estructura de oraciones, tono, registro, puntuación, ortografía.
    NO expandir el texto. El resultado debe tener igual o menor longitud.
    Responde en JSON..."""

def build_style_system_prompt() -> str:
    """Pasada 3: Estilo profundo. Cacheable."""
    return """Eres un corrector de estilo editorial experto en español.
    Referencia: Nueva gramática (RAE), Manual de estilo de Martínez de Sousa.
    
    Tu tarea es mejorar:
    1. Coherencia y cohesión discursiva entre oraciones
    2. Ritmo y fluidez (variar longitud de oraciones, mejorar conectores)
    3. Registro y tono según el perfil del documento
    4. Claridad narrativa sin simplificar el contenido
    
    REGLA FUNDAMENTAL: "Se corrige todo menos el estilo del autor."
    Si la única razón para cambiar una frase es "yo lo escribiría distinto", NO la cambies.
    
    NO corregir: ortografía, gramática, léxico (ya corregidos en pasadas anteriores).
    Responde en JSON..."""
```

#### 3.2 Configurar modelos realmente diferenciados
**Archivos**: `backend/app/config.py`, `.env.example`

```python
# config.py - valores que DEBEN ser distintos
openai_cheap_model: str = "gpt-4o-mini"       # Pasada 2 léxica
openai_editorial_model: str = "gpt-4o"         # Pasada 3 estilística (modelo potente)
# Alternativa: claude-sonnet-4-5-20250514 via Anthropic SDK
```

```env
# .env.example
OPENAI_CHEAP_MODEL=gpt-4o-mini
OPENAI_EDITORIAL_MODEL=gpt-4o
# Para usar Claude en pasada 3:
# ANTHROPIC_API_KEY=sk-ant-...
# EDITORIAL_PROVIDER=anthropic
# EDITORIAL_MODEL=claude-sonnet-4-5-20250514
```

#### 3.3 Ejemplos negativos en prompts
**Archivo**: `backend/app/services/prompt_builder.py`

Agregar sección de ejemplos negativos al system prompt:

```
## EJEMPLOS DE QUÉ NO CORREGIR
- Original: "A pesar de todo, el proyecto salió adelante."
  ✗ Incorrecto: "No obstante, el proyecto salió adelante." (sinónimo innecesario)
  ✓ Correcto: No requiere corrección.

- Original: "El niño corrió y corrió sin parar."
  ✗ Incorrecto: "El niño corrió incesantemente." (destruye ritmo intencional)
  ✓ Correcto: No requiere corrección (repetición intencional en narrativa).

- Original: "—¿Qué querés? —preguntó."
  ✗ Incorrecto: "—¿Qué quieres? —preguntó." (cambio de variante dialectal)
  ✓ Correcto: No requiere corrección (voseo es válido y es voz del personaje).
```

#### 3.4 Registro de decisiones estilísticas acumulado
**Archivo**: `backend/app/services/correction.py`

```python
class StyleDecisionLog:
    """Registro que se acumula durante la corrección de un documento.
    Se inyecta en el prompt para mantener coherencia."""
    
    def __init__(self):
        self.decisions = []  # [{"term": "internet", "decision": "Internet", "paragraph": 5}]
        self.tone_samples = []  # Frases que definen el tono del autor
    
    def add_decision(self, original: str, corrected: str, paragraph_index: int):
        self.decisions.append({...})
    
    def to_prompt_fragment(self, max_decisions: int = 20) -> str:
        """Genera fragmento inyectable en el prompt."""
        if not self.decisions:
            return ""
        lines = ["## Decisiones estilísticas previas (mantener coherencia):"]
        for d in self.decisions[-max_decisions:]:
            lines.append(f"- '{d['term']}' → '{d['decision']}' (párrafo {d['paragraph']})")
        return "\n".join(lines)
```

#### 3.5 Ventana de contexto ampliada
**Archivo**: `backend/app/services/correction.py`

Cambiar de 1 párrafo anterior a 3 (como documenta CLAUDE.md pero el código no implementa):

```python
# ACTUAL en correction.py ~línea 526:
context_window = corrected_context[-3:]  # Ya dice 3 pero...

# VERIFICAR que build_user_prompt recibe los 3, no solo 1
# En prompt_builder.py, el campo previous_context se trunca a 200 chars
# CAMBIAR: enviar los 3 párrafos completos (hasta 500 chars total)
```

#### 3.6 Pasada de verificación de transiciones
**Archivo**: nuevo `backend/app/services/transition_checker.py`

```python
def verify_transitions(corrected_paragraphs: list[dict], profile: dict) -> list[dict]:
    """
    Post-corrección: verifica coherencia entre párrafos adyacentes.
    Solo examina última oración del párrafo N y primera del N+1.
    Modelo: gpt-4o-mini (barato, solo detecta problemas).
    """
    issues = []
    for i in range(len(corrected_paragraphs) - 1):
        last_sentence = corrected_paragraphs[i]["text"].split(".")[-2]  # Penúltima oración
        first_sentence = corrected_paragraphs[i+1]["text"].split(".")[0]
        
        # LLM evalúa: ¿la transición es coherente?
        # Si detecta problema, genera sugerencia de conector o reestructuración
        result = _check_transition(last_sentence, first_sentence, profile)
        if result["needs_fix"]:
            issues.append({
                "paragraph_index": i,
                "type": "transition",
                "suggestion": result["suggestion"],
                "explanation": result["explanation"],
            })
    return issues
```

---

### FASE 4: Calidad y Validación (P1/P2)

#### 4.1 INFLESZ gate habilitado por defecto
**Archivo**: `backend/app/data/profiles.py`

Agregar targets INFLESZ a cada perfil predeterminado:

```python
PRESETS = {
    "infantil": {
        ...,
        "target_inflesz_min": 75,   # Bastante fácil a muy fácil
        "target_inflesz_max": 100,
    },
    "juvenil": {
        ...,
        "target_inflesz_min": 65,
        "target_inflesz_max": 85,
    },
    "novela_adulta": {
        ...,
        "target_inflesz_min": 55,
        "target_inflesz_max": 75,
    },
    "ensayo": {
        ...,
        "target_inflesz_min": 45,
        "target_inflesz_max": 65,
    },
    "academico": {
        ...,
        "target_inflesz_min": 35,
        "target_inflesz_max": 55,
    },
    "marketing": {
        ...,
        "target_inflesz_min": 60,
        "target_inflesz_max": 85,
    },
    # ... completar los 10 perfiles
}
```

#### 4.2 Protected terms con word boundaries
**Archivo**: `backend/app/services/quality_gates.py`

```python
# ACTUAL (naive):
if term.lower() in original.lower() and term.lower() not in corrected.lower():
    failed_terms.append(term)

# CORREGIDO (word boundary):
import re
for term in protected_terms:
    pattern = r'\b' + re.escape(term) + r'\b'
    if re.search(pattern, original, re.IGNORECASE) and not re.search(pattern, corrected, re.IGNORECASE):
        failed_terms.append(term)
```

#### 4.3 Structured Outputs con Pydantic
**Archivo**: `backend/app/utils/openai_client.py`

```python
from pydantic import BaseModel, Field
from typing import Literal

class CorrectionResponse(BaseModel):
    corrected_text: str
    changes_made: list[dict] = Field(default_factory=list)
    category: Literal[
        "ortotipografia", "lexico", "redundancia", "coherencia",
        "cohesion", "registro", "claridad", "estructura", "ritmo", "muletilla"
    ]
    severity: Literal["critical", "important", "suggestion"]
    explanation: str = Field(description="Justificación en español citando normativa")
    confidence: float = Field(ge=0.0, le=1.0)
    action: Literal["correct", "flag", "skip"] = "correct"

# Usar con Structured Outputs de OpenAI:
response = client.beta.chat.completions.parse(
    model=model,
    messages=messages,
    response_format=CorrectionResponse,
)
correction = response.choices[0].message.parsed
```

**Nota**: Requiere `openai>=1.40.0` y modelos que soporten structured outputs (gpt-4o-2024-08-06+, gpt-4o-mini).

#### 4.4 Saneamiento de páginas en blanco PDF
**Archivo**: `backend/app/services/rendering.py`

Agregar función post-conversión:

```python
import fitz  # PyMuPDF

def _sanitize_blank_pages(pdf_path: str) -> int:
    """Elimina páginas en blanco del PDF generado por LibreOffice.
    Retorna cantidad de páginas eliminadas."""
    doc = fitz.open(pdf_path)
    pages_to_delete = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        
        if len(text) == 0:
            # Sin texto. ¿Tiene imágenes o contenido visual?
            image_list = page.get_images(full=True)
            drawings = page.get_drawings()
            
            if len(image_list) == 0 and len(drawings) == 0:
                pages_to_delete.append(page_num)
    
    if pages_to_delete:
        doc.delete_pages(pages_to_delete)
        doc.save(pdf_path, incremental=False, deflate=True)
        logger.info(f"Sanitized {len(pages_to_delete)} blank pages from PDF")
    
    doc.close()
    return len(pages_to_delete)
```

Llamar después de `convert_docx_to_pdf()` en `render_docx_first_sync()`.

---

### FASE 5: Track Changes y Experiencia Editorial (P1/P2)

#### 5.1 Generación de DOCX con track changes
**Dependencia nueva**: `python-redlines` (pip install python-redlines)

**Archivo**: `backend/app/services/rendering.py`

```python
from redlines import Redlines

def generate_tracked_changes_docx(original_path: str, corrected_path: str, output_path: str):
    """Genera DOCX con marcado de cambios real (Open XML tracked changes)."""
    rl = Redlines(original_path, corrected_path)
    rl.save(output_path)
```

**Alternativa sin dependencia externa** (si python-redlines no funciona bien):
Usar `python-docx` para insertar comentarios XML en las posiciones de los patches:

```python
def _add_comment_to_paragraph(paragraph, comment_text: str, author: str = "STYLIA"):
    """Agrega un comentario de revisión al párrafo en el DOCX."""
    # Manipulación directa de Open XML para insertar w:commentRangeStart/End
    # Esto es visible como "comentario" en Word/LibreOffice
```

#### 5.2 Tres archivos de salida
**Archivo**: `backend/app/services/rendering.py`, `backend/app/api/v1/documents.py`

El sistema debe generar 3 archivos:
1. `{stem}_corrected.docx` — DOCX con correcciones aplicadas (limpio)
2. `{stem}_tracked.docx` — DOCX con track changes/comentarios (para revisión en Word)
3. `{stem}_corrected.pdf` — PDF final limpio

Nuevas URIs en MinIO:
```
docx/{doc_id}/{stem}_tracked.docx
```

Nuevo endpoint:
```
GET /documents/{id}/download/tracked-docx
```

---

### FASE 6: Tests y Estabilidad (P2)

#### 6.1 Suite de tests mínima
**Directorio**: `backend/tests/`

```
tests/
├── conftest.py                    # Fixtures: DB en memoria, mock OpenAI, mock MinIO
├── test_quality_gates.py          # Cada gate con casos edge
├── test_complexity_router.py      # Routing correcto por tipo de párrafo
├── test_prompt_builder.py         # Prompts generados correctamente
├── test_correction.py             # Corrección con mock LLM
├── test_rendering.py              # Aplicación de patches, preservación de runs
├── test_analysis.py               # Clasificación de párrafos, detección secciones
├── test_table_context.py          # Contexto de tabla extraído correctamente
├── test_api_review.py             # Endpoints accept/reject/finalize
└── test_pipeline_integration.py   # Pipeline completo con mocks
```

**Prioridad de tests**:
1. `test_quality_gates.py` — Validar que gates protegen contra alucinaciones
2. `test_rendering.py` — Validar que patches se aplican sin destruir formato
3. `test_api_review.py` — Validar flujo human-in-the-loop
4. `test_table_context.py` — Validar que tablas no se corrompen

#### 6.2 Limpieza de MinIO al eliminar documento
**Archivo**: `backend/app/api/v1/documents.py`

En el endpoint `DELETE /documents/{id}`:
```python
# ACTUAL: solo borra registros de BD
# AGREGAR: limpiar objetos en MinIO
from app.utils.minio_client import delete_document_objects

async def delete_document(doc_id: UUID, ...):
    # ... borrar BD ...
    delete_document_objects(str(doc_id))  # Borra source/, pdf/, pages/, docx/, final/
```

---

## Orden de Implementación Recomendado

```
SEMANA 1-2: FASE 1 (Human-in-the-Loop)
├── 1.1 Estado pending_review
├── 1.2 Endpoints de revisión
├── 1.3 Campos de auditoría en Patch
├── 1.4 Rendering filtrado
├── 1.5 Frontend acciones
└── 1.6 Separar corrección de rendering

SEMANA 3-4: FASE 2 (Contexto Estructural)
├── 2.1 Contexto de tabla para LLM
├── 2.2 Detección de captions
├── 2.3 Cross-references
└── 2.4 Preservación de runs mejorada

SEMANA 5-6: FASE 3 (Multi-Pasada)
├── 3.1 Pasadas léxica y estilística separadas
├── 3.2 Modelos diferenciados
├── 3.3 Ejemplos negativos
├── 3.4 Registro de decisiones estilísticas
├── 3.5 Ventana contexto ampliada
└── 3.6 Verificación de transiciones

SEMANA 7: FASE 4 (Calidad)
├── 4.1 INFLESZ habilitado
├── 4.2 Protected terms con word boundaries
├── 4.3 Structured Outputs
└── 4.4 Saneamiento páginas blanco PDF

SEMANA 8: FASE 5 (Track Changes)
├── 5.1 DOCX con track changes
└── 5.2 Tres archivos de salida

SEMANA 9-10: FASE 6 (Tests)
├── 6.1 Suite de tests
└── 6.2 Limpieza MinIO
```

---

## Criterios de Verificación por Fase

| Fase | Test de Aceptación |
|------|-------------------|
| 1 | Subir documento → corregir → revisar correcciones (accept/reject) → finalizar → DOCX solo contiene correcciones aceptadas |
| 2 | Documento con tablas → celdas NO expandidas → formato de tabla intacto → captions preservados |
| 3 | Mismo párrafo procesado en 3 pasadas → cambios léxicos separados de estilísticos → modelo potente solo en EDITORIAL |
| 4 | INFLESZ valida rango por perfil → "plan" no matchea "explanation" → JSON schema siempre válido → PDF sin páginas blanco |
| 5 | DOCX con track changes abreable en Word/LibreOffice → cambios visibles como sugerencias |
| 6 | `pytest backend/tests/` pasa al 100% → eliminar documento limpia MinIO |

---

## Dependencias Nuevas

```
# backend/requirements.txt — agregar:
python-redlines>=0.4.0    # Track changes DOCX (Fase 5)
# instructor>=1.0.0       # Opcional: Structured outputs multi-proveedor
```

**No se necesitan más dependencias**. INFLESZ, quality gates, routing ya están implementados con stdlib.

---

## Notas Arquitectónicas

1. **No romper lo que funciona**: El pipeline A→B→C→D→E actual es correcto. Solo se modifica el flujo post-D (agregar pausa) y se enriquece D (multi-pasada + contexto).

2. **Migración de BD**: Al agregar columnas a Patch y estados a Document, usar `ALTER TABLE` manual o implementar Alembic. En MVP, `create_all` maneja columnas nuevas pero no modifica existentes.

3. **Backward compatibility**: Documentos ya procesados antes de este fix tendrán `review_status=auto_accepted` y seguirán descargándose normalmente. El nuevo flujo solo aplica a documentos procesados después del deploy.

4. **Costos**: La pasada 3 con gpt-4o cuesta ~10x más que gpt-4o-mini. Para un libro de 100 páginas: ~$0.02 (solo mini) → ~$0.15 (mini + gpt-4o para EDITORIAL). Sigue siendo económico.

5. **Claude como alternativa**: Para la pasada estilística, Claude Sonnet 4.5 produce español más natural. Implementar vía `anthropic` SDK como provider alternativo en `openai_client.py` (renombrar a `llm_client.py`).
