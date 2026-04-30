# REGISTRO MVP2 — Tracking IA + Humano

## Resumen de Lotes

| Lote | Nombre | Estado | Fecha inicio | Fecha validación |
|------|--------|--------|-------------|-----------------|
| 1 | Perfiles Editoriales + Flujo Separado | IA COMPLETADO | 2026-03-24 | Pendiente validacion |
| 2 | Prompt Parametrizado + Patches Enriquecidos | IA COMPLETADO | 2026-03-24 | Pendiente validacion |
| 3 | Etapa C: Análisis Editorial | IA COMPLETADO | 2026-03-25 | Pendiente validacion |
| 4 | Contexto Jerárquico + Router Complejidad | IA COMPLETADO | 2026-03-26 | Pendiente validacion |
| 5 | Quality Gates + Métricas INFLESZ | IA COMPLETADO | 2026-03-26 | Pendiente validacion |

---

## LOTE 1 — Perfiles Editoriales + Flujo Separado

### Tareas

| # | Tarea | Estado | Implementado por | Validado por usuario | Notas |
|---|-------|--------|-----------------|---------------------|-------|
| 1.1 | Modelo DocumentProfile (DB) | HECHO | IA | — | backend/app/models/style_profile.py |
| 1.2 | Relationship en Document | HECHO | IA | — | profile (uselist=False) en document.py |
| 1.3 | 10 presets editoriales | HECHO | IA | — | backend/app/data/profiles.py |
| 1.4 | Schemas Pydantic de perfiles | HECHO | IA | — | backend/app/schemas/style_profile.py |
| 1.5 | API: separar upload/process | HECHO | IA | — | POST /upload ya no lanza pipeline |
| 1.6 | API: endpoints CRUD profile | HECHO | IA | — | POST/GET/PUT /documents/{id}/profile |
| 1.7 | API: endpoint GET /presets | HECHO | IA | — | GET /presets retorna 10 presets |
| 1.8 | Frontend: api.ts tipos/funciones | HECHO | IA | — | StyleProfile, PresetInfo, etc. |
| 1.9 | Frontend: ProfileSelector.tsx | HECHO | IA | — | Grid 10 cards con iconos SVG |
| 1.10 | Frontend: ProfileEditor.tsx | HECHO | IA | — | Sliders, tags, toggles |
| 1.11 | Frontend: nuevo flujo page.tsx | HECHO | IA | — | Upload → ProfileSelector → Process |
| 1.12 | Actualizar CLAUDE.md | HECHO | IA | — | Estructura, API, DB, roadmap |

### Pruebas de Validación (usuario)

- [ ] `docker-compose up --build` levanta sin errores
- [ ] Subir .docx → aparece selector de perfiles (NO se procesa automático)
- [ ] Ver 10 perfiles con descripciones
- [ ] Seleccionar perfil → click "Procesar" → doc se procesa
- [ ] GET /api/v1/documents/{id}/profile retorna perfil correcto
- [ ] "Personalizar" → ajustar campos → procesar
- [ ] "Sin perfil" → procesa como MVP1

### Log de sesión

#### 2026-03-24 — Sesión 1 (IA)
- Análisis completo del codebase MVP1 (todos los modelos, servicios, API, frontend)
- Diseño de plan por lotes (5 lotes incrementales)
- Implementación completa Lote 1:
  - Creado modelo DocumentProfile con 20+ campos editoriales
  - 10 presets editoriales con UI info (icono, nombre, descripción)
  - Schemas Pydantic para CRUD de perfiles
  - API: separado upload de process (antes era automático)
  - API: endpoints CRUD profile + GET /presets
  - Frontend: ProfileSelector con grid de cards, iconos SVG, badges de intervención
  - Frontend: ProfileEditor con sliders, radio buttons, tags, toggles
  - Frontend: page.tsx con flujo Upload → Selector → Procesar
  - DocumentUploader modificado con callback onUploaded
  - CLAUDE.md actualizado con nueva estructura y endpoints
- **Pendiente**: Validación por usuario con docker-compose up --build

---

## LOTE 2 — Prompt Parametrizado + Patches Enriquecidos

### Tareas

