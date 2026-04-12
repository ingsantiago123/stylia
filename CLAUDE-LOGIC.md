# CLAUDE-LOGIC.md — Lógica, Workflow y Flujo de Datos

Este documento detalla cómo fluye la información desde que el usuario sube un documento hasta que descarga el resultado corregido. Es el complemento de CLAUDE.md enfocado en el **cómo funciona internamente**.

---

## 1. Flujo completo del usuario (MVP2)

```
USUARIO                     FRONTEND                         BACKEND                          SERVICIOS EXTERNOS
  │                            │                                │                                │
  │ 1. Arrastra .docx          │                                │                                │
  │ ───────────────────────→   │                                │                                │
  │                            │ 2. POST /api/v1/upload         │                                │
  │                            │ ──────────────────────────────→│ 3. Valida + guarda MinIO       │───→ MinIO
  │                            │                                │ 4. Crea Document (status=uploaded)
  │                            │ ← Response {id, status}        │ 5. Crea Document en DB         │───→ PostgreSQL
  │                            │                                │                                │
  │ 6. Ve doc en lista          │                                │                                │
  │ ←───────────────────────   │                                │                                │
  │                            │                                │                                │
  │ [OPCIONAL] 7. Selecciona    │                                │                                │
  │    perfil editorial         │ 8. POST /documents/{id}/profile │                                │
  │ ───────────────────────→   │ ──────────────────────────────→│ 9. Crear/actualizar perfil     │───→ PostgreSQL
  │                            │ ← Response (perfil guarado)    │                                │
  │                            │                                │                                │
  │ 10. Click "Procesar"        │                                │                                │
  │ ───────────────────────→   │ 11. POST /documents/{id}/process│                                │
  │                            │ ──────────────────────────────→│ 12. Lanza Celery task          │───→ Redis (broker)
  │                            │ ← Response (tarea encolada)    │ 13. Worker: A→B→C→D→E         │
  │                            │                                │ (status: converting..correcting)
  │                            │ 14. Polling GET /documents      │                                │
  │                            │     (dinámico: 5-30s)           │                                │
  │                            │ ←──────────────────────────────│                                │
  │ 15. Ve progreso por etapa  │                                │                                │
  │ ←───────────────────────   │ 16. Pipeline finaliza           │                                │
  │                            │ ──────────────────────────────→│ candidate_rendering → candidate_ready
  │                            │ ← Doc con status=candidate_ready│                                │
  │                            │                                │                                │
  │ 17. Click en documento      │                                │                                │
  │ ───────────────────────→   │ 18. GET /documents/{id}         │                                │
  │                            │     GET /analysis               │                                │
  │                            │     GET /corrections            │                                │
  │                            │ ──────────────────────────────→│                                │
  │ 19. Ve 5 tabs + correcciones│ ←──────────────────────────────│                                │
  │ (Resumen|Análisis|Correcciones│                               │                                │
  │  |Comparar|Flujo API)        │                                │                                │
  │ ←───────────────────────   │                                │                                │
  │                            │                                │                                │
  │ [OPCIONAL HITL]            │                                │                                │
  │ 20. Revisa correcciones     │                                │                                │
  │ 21. Aprueba/rechaza patches │ 22. POST /corrections/{id}/review│                              │
  │ ───────────────────────→   │ ──────────────────────────────→│ 23. Actualiza patches         │───→ PostgreSQL
  │                            │                                │                                │
  │ 24. Click "Finalizar"       │                                │                                │
  │ ───────────────────────→   │ 25. POST /documents/{id}/finalize│                              │
  │                            │ ──────────────────────────────→│ 26. status=finalizing          │───→ Redis (worker)
  │                            │                                │ 27. Rerender DOCX/PDF final   │───→ MinIO
  │                            │ ← Response (finalizado)        │ 28. status=completed           │───→ PostgreSQL
  │                            │                                │                                │
  │ 29. Click "Descargar PDF"   │                                │                                │
  │ ───────────────────────→   │ 30. GET /download/pdf           │                                │
  │                            │ ──────────────────────────────→│ 31. Stream desde MinIO         │───→ MinIO
  │ 32. Descarga archivo final  │ ←──────────────────────────────│                                │
  │ ←───────────────────────   │                                │                                │
```

