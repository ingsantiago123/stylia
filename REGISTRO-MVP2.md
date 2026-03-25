# REGISTRO MVP2 — Tracking IA + Humano

## Resumen de Lotes

| Lote | Nombre | Estado | Fecha inicio | Fecha validación |
|------|--------|--------|-------------|-----------------|
| 1 | Perfiles Editoriales + Flujo Separado | IA COMPLETADO | 2026-03-24 | Pendiente validacion |
| 2 | Prompt Parametrizado + Patches Enriquecidos | IA COMPLETADO | 2026-03-24 | Pendiente validacion |
| 3 | Etapa C: Análisis Editorial | PENDIENTE | — | — |
| 4 | Contexto Jerárquico + Router Complejidad | PENDIENTE | — | — |
| 5 | Quality Gates + Métricas | PENDIENTE | — | — |

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
*(Se completará cuando inicie este lote)*

---

## LOTE 4 — Contexto Jerárquico + Router Complejidad
*(Se completará cuando inicie este lote)*

---

## LOTE 5 — Quality Gates + Métricas
*(Se completará cuando inicie este lote)*