| # | Tarea | Estado | Implementado por | Validado por usuario | Notas |
|---|-------|--------|-----------------|---------------------|-------|
| 2.1 | Campos enriquecidos en modelo Patch (DB) | HECHO | IA | — | category, severity, explanation, confidence, rewrite_ratio, pass_number, model_used |
| 2.2 | Schemas Pydantic con campos nuevos | HECHO | IA | — | PatchListItem + PatchDetail actualizados |
| 2.3 | PromptBuilder (system + user prompt) | HECHO | IA | — | backend/app/services/prompt_builder.py |
| 2.4 | openai_client: correct_with_profile() | HECHO | IA | — | Método nuevo que acepta prompts externos |
| 2.5 | correction.py: usar perfil + parsear respuesta | HECHO | IA | — | Pipeline parametrizado con fallback MVP1 |
| 2.6 | tasks_pipeline.py: cargar perfil de BD | HECHO | IA | — | Carga DocumentProfile, pasa dict a correct_docx_sync |
| 2.7 | API: list_corrections con campos enriquecidos | HECHO | IA | — | Pasa category, severity, etc. al schema |
| 2.8 | Frontend: api.ts tipos enriquecidos | HECHO | IA | — | PatchListItem con 7 campos nuevos |
| 2.9 | Frontend: CorrectionHistory.tsx mejorado | HECHO | IA | — | Filtros categoría/severidad, badges coloreados, explicación, confianza |
| 2.10 | Actualizar REGISTRO-MVP2.md y CLAUDE.md | HECHO | IA | — | Este registro |

### Pruebas de Validación (usuario)

- [ ] `docker-compose up --build` levanta sin errores
- [ ] Subir doc → seleccionar perfil "ensayo" → procesar → ver correcciones
- [ ] Las correcciones muestran badges de categoría (coloreados) y severidad
- [ ] Filtrar por categoría (dropdown) → solo muestra las de esa categoría
- [ ] Filtrar por severidad (dropdown) → solo muestra las de esa severidad
- [ ] Expandir corrección → ver sección "Explicación" con razón del cambio
- [ ] Expandir corrección → ver confianza % y modelo usado en metadata
- [ ] Subir doc → "Sin perfil" → procesar → funciona como MVP1 (sin categorías)
- [ ] Procesar con 2 perfiles distintos → ver diferencias en correcciones

### Log de sesión

#### 2026-03-24 — Sesión 1 (IA)
- Implementación completa Lote 2:
  - Modelo Patch: 7 nuevas columnas (category, severity, explanation, confidence, rewrite_ratio, pass_number, model_used)
  - Schemas Pydantic actualizados con campos nuevos en PatchListItem y PatchDetail
  - PromptBuilder: system prompt estático (~800 tokens) con reglas, categorías, severidades, schema JSON, ejemplos
  - PromptBuilder: user prompt dinámico con perfil codificado, contexto previo, párrafo
  - openai_client: nuevo método correct_with_profile() que acepta prompts externos y valida longitud
  - correction.py: correct_docx_sync() ahora acepta profile dict, usa PromptBuilder cuando hay perfil, fallback a MVP1 sin perfil
  - tasks_pipeline.py: carga DocumentProfile de BD, convierte a dict, pasa a correct_docx_sync(); patches en BD se crean con campos enriquecidos (un patch por cambio LLM)
  - API: list_corrections pasa los 7 campos nuevos al schema
  - Frontend api.ts: PatchListItem con 7 campos nuevos
  - CorrectionHistory.tsx: filtros dropdown por categoría y severidad, badges coloreados por categoría (9 colores) y severidad (3 colores), sección de explicación en card expandida, indicador de confianza con color semáforo, modelo usado en metadata
- **Pendiente**: Validación por usuario con docker-compose up --build

---

## LOTE 3 — Etapa C: Análisis Editorial

### Tareas