---

## 2. Pipeline de procesamiento (Celery worker)

Cuando el usuario hace POST a `/documents/{id}/process`, el endpoint dispara `process_document_pipeline` como tarea Celery en la cola `pipeline`. Esta tarea ejecuta 5 etapas secuencialmente, seguidas de 2 estados de finalización:

### ETAPA A: Ingesta (`services/ingestion.py`)

**Entrada**: doc_id, source_key (MinIO), filename, original_format
**Salida**: {pdf_uri, total_pages}

```
1. Descargar DOCX de MinIO → bytes en memoria
2. Escribir a archivo temporal
3. Ejecutar: soffice --headless --convert-to pdf --outdir {tmpdir} {docx_path}
   - Timeout: 300 segundos
   - Si falla: raise RuntimeError
4. Contar páginas del PDF con PyMuPDF: len(fitz.open(pdf_bytes))
5. Subir PDF a MinIO: pdf/{doc_id}/{stem}.pdf
6. Limpiar archivos temporales
```

**DB updates**: Document.status = "converting" → "extracting", Document.pdf_uri, Document.total_pages
**Pages creadas**: Una por cada página detectada (status="pending")

---

### ETAPA B: Extracción (`services/extraction.py`)

**Entrada**: doc_id, pdf_uri, page_no
**Salida**: {layout_uri, text_uri, preview_uri, blocks[], full_text}

```
Por cada página:
1. Descargar PDF de MinIO
2. Abrir con PyMuPDF: fitz.open(stream=pdf_bytes)
3. Extraer layout: page.get_text("dict", sort=True)
   - Retorna: {"blocks": [{type, bbox, lines: [{spans: [{text, font, size, color, flags}]}]}]}
4. Clasificar bloques:
   - type=0 → "text" (extraer líneas y spans)
   - type=1 → "image" (solo bbox)
5. Generar preview: page.get_pixmap(dpi=150) → PNG bytes
6. Subir a MinIO:
   - pages/{doc_id}/layout/{page_no}.json  (estructura completa)
   - pages/{doc_id}/text/{page_no}.txt     (texto plano concatenado)
   - pages/{doc_id}/preview/{page_no}.png  (imagen preview)
7. Crear Block records en DB (uno por bloque de texto/imagen)
```

**Estructura de un bloque extraído**:
```json
{
  "block_no": 0,
  "type": "text",
  "bbox": [72.0, 90.5, 540.3, 120.8],
  "text": "Texto completo del bloque...",
  "lines": [{
    "bbox": [72.0, 90.5, 540.3, 105.2],
    "spans": [{
      "text": "Texto ",
      "font": "TimesNewRomanPSMT",
      "size": 12.0,
      "color": 0,
      "flags": 0,
      "bbox": [72.0, 90.5, 110.3, 105.2]
    }]
  }]
}
```

---

### ETAPA C: Análisis Editorial (`services/analysis.py`)

**Entrada**: doc_id, list of Blocks with original_text
**Salida**: {sections[], glossary[], paragraph_classifications{}, inferred_profile{}}

```
1. Dividir párrafos en secciones (heurística: títulos, cambios temáticos, saltos de línea)
2. Por cada sección:
   - Generar resumen con contexto 3-párrafo ventana
   - Extraer términos clave (frecuencia, campo semántico)
   - Marcar términos protegidos (nombres, marcas, tecnicismos)
3. Clasificar cada párrafo (11 tipos):
   - intro, heading, body, list_item, table, quote, footer, code, image_caption, transition, conclusion
4. Inferir perfil editorial si no fue proporcionado:
   - Heurística: género (ensayo/narrativa/técnico), tono (formal/informal), nivel intervención (ligero/medio/profundo)
5. Actualizar Document.document_profiles.protected_terms con términos del análisis
6. Crear SectionSummary y TermRegistry records en BD
7. Guardar análisis completo en Document.analysis_json
```

**DB updates**: Document.status = "analyzing" → "correcting", SectionSummary[], TermRegistry[]

---

### ETAPA D: Corrección (`services/correction.py` + MVP2 servicios)

**Ruta 1 activa: DOCX-first** (`correct_docx_sync`)

**Entrada**: doc_id, docx_uri (MinIO key del original), config, profile (opcional), analysis_data (de Etapa C)
**Salida**: lista de patches [{paragraph_index, location, original_text, corrected_text, lt_operations, category, severity, explanation, confidence, route_taken, gate_results, review_reason}]

```
1. Descargar DOCX de MinIO → archivo temporal
2. Parsear con python-docx: DocxDocument(tmpfile)
3. Recolectar TODOS los párrafos (_collect_all_paragraphs):
   - doc.paragraphs → "body:0", "body:1", ...
   - doc.tables[t].rows[r].cells[c].paragraphs[p] → "table:0:1:2:0"
   - doc.sections[s].header.paragraphs[p] → "header:0:0"
   - doc.sections[s].footer.paragraphs[p] → "footer:0:0"

4. Por cada párrafo (si len(text.strip()) >= 3):

   PASO 0 — Router de complejidad (MVP2 Lote 4):
   ├─ Evaluar: paragraph_type (del análisis C), longitud, complejidad sintáctica, posición en sección
   ├─ Decidir ruta: SKIP | CHEAP | EDITORIAL
   ├─ SKIP: sin llamada LLM (solo LanguageTool)
   ├─ CHEAP: llamada LLM con modelo económico (openai_cheap_model)
   └─ EDITORIAL: llamada LLM con modelo potente (openai_editorial_model)

   PASO 1 — LanguageTool:
   ├─ POST http://languagetool:8010/v2/check (load-balanced en Nginx)
   │  body: {text, language: "es", disabledRules: "RULE1,RULE2"}
   ├─ Parsear response.matches[]
   ├─ Ordenar matches por offset DESCENDENTE
   ├─ Aplicar reemplazos de atrás hacia adelante:
   │  corrected = text[:offset] + replacement + text[offset+length:]
   ├─ Registrar operaciones: [{offset, length, original, replacement, rule_id, category, message}]
   └─ Resultado: post_lt_text (texto con ortografía/gramática corregida)

   PASO 2 — ChatGPT (estilo, si ruta != SKIP):
   ├─ Construir prompt con PromptBuilder (MVP2 Lote 2):
   │  ├─ System: cacheable, sin variables
   │  ├─ User: dinámico incluye
   │  │  ├─ Instrucciones del perfil (si aplica)
   │  │  ├─ Contexto jerárquico: section_summary, active_terms, paragraph_type (MVP2 Lote 4)
   │  │  ├─ Contexto acumulado: últimos 3 párrafos corregidos
   │  │  ├─ Límite de caracteres (max_expansion_ratio del perfil)
   │  │  └─ Texto a corregir (post_lt_text)
   │  └─ response_format: {"type": "json_object"}
   ├─ Llamar OpenAI API con modelo elegido por router:
   │  client.chat.completions.create(model=model, temperature=0.3, max_tokens=500)
   ├─ Parsear JSON: {"corrected_text": "...", "changes_made": [...], "character_count": N}
   └─ Fallback: _simulate_correction() o usar post_lt_text

   PASO 3 — Quality Gates (MVP2 Lote 5):
   ├─ Validar corrección post-LLM:
   │  ├─ gate_not_empty (CRÍTICO): texto no vacío
   │  ├─ gate_expansion_ratio (CRÍTICO): len(corrected) <= 110% original
   │  ├─ gate_protected_terms (CRÍTICO): términos protegidos preservados
   │  ├─ gate_rewrite_ratio (no-crítico): distancia edición normalizada
   │  ├─ gate_language_preserved (no-crítico): proporción chars españoles
   │  └─ gate_readability_inflesz (no-crítico): INFLESZ en rango target
   ├─ Decisión:
   │  ├─ Si gate crítico falla → gate_rejected, usa original, marca para manual_review
   │  ├─ Si solo gates no-críticos fallan → valida, marca review_reason
   │  └─ Si todo pasa → valida
   └─ Resultado: final_text, gate_results (JSONB), review_reason

   CONTEXTO ACUMULADO (MVP2 Lote 4):
   ├─ Mantener contexto jerárquico por sección + últimos 3 corregidos
   ├─ corrected_context.append(final_text) después de cada párrafo
   └─ Se pasan [section_summary, active_terms, corrected_context[-3:]] al siguiente

5. Guardar patches JSON en MinIO: docx/{doc_id}/patches_docx.json
6. Crear Patch records en DB con campos MVP2:
   - category, severity (MVP2 Lote 2)
   - explanation, confidence, rewrite_ratio (MVP2 Lote 2)
   - route_taken (MVP2 Lote 4)
   - gate_results, review_reason (MVP2 Lote 5)
7. Actualizar Document.review_status = pending_review si hay patches con manual_review=True
```