| # | Tarea | Estado | Implementado por | Validado por usuario | Notas |
|---|-------|--------|-----------------|---------------------|-------|
| 3.1 | Modelo SectionSummary (DB) | HECHO | IA | — | backend/app/models/section_summary.py |
| 3.2 | Modelo TermRegistry (DB) | HECHO | IA | — | backend/app/models/term_registry.py |
| 3.3 | Extender Block con paragraph_type, requires_llm, section_id | HECHO | IA | — | 3 columnas nuevas + FK a section_summaries |
| 3.4 | Document: status "analyzing" + relaciones sections/terms | HECHO | IA | — | Nuevo estado en pipeline |
| 3.5 | Registrar modelos + migraciones startup | HECHO | IA | — | __init__.py + main.py ALTER TABLE |
| 3.6 | Schemas Pydantic de análisis | HECHO | IA | — | backend/app/schemas/analysis.py |
| 3.7 | Servicio analysis.py (C.1-C.5) | HECHO | IA | — | Inferencia perfil, secciones, glosario, clasificación |
| 3.8 | Integrar Etapa C en pipeline Celery | HECHO | IA | — | Entre Etapa B y Etapa D, persiste en DB |
| 3.9 | Endpoint GET /documents/{id}/analysis | HECHO | IA | — | Retorna secciones, términos, perfil inferido |
| 3.10 | Frontend: AnalysisView.tsx | HECHO | IA | — | Secciones, glosario, distribución tipos, perfil |
| 3.11 | Frontend: tab Análisis + etapa pipeline | HECHO | IA | — | Nueva etapa "Analizando" en PipelineFlow |
| 3.12 | Frontend: api.ts tipos + funciones | HECHO | IA | — | AnalysisResult, getDocumentAnalysis() |

### Pruebas de Validación (usuario)

- [ ] `docker-compose up --build` levanta sin errores
- [ ] Subir doc → ver etapa "Análisis" en pipeline (entre Extracción y Corrección)
- [ ] Doc completado → tab "Análisis" muestra secciones con resúmenes
- [ ] Tab "Análisis" muestra glosario de términos (con protegidos marcados)
- [ ] Tab "Análisis" muestra distribución de tipos de párrafo (barras)
- [ ] Tab "Análisis" muestra perfil inferido (género, audiencia, registro, tono)
- [ ] Los términos protegidos del análisis se agregan al perfil para corrección
- [ ] Endpoint GET /api/v1/documents/{id}/analysis retorna datos correctos
- [ ] Doc "Sin perfil" → análisis infiere perfil automáticamente

### Log de sesión

#### 2026-03-25 — Sesión 1 (IA)
- Análisis completo del estado actual: Lotes 1-2 committed, Lote 2.5 (costos) uncommitted
- Diseño e implementación completa Lote 3:
  - **Modelos**: SectionSummary (resumen por sección con topic, tono, términos activos, transiciones), TermRegistry (glosario con frecuencia, protección, normalización)
  - **Block extendido**: paragraph_type (11 tipos), requires_llm (bool), section_id (FK)
  - **Servicio analysis.py**: 5 sub-etapas implementadas:
    - C.1+C.2: Inferencia de perfil con LLM (1 llamada GPT sobre muestras del documento)
    - C.3: Detección de secciones por headings python-docx + resúmenes batch con LLM
    - C.4: Extracción de términos por frecuencia de n-gramas + merge con perfil
    - C.5: Clasificación heurística de párrafos (sin LLM): heading→titulo, tabla→celda_tabla, "—"→dialogo, bullet→lista, etc.
  - **Pipeline**: Etapa C insertada entre B y D, con nuevo status "analyzing"
  - **API**: Endpoint GET /documents/{id}/analysis
  - **Frontend**: AnalysisView con 4 cards (secciones, glosario, tipos, perfil), tab "Análisis", etapa "Analizando" en PipelineFlow
  - Términos protegidos del análisis se mergean al perfil antes de Etapa D
  - Costos del análisis se registran en LlmUsage (call_type: analysis_c1, analysis_c3)
- **Pendiente**: Validación por usuario con docker-compose up --build

---

## LOTE 4 — Contexto Jerárquico + Router Complejidad

### Tareas