**Estructura de un patch**:
```json
{
  "paragraph_index": 5,
  "location": "body:5",
  "original_text": "Este texto esta mal escrito.",
  "corrected_text": "Este texto está correctamente redactado.",
  "lt_operations": [
    {
      "offset": 11,
      "length": 4,
      "original": "esta",
      "replacement": "está",
      "rule_id": "MORFOLOGIK_RULE_ES",
      "category": "TYPOS",
      "message": "Se ha encontrado un posible error ortográfico."
    }
  ],
  "source": "languagetool+chatgpt"
}
```

---

### ETAPA E: Renderizado (`services/rendering.py`)

**Entrada**: doc_id, docx_uri, filename, all_patches (lista de patches de Etapa D, incluyendo approved de HITL)
**Salida**: {corrected_docx_uri, corrected_pdf_uri, changes_count}

```
1. Descargar DOCX original de MinIO → archivo local temporal
2. Abrir con python-docx: DocxDocument(local_docx)
3. Por cada patch (filtrar: solo approved=True):
   a. Localizar párrafo: _get_paragraph_by_location(doc, location)
      - Parsea "body:5" → doc.paragraphs[5]
      - Parsea "table:0:1:2:0" → doc.tables[0].rows[1].cells[2].paragraphs[0]
      - Parsea "header:0:0" → doc.sections[0].header.paragraphs[0]
   b. Verificar: paragraph.text.strip() == original_text
      - Si NO coincide → skip (log warning)
      - Si SÍ coincide → aplicar
   c. Aplicar: _apply_text_to_paragraph_runs(paragraph, corrected_text)
      - runs[0].text = corrected_text  (todo el texto en primer run)
      - runs[1:].text = ""             (vaciar resto para no duplicar)
      - PRESERVA: formato del primer run (font, bold, italic, size, color)

4. Guardar DOCX corregido: {stem}_corrected.docx en tmpdir
5. Convertir a PDF: soffice --headless --convert-to pdf
6. Subir a MinIO:
   - docx/{doc_id}/{stem}_corrected.docx
   - final/{doc_id}/{stem}_corrected.pdf
7. Marcar patches como applied=True en DB

DB updates: Document.status = "candidate_rendering" → "candidate_ready"
Document.docx_uri actualizado, Document.pdf_uri actualizado
```

---

### ESTADO INTERMEDIO: Candidato listo para revisión (`POST /documents/{id}/finalize`)

**Entrada**: doc_id, user_review_feedback (opcional)
**Salida**: {review_summary, stats}

```
document.status = "candidate_ready"

El documento permanece en estado candidato hasta que el usuario:
- Revisa las correcciones en frontend (CorrectionHistory + DiffCompareView)
- Aprueba/rechaza correcciones individuales (MVP2 HITL)
- Opcionalmente edita correcciones manualmente
- Haz click "Finalizar" → POST /documents/{id}/finalize

En candidate_ready, el usuario puede:
- Descargar "candidato" (DOCX/PDF con correcciones aprobadas)
- Reabrir (status=correcting) para relanzar corrección con cambios
- Finalize (status=finalizing)
```

---

### ESTADO FINAL: Finalizando y Completado

**POST `/documents/{id}/finalize`**

```
1. Document.status = "finalizing"
2. Celery worker tarea finalize_document:
   a. Si hay edits manuales desde HITL:
      - Recolectar patches editados manualmente
      - Lanzar quality_gates nuevamente
      - Si pasan → aplicar
   b. Renderizar final (Etapa E nuevamente si hay cambios)
   c. Generar estadísticas finales y resumen de cambios
   d. Marcar Document.review_status = "completed"
3. Document.status = "completed"
4. Subir resumen a MinIO: final/{doc_id}/summary.json
5. Actualizar BD: Document.completed_at, Document.final_review_notes
```

---

## 3. Cómo se construye el prompt para el LLM

El prompt se construye en `openai_client.py:correct_text_style()`:

```
┌─────────────────────────────────────────────────────────────────┐
│ SYSTEM MESSAGE                                                  │
│ "Eres un corrector de estilo experto en español. Siempre       │
│  respondes en formato JSON válido."                             │
├─────────────────────────────────────────────────────────────────┤
│ USER MESSAGE                                                    │
│                                                                  │
│ Eres un corrector de estilo profesional en español. Tu tarea    │
│ es corregir y mejorar el siguiente párrafo.                     │
│                                                                  │
│ INSTRUCCIONES ESTRICTAS:                                        │
│ - Mejora claridad, concisión y fluidez del texto                │
│ - Mejora la redacción y el estilo sin alterar el tono del autor │
│ - NO cambies el significado ni el contenido                     │
│ - Mantén consistencia con el contexto previo                    │
│ - Máximo {max_length} caracteres                                │
│ - Responde SOLO con el JSON sin explicaciones                   │
│                                                                  │
│ Formato de respuesta JSON requerido:                            │
│ {                                                                │
│   "corrected_text": "texto corregido aquí",                     │
│   "changes_made": ["lista", "de", "cambios"],                   │
│   "character_count": número_de_caracteres                       │
│ }                                                                │
│                                                                  │
│ [SI HAY CONTEXTO:]                                              │
│ CONTEXTO PREVIO (párrafos ya corregidos):                       │
│ Párrafo 1: {corrected_context[-3]}                              │
│ Párrafo 2: {corrected_context[-2]}                              │
│ Párrafo 3: {corrected_context[-1]}                              │
│                                                                  │
│ PÁRRAFO A CORREGIR:                                             │
│ {original_text}                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Parámetros de la llamada API:
```python
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[system_msg, user_msg],
    max_tokens=500,
    temperature=0.3,
    response_format={"type": "json_object"}
)
```

### Post-procesamiento de la respuesta:
```python
content = response.choices[0].message.content  # string JSON
data = json.loads(content)
corrected = data["corrected_text"]

# Validación de longitud
if len(corrected) > int(len(original) * 1.1):
    return original  # rechazar si excede 110%
return corrected
```

---

## 4. Contexto acumulado: cómo se mantiene coherencia entre párrafos

```
Párrafo 1: se corrige SIN contexto
           → corrected_context = ["texto corregido 1"]

Párrafo 2: se corrige CON contexto = ["texto corregido 1"]
           → corrected_context = ["texto corregido 1", "texto corregido 2"]

Párrafo 3: se corrige CON contexto = ["texto corregido 1", "texto corregido 2"]
           → corrected_context = ["texto corregido 1", "texto corregido 2", "texto corregido 3"]