| # | Tarea | Estado | Implementado por | Validado por usuario | Notas |
|---|-------|--------|-----------------|---------------------|-------|
| 4.1 | complexity_router.py (SKIP/CHEAP/EDITORIAL) | HECHO | IA | — | route_paragraph() + compute_section_position() |
| 4.2 | Config: openai_cheap_model + openai_editorial_model | HECHO | IA | — | Ambos default gpt-4o-mini, configurables via .env |
| 4.3 | openai_client: model_override en correct_with_profile() | HECHO | IA | — | Permite usar modelo distinto por ruta |
| 4.4 | prompt_builder: contexto jerárquico | HECHO | IA | — | section_summary, active_terms, paragraph_type con hints |
| 4.5 | correction.py: integrar router + análisis | HECHO | IA | — | Router decide ruta, sección da contexto al prompt |
| 4.6 | tasks_pipeline.py: pasar analysis_data | HECHO | IA | — | analysis_result se pasa a correct_docx_sync() |
| 4.7 | Patch model: columna route_taken | HECHO | IA | — | VARCHAR(15) + migración startup + schema |
| 4.8 | Frontend: route badges + stats | HECHO | IA | — | Badge Skip/Cheap/Editorial + contadores en stats bar |
| 4.9 | API: pasar route_taken en list_corrections | HECHO | IA | — | PatchListItem incluye route_taken |
| 4.10 | Actualizar REGISTRO-MVP2.md y CLAUDE.md | HECHO | IA | — | Este registro |

### Pruebas de Validación (usuario)

- [ ] `docker-compose up --build` levanta sin errores
- [ ] Subir doc con perfil → procesar → ver correcciones con badges de ruta (Skip/Cheap/Editorial)
- [ ] Stats bar muestra contadores por ruta (cuántos Skip, Cheap, Editorial)
- [ ] Logs del worker muestran distribución de rutas: `rutas: skip=N cheap=N editorial=N`
- [ ] Párrafos tipo "titulo" y "encabezado" hacen SKIP (no llaman al LLM)
- [ ] Párrafos de transición de sección usan ruta EDITORIAL
- [ ] Correcciones con perfil muestran contexto de sección en explicaciones
- [ ] Doc "Sin perfil" → sigue funcionando con fallback MVP1
- [ ] Endpoint GET /api/v1/documents/{id}/corrections retorna route_taken

### Log de sesión

#### 2026-03-26 — Sesión 1 (IA)
- Implementación completa Lote 4:
  - **complexity_router.py** (NUEVO): Router con 3 rutas (SKIP, CHEAP, EDITORIAL) basado en:
    - Tipo de párrafo (titulo/encabezado/cita → SKIP, celda_tabla/lista → CHEAP)
    - Longitud y complejidad sintáctica (subordinadas anidadas → EDITORIAL)
    - Posición en sección (primer/último párrafo → EDITORIAL)
    - Transiciones entre secciones → EDITORIAL
    - Nivel de intervención del perfil (mínima → CHEAP, agresiva + largo → EDITORIAL)
    - compute_section_position() para localizar párrafo en su sección
  - **config.py**: Nuevos settings `openai_cheap_model` y `openai_editorial_model` (ambos default gpt-4o-mini)
  - **openai_client.py**: `correct_with_profile()` acepta `model_override` para usar modelo distinto por ruta
  - **prompt_builder.py**: `build_user_prompt()` ahora recibe section_summary, active_terms, paragraph_type con hints contextuales por tipo
  - **correction.py**: `correct_docx_sync()` acepta `analysis_data`, usa router para decidir ruta, pasa contexto jerárquico al prompt, selecciona modelo según ruta, logging de distribución de rutas
  - **tasks_pipeline.py**: Pasa `analysis_result` a `correct_docx_sync()`, almacena `route_taken` en cada Patch
  - **Patch model**: Nueva columna `route_taken` (VARCHAR 15) + migración startup
  - **Schemas**: PatchListItem y PatchDetail incluyen `route_taken`
  - **API**: `list_corrections` pasa `route_taken` al response
  - **Frontend**: ROUTE_COLORS map, badges Skip/Cheap/Editorial en CorrectionCard, contadores de rutas en stats bar
- **Pendiente**: Validación con docker-compose up --build

---

## LOTE 5 — Quality Gates + Métricas INFLESZ

### Tareas