Párrafo 4: se corrige CON contexto = ["texto corregido 2", "texto corregido 3"]  ← ventana de 3
           → corrected_context = [..., "texto corregido 4"]

Párrafo N: siempre recibe los últimos 3 párrafos ya corregidos
```

La ventana de 3 párrafos se implementa con: `corrected_context[-3:]`

Esto le permite al LLM:
- Mantener un tono consistente a lo largo del documento
- No repetir correcciones que ya se hicieron
- Preservar la narrativa y las transiciones entre párrafos
- Usar terminología consistente con lo ya corregido

---

## 5. Cómo se editan los documentos (preservación de formato)

### El problema
Un párrafo en python-docx se compone de **runs** (fragmentos con formato individual):
```
Párrafo: "Este es un texto en negrita y normal"
Run 1: "Este es un texto en "  (font: Times, 12pt)
Run 2: "negrita"               (font: Times, 12pt, bold)
Run 3: " y normal"             (font: Times, 12pt)
```

Si reemplazamos el texto completo, necesitamos manejar los runs correctamente.

### La solución actual (MVP)
```python
def _apply_text_to_paragraph_runs(paragraph, new_text):
    runs = paragraph.runs
    # Poner TODO el texto corregido en el primer run
    runs[0].text = new_text
    # Vaciar los demás runs
    for run in runs[1:]:
        run.text = ""
```

**Limitación**: Se preserva el formato del **primer run** solamente. Si el párrafo tenía negrita parcial, cursiva, etc., esos formatos se pierden. El texto completo hereda el formato de `runs[0]`.

**Esto es aceptable en MVP** porque:
- La mayoría de párrafos editoriales tienen formato uniforme
- Preservar formato parcial requiere diff character-level (planificado para fases futuras)
- Es mejor tener texto corregido con formato simple que texto incorrecto con formato perfecto

---

## 6. Cómo interactúa el usuario con la aplicación

### Dashboard (Home `/`)

```
┌─────────────────────────────────────────────────────────┐
│ STYLIA                                          ● Live  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  ⬆ Arrastra un archivo .docx aquí                 │  │
│  │    o haz clic para seleccionar                    │  │
│  │    Formatos: .docx — Máximo 500 MB                │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  📄 2 documento(s) en proceso                           │
│                                                         │
│  ┌────────────────┐  ┌────────────────┐                 │
│  │ tesis_cap3.docx│  │ informe.docx   │                 │
│  │ ● Corrigiendo  │  │ ✓ Completado   │                 │
│  │ ██████░░░ 60%  │  │ [PDF] [DOCX]   │                 │
│  │ 5 págs         │  │ 12 págs        │                 │
│  └────────────────┘  └────────────────┘                 │
│                                                         │
│  v0.1.0 — Corrección de estilo con IA                   │
└─────────────────────────────────────────────────────────┘
```

### Vista de detalle (`/documents/[id]`)

5 tabs disponibles (MVP2 completado):

1. **Resumen**: Estado del documento, progreso por etapa, perfiles (inferido vs seleccionado), estadísticas de correcciones
2. **Análisis**: Secciones detectadas (MVP2 Lote 3), glosario de términos, distribución de tipos de párrafos, perfil editorial inferido
3. **Correcciones**: Lista filtrable con diff word-level (rojo=original, verde=corregido), filtros por categoría/severidad/ruta (MVP2 Lote 2/4), badges de estado y confianza
4. **Comparar**: Vista side-by-side original/corregido con modo diff avanzado, anotaciones de calidad (MVP2 Lote 5)
5. **Flujo API**: Timeline de requests a LanguageTool y ChatGPT con contexto jerárquico (MVP2 Lote 4)

### Acciones del usuario:

**Fase upload**:
- **Subir**: Drag-drop o click → solo .docx
- **Ver estado**: Doc aparece en lista con status=uploaded

**Fase selección de perfil**:
- **(Opcional) Seleccionar perfil**: Grid de 10 presets o editor custom
- **Sin perfil**: Usar flujo genérico MVP1

**Fase procesamiento**:
- **Procesar**: Click botón → POST /documents/{id}/process
- **Monitorear**: Polling dinámico muestra progreso por etapa (5-30s según estado)
- **Ver detalles**: Click documento → 5 tabs con análisis completo

**Fase revisión (HITL)**:
- **Revisar correcciones**: Expandir cards para ver diff detallado y explicaciones (MVP2 Lote 2)
- **Filtrar**: Por categoría, severidad, ruta SKIP/CHEAP/EDITORIAL (MVP2 Lotes 2/4)
- **Aprobar/rechazar**: Acciones en patches individuales (HITL)
- **Descargar candidato**: PDF/DOCX con correcciones aprobadas (status=candidate_ready)

**Fase finalización**:
- **Finalizar**: Click "Completar" → POST /documents/{id}/finalize → status=completed
- **Reabrir**: Para relanzar corrección → status=correcting
- **Descargar final**: PDF/DOCX final (status=completed)
- **Eliminar**: Botón rojo con confirmación

**Costos**:
- **Ver costos**: Tab `/costs` con resumen de llamadas LLM y costos agregados por documento

---

## 7. LanguageTool: cómo funciona la corrección ortográfica

### Request
```http
POST http://languagetool:8010/v2/check
Content-Type: application/x-www-form-urlencoded

text=Este texto esta mal escrito a proposito&language=es
```

### Response (simplificada)
```json
{
  "matches": [
    {
      "offset": 11,
      "length": 4,
      "message": "Se ha encontrado un posible error",
      "replacements": [{"value": "está"}],
      "rule": {"id": "MORFOLOGIK_RULE_ES", "category": {"id": "TYPOS"}}
    },
    {
      "offset": 30,
      "length": 9,
      "message": "Falta tilde",
      "replacements": [{"value": "propósito"}],
      "rule": {"id": "MORFOLOGIK_RULE_ES", "category": {"id": "TYPOS"}}
    }
  ]
}
```

### Aplicación de correcciones
Se aplican **de atrás hacia adelante** (offset descendente) para no alterar las posiciones:
```python
sorted_matches = sorted(matches, key=lambda m: m["offset"], reverse=True)
for match in sorted_matches:
    corrected = corrected[:offset] + replacement + corrected[offset + length:]
```

Resultado: `"Este texto está mal escrito a propósito"`

---

## 8. Flujo de datos entre componentes

```
                          ┌────────────┐
                          │   MinIO    │
                          │  (S3 obj)  │
                          └──────┬─────┘
                                 │ download/upload
                                 │
┌──────────┐    HTTP    ┌───────┴──────┐    SQL     ┌────────────┐
│ Frontend │◄──────────►│   FastAPI    │◄──────────►│ PostgreSQL │
│ Next.js  │  REST API  │   Backend   │  SQLAlchemy │  (ORM)     │
└──────────┘            └───────┬──────┘            └────────────┘
                                │ enqueue task
                                │
                          ┌─────┴──────┐
                          │   Redis    │
                          │  (broker)  │
                          └─────┬──────┘
                                │ consume task
                                │
                          ┌─────┴──────┐    HTTP    ┌──────────────┐
                          │   Celery   │◄──────────►│ LanguageTool │
                          │   Worker   │            └──────────────┘
                          │            │    HTTP    ┌──────────────┐
                          │            │◄──────────►│  OpenAI API  │
                          └────────────┘            └──────────────┘
```

### Flujo de un archivo a través del sistema:
```
1. Upload  → MinIO: source/{doc_id}/archivo.docx
2. Convert → MinIO: pdf/{doc_id}/archivo.pdf
3. Extract → MinIO: pages/{doc_id}/layout/1.json, text/1.txt, preview/1.png
4. Correct → MinIO: docx/{doc_id}/patches_docx.json
5. Render  → MinIO: docx/{doc_id}/archivo_corrected.docx
                     final/{doc_id}/archivo_corrected.pdf