| # | Tarea | Estado | Implementado por | Validado por usuario | Notas |
|---|-------|--------|-----------------|---------------------|-------|
| 5.1 | Servicio quality_gates.py | HECHO | IA | — | 5 gates + INFLESZ + orquestador |
| 5.2 | gate_not_empty (crítico) | HECHO | IA | — | Texto corregido no vacío |
| 5.3 | gate_expansion_ratio (crítico) | HECHO | IA | — | len(corrected)/len(original) <= max |
| 5.4 | gate_rewrite_ratio (no-crítico) | HECHO | IA | — | SequenceMatcher difflib, sin dependencia |
| 5.5 | gate_protected_terms (crítico) | HECHO | IA | — | Términos protegidos deben mantenerse |
| 5.6 | gate_language_preserved (no-crítico) | HECHO | IA | — | Heurístico chars españoles |
| 5.7 | gate_readability_inflesz (no-crítico) | HECHO | IA | — | Fernández Huerta, sin dependencias externas |
| 5.8 | Integración en correction.py | HECHO | IA | — | Gates críticos descartan, no-críticos flag |
| 5.9 | Patch model: gate_results + review_reason | HECHO | IA | — | JSONB + Text, migración startup |
| 5.10 | Schemas + API: pasar gate fields | HECHO | IA | — | PatchListItem + list_corrections |
| 5.11 | Frontend: barras rewrite/confidence | HECHO | IA | — | Progress bars coloreadas |
| 5.12 | Frontend: badges review_status | HECHO | IA | — | Validado/Revisión/Rechazado |
| 5.13 | Frontend: gate badges expandidos | HECHO | IA | — | Cada gate con ✓/✕ coloreado |
| 5.14 | Frontend: stats counters quality | HECHO | IA | — | Validados/Revisión/Rechazados |
| 5.15 | Actualizar REGISTRO-MVP2.md y CLAUDE.md | HECHO | IA | — | Este registro |

### Pruebas de Validación (usuario)

- [ ] `docker-compose up --build` levanta sin errores
- [ ] Subir doc con perfil → procesar → correcciones muestran badge "Validado" (verde)
- [ ] Correcciones expandidas muestran barras de reescritura y confianza
- [ ] Correcciones expandidas muestran badges de gates (✓/✕) con nombre
- [ ] Stats bar muestra contadores de Validados/Revisión/Rechazados (si aplica)
- [ ] Subir doc con perfil conservador (max_rewrite_ratio: 0.15) → correcciones agresivas rechazadas
- [ ] Subir doc con términos protegidos → verificar que no se eliminan (gate crítico)
- [ ] Si gate crítico falla → corrección LLM descartada, solo LanguageTool aplicado
- [ ] Si gate no-crítico falla → badge naranja "Revisión" con razón visible
- [ ] Logs del worker muestran distribución de gates: ok=N descartados=N revisión=N

### Log de sesión

#### 2026-03-26 — Sesión 2 (IA)
- Implementación completa Lote 5:
  - **quality_gates.py** (NUEVO): 5 gates individuales + INFLESZ + orquestador
    - `gate_not_empty` (crítico): texto corregido no puede estar vacío
    - `gate_expansion_ratio` (crítico): ratio largo corregido/original <= max_expansion_ratio del perfil
    - `gate_rewrite_ratio` (no-crítico): distancia edición normalizada con SequenceMatcher (stdlib)
    - `gate_protected_terms` (crítico): todos los términos protegidos presentes en original deben mantenerse
    - `gate_language_preserved` (no-crítico): heurístico de proporción caracteres españoles
    - `gate_readability_inflesz` (no-crítico): índice Fernández Huerta en rango objetivo del perfil
    - `compute_inflesz()`: cálculo INFLESZ implementado nativamente (sin dependencias externas)
    - `validate_correction()`: orquestador que ejecuta todos los gates
  - **correction.py**: Integración post-LLM — gates críticos descartan corrección (→ gate_rejected), no-críticos marcan manual_review
  - **Patch model**: 2 columnas nuevas: `gate_results` (JSONB), `review_reason` (Text) + migración startup
  - **Schemas**: PatchListItem y PatchDetail con gate_results y review_reason
  - **API**: list_corrections pasa gate_results y review_reason
  - **tasks_pipeline.py**: Pasa review_status, review_reason, gate_results a Patch constructor
  - **Frontend CorrectionHistory.tsx**:
    - Barras de progreso para rewrite_ratio (rojo/amarillo/verde) y confidence
    - Badges review_status: "Validado" (verde), "Revisión" (naranja), "Rechazado" (rojo)
    - Sección expandida con detalle de razón de revisión/rechazo
    - Badges por cada gate (✓ verde / ✕ rojo-naranja) con tooltip
    - Stats bar: contadores Validados, Revisión, Rechazados
  - Sin dependencias externas nuevas (INFLESZ y Levenshtein implementados con stdlib)
- **Pendiente**: Validación por usuario con docker-compose up --build