```

---

## 9. Manejo de errores y fallbacks

| Escenario | Comportamiento |
|-----------|---------------|
| OpenAI API sin key | `_simulate_correction()`: reemplazos hardcoded básicos |
| OpenAI API falla (timeout, error) | Retorna `None` → se usa texto post-LanguageTool |
| OpenAI respuesta excede 110% | Se descarta corrección, se usa texto original |
| LanguageTool falla (timeout, error) | Retorna texto original sin cambios |
| LibreOffice conversión falla | Raise RuntimeError → pipeline falla, retry en 60s |
| Texto párrafo no coincide al aplicar patch | Skip silencioso con warning log |
| Celery task falla | Retry x3 con countdown=60s, luego marca "failed" |
| Archivo demasiado grande | HTTP 413 antes de procesar |
| Formato no .docx | HTTP 400 con mensaje descriptivo |

---

## 10. Configuración por documento (config_json)

Cada documento puede tener configuración personalizada almacenada en `documents.config_json` (JSONB):

```json
{
  "language": "es",
  "lt_disabled_rules": ["WHITESPACE_RULE", "UPPERCASE_SENTENCE_START"],
  "perfectionista": false,
  "custom_dict": ["STYLIA", "ChatGPT"],
  "style_guide": "formal"
}
```

Actualmente solo se usan `language` y `lt_disabled_rules`. El resto está preparado para fases futuras.

---

## 11. Tracking de progreso (cómo se calcula)

El frontend calcula el progreso del documento basado en la etapa actual y un heartbeat/evento de progreso:

**Modelo MVP2** (etapas A-B-C-D-E):
```
- converting (etapa A): 10% (estimado)
- extracting (etapa B): 20% (estimado)
- analyzing (etapa C): 30% (estimado)
- correcting (etapa D): 75% (basado en párrafos procesados: heartbeat)
- candidate_rendering (etapa E): 90% (estimado)
- candidate_ready: 100%
- finalizing → completed: 100%
```

El backend emite **heartbeats de progreso** durante la Etapa D (corrección) para indicar avance real:
```
POST /documents/{id}/progress
{
  "current_paragraph": N,
  "total_paragraphs": M,
  "percentage": (N/M) * 75
}
```

El frontend polling obtiene este dato cada 5-30s según el estado:
- Etapas rápidas (A, B, C): polling cada 30s
- Etapa D (corrección): polling cada 5s (conteo de párrafos procesados)
- Etapas finales (E, finalize): polling cada 10s

**Cálculo de progreso global**:
```python
progress_by_stage = {
  "converting": 0.10,
  "extracting": 0.20,
  "analyzing": 0.30,
  "correcting": 0.30 + (current_para / total_paras) * 0.45,
  "candidate_rendering": 0.90,
  "candidate_ready": 1.0,
  "finalizing": 1.0,
  "completed": 1.0
}
current_progress = progress_by_stage[document.status]
```

---

## 12. Diferencia entre Ruta 1, 2 y 3

| Ruta | Entrada | Estado | Descripción |
|------|---------|--------|-------------|
| **Ruta 1** (activa) | DOCX | MVP 1 | Corrige directamente párrafos del DOCX, evita fragmentación PDF |
| **Ruta 2** (futura) | PDF digital | Fase 3 | Extrae bloques del PDF, corrige y regenera overlay |
| **Ruta 3** (futura) | PDF escaneado | Fase 4 | OCR → texto → corrección → overlay sobre imagen |

La Ruta 1 fue elegida para MVP porque:
- Los párrafos del DOCX están completos (no fragmentados como en PDF)
- Se preserva la estructura del documento (tablas, headers, footers)
- python-docx permite manipulación directa de runs
- La conversión final a PDF con LibreOffice mantiene fidelidad visual
