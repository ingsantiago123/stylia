# CLAUDE.md — Corrector de Estilos (STYLIA)

## Proyecto

Sistema de corrección editorial para documentos DOCX en español con pipeline de análisis y corrección en dos etapas: LanguageTool (ortografía/gramática) seguido de OpenAI GPT (estilo/claridad/fluidez). Incluye análisis editorial automático (secciones, glosario, clasificación de párrafos), router de complejidad por párrafo y validación multi-gate post-corrección. Preserva formato original del documento. MVP 2 completado (Lotes 1-5): perfiles editoriales, prompts parametrizados, análisis editorial, router de complejidad y quality gates.

**Nombre del producto**: STYLIA
**Versión**: 0.2.0 (MVP 2 completado)
**Idioma principal del código**: Python (backend), TypeScript (frontend)
**Idioma del contenido/UI**: Español
**Estado**: Operativo en desarrollo; MVP 2 lotes 1-5 implementados; roadmap: fases 3+ (PDF digital, OCR, escalado)

---

## Stack tecnológico

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Backend API | FastAPI | 0.115.6 |
| Backend Runtime | Python | 3.11 |
| ORM | SQLAlchemy (async) | 2.0.36 |
| Base de datos | PostgreSQL | 16-alpine |
| Cache / Broker | Redis | 7-alpine |
| Cola de tareas | Celery | 5.4.0 |
| Almacenamiento objetos | MinIO (S3-compatible) | latest |
| Corrector ortográfico | LanguageTool | (Java, Docker) |
| LLM (estilo) | OpenAI gpt-4o-mini | SDK 1.51.0 |
| Frontend framework | Next.js | 14.2.21 |
| Frontend UI | React + TypeScript | 18.3.1 / 5.7.2 |
| Frontend CSS | Tailwind CSS | 3.4.17 |
| Procesamiento PDF | PyMuPDF (fitz) | 1.25.1 |
| Procesamiento DOCX | python-docx | 1.1.2 |
| Conversión documentos | LibreOffice (headless) | sistema |
| Contenedores | Docker Compose | 3.8 |

---

## Estructura del proyecto

```
corrector de estilos/
├── backend/                          # API FastAPI + Celery workers
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                   # Entry point FastAPI (lifespan, CORS, router)
│   │   ├── config.py                 # Pydantic Settings (todas las env vars)
│   │   ├── database.py               # SQLAlchemy async engine + session
│   │   ├── api/v1/
│   │   │   └── documents.py          # Todos los endpoints REST (incluyendo HITL)
│   │   ├── models/                   # ORM: 10 tablas (incluye CorrectionBatch)
│   │   ├── schemas/                  # Pydantic: request/response validation
│   │   ├── data/
│   │   │   └── profiles.py           # 10 perfiles editoriales predeterminados (MVP2 Lote 1)
│   │   ├── services/                 # Lógica de negocio
│   │   │   ├── ingestion.py          # Etapa A: upload + DOCX→PDF
│   │   │   ├── extraction.py         # Etapa B: layout extraction (PyMuPDF)
│   │   │   ├── analysis.py           # Etapa C: análisis editorial (MVP2 Lote 3)
│   │   │   ├── correction.py         # Etapa D: LanguageTool + ChatGPT + quality gates
│   │   │   ├── prompt_builder.py     # MVP2 Lote 2: prompts parametrizados por perfil
│   │   │   ├── complexity_router.py  # MVP2 Lote 4: router SKIP/CHEAP/EDITORIAL
│   │   │   ├── quality_gates.py      # MVP2 Lote 5: validación post-corrección (5 gates + INFLESZ)
│   │   │   ├── rendering.py          # Etapa E: aplicar patches + generar output
│   │   │   └── context_accumulator.py # Gestión de contexto acumulado para LLM
│   │   ├── workers/
│   │   │   ├── celery_app.py         # Configuración Celery + Redis (2 colas: pipeline, batch)
│   │   │   └── tasks_pipeline.py     # Tarea monolítica del pipeline completo
│   │   └── utils/
│   │       ├── openai_client.py      # Cliente OpenAI (prompt, parse, fallback)
│   │       ├── minio_client.py       # Operaciones MinIO/S3
│   │       └── pdf_utils.py          # LibreOffice convert, PyMuPDF extract
│
├── frontend/                         # Next.js 14 (App Router)
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js                # Rewrites /api/v1/* → backend:8000
│   ├── tailwind.config.js            # Paleta: carbon/krypton/bruma/plomo
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx            # Layout global (header STYLIA, footer)
│   │   │   ├── page.tsx              # Dashboard: upload + lista documentos + selector perfil
│   │   │   ├── globals.css           # Estilos globales + variables CSS
│   │   │   ├── costs/
│   │   │   │   └── page.tsx          # Vista de costos y métricas LLM
│   │   │   └── documents/[id]/
│   │   │       └── page.tsx          # Vista detalle: 5 tabs (resume, analysis, corrections, compare, flow)
│   │   ├── components/
│   │   │   ├── DocumentUploader.tsx  # Drag-drop .docx (react-dropzone)
│   │   │   ├── DocumentList.tsx      # Grid de documentos con status
│   │   │   ├── PipelineFlow.tsx      # Visualización pipeline con etapas reales
│   │   │   ├── CorrectionHistory.tsx # Correcciones con diff, filtros, badges (MVP2 Lote 2)
│   │   │   ├── CorrectionActionPanel.tsx # Acciones de revisión humana (MVP2 Lotes 4+)
│   │   │   ├── DiffCompareView.tsx   # Modo comparación detallado
│   │   │   └── CorrectionFlowViewer.tsx # Flujo API ChatGPT con contexto jerárquico
│   │   └── lib/
│   │       └── api.ts                # Cliente API fetch + tipos TypeScript
│
├── landing/                          # Sitio landing (Next.js, puerto 3001)
│   └── src/
│
├── docker-compose.yml                # 11 servicios: postgres, pgadmin, redis, minio, 2x languagetool, 
│                                     #              nginx (LB), backend, worker-pipeline, worker-batch, frontend
├── .env.example                      # Template de variables de entorno
├── fonts/                            # Liberation + Noto (para LibreOffice)
├── scripts/                          # start.bat, start.ps1
└── models/                           # Modelos LLM locales (futura Fase 3+, .gitignored)
```

---

## Comandos esenciales

### Levantar todo el stack
```bash
docker-compose up --build
```

### Solo backend (desarrollo local sin Docker)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Solo frontend (desarrollo local)
```bash
cd frontend
npm install
npm run dev
```

### Celery worker (desarrollo local)
```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
```

### URLs de servicios (Docker)
- Frontend: http://localhost:3000
- Landing: http://localhost:3001 (desarrollo)
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
- LanguageTool (balanceado): http://localhost:8010 (nginx)
- pgAdmin: http://localhost:5050 (postgresql/admin)
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

## Arquitectura del pipeline

El procesamiento de un documento sigue 5 etapas secuenciales más 2 estados de finalización, ejecutadas en un solo Celery task (`process_document_pipeline`):

```
ETAPA A: INGESTA           → Recibe DOCX, convierte a PDF (LibreOffice), cuenta páginas
ETAPA B: EXTRACCIÓN        → Extrae layout/texto de cada página (PyMuPDF), genera previews PNG
ETAPA C: ANÁLISIS EDITORIAL → Inferencia de perfil, detección de secciones, glosario, clasificación párrafos (MVP2 Lote 3)
ETAPA D: CORRECCIÓN        → Por cada párrafo: LanguageTool → ChatGPT (con perfil + router + contexto jerárquico + quality gates)
ETAPA E: RENDERIZADO       → Aplica patches al DOCX original, genera PDF candidato
ESTADO INTERMEDIO          → candidate_ready (listo para revisión humana)
ESTADO FINAL               → completed | failed (después de revisión humana y finalize)
```

**Estados del documento (canónicos)**: 
```
uploaded → converting → extracting → analyzing → correcting 
→ candidate_rendering → candidate_ready → [revisión humana] → finalizing → completed/failed
```

**Estados legacy compatible** (sin uso activo pero soportados en código): `pending_review`, `rendering`

**Estados de página**: `pending → extracting → extracted → correcting → corrected → rendering → rendered/failed`

---

## Base de datos (PostgreSQL)

10 tablas principales:

| Tabla | Propósito | Campos clave |
|-------|-----------|-------------|
| `documents` | Documento maestro | id (UUID), filename, status, source_uri, pdf_uri, docx_uri, config_json, total_pages, prompt_tokens, llm_cost_usd, review_status, final_review_notes |
| `document_profiles` | Perfil editorial (MVP2 Lote 1) | doc_id (FK unique), preset_name, source, genre, audience, register, tone, intervention_level, protected_terms, style_priorities, max_expansion_ratio, target_inflesz_min/max |
| `pages` | Páginas individuales | doc_id (FK), page_no, page_type, layout_uri, text_uri, preview_uri, preview_corrected_uri, status |
| `blocks` | Bloques de texto/imagen | page_id (FK), block_no, block_type, bbox, original_text, font_info, paragraph_type, requires_llm, section_id |
| `patches` | Correcciones aplicadas (MVP2 Lote 2) | block_id (FK), version, source, original_text, corrected_text, operations_json, category, severity, explanation, confidence, route_taken, gate_results, review_reason, pass_number, model_used, rewrite_ratio |
| `jobs` | Tracking de tareas Celery | doc_id (FK), task_type, celery_task_id, status, error |
| `llm_usage` | Costos LLM por párrafo | doc_id (FK), paragraph_index, call_type, model_used, prompt_tokens, completion_tokens, cost_usd |
| `section_summaries` | Secciones detectadas (MVP2 Lote 3) | doc_id (FK), section_index, section_title, start/end_paragraph, summary_text, topic, active_terms |
| `term_registry` | Glosario de términos (MVP2 Lote 3) | doc_id (FK), term, normalized_form, frequency, is_protected, decision |
| `correction_batches` | Lotes de corrección paralela (MVP2 Lote 4+) | doc_id (FK), batch_no, paragraph_indices, status, results_json, created_at, completed_at |

**Nota**: En MVP las tablas se crean con `Base.metadata.create_all` en startup. No hay Alembic aún. Las columnas HITL (review_status, final_review_notes) están en Document para soporte de flujo de revisión humana.

---

## Almacenamiento MinIO (S3-compatible)

Bucket: `stylecorrector`

```
source/{doc_id}/{filename}               # DOCX original
pdf/{doc_id}/{stem}.pdf                   # PDF convertido
pages/{doc_id}/layout/{page_no}.json      # Layout estructurado por página
pages/{doc_id}/text/{page_no}.txt         # Texto plano por página
pages/{doc_id}/preview/{page_no}.png      # Preview PNG (150 DPI)
pages/{doc_id}/patch/{page_no}_v1.json    # Patches por página (Ruta 2, no activa)
docx/{doc_id}/patches_docx.json           # Todos los patches DOCX (Ruta 1)
docx/{doc_id}/{stem}_corrected.docx       # DOCX corregido final
final/{doc_id}/{stem}_corrected.pdf       # PDF corregido final
```

---

## API REST (Backend)

Base: `/api/v1`

### Flujo principal
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/upload` | Sube DOCX (status=uploaded, espera selección de perfil) |
| POST | `/documents/{id}/process` | Lanza pipeline Celery (status=uploaded → converting → ... → candidate_ready) |
| GET | `/health` | Health check |

### Perfiles editoriales
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/presets` | Lista 10 perfiles editoriales predeterminados (MVP2 Lote 1) |
| POST | `/documents/{id}/profile` | Crea perfil editorial (desde preset o custom) |
| GET | `/documents/{id}/profile` | Lee perfil editorial del documento |
| PUT | `/documents/{id}/profile` | Actualiza perfil editorial |

### Documentos y resultados
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents` | Lista documentos (skip, limit) |
| GET | `/documents/{id}` | Detalle documento (incluye review_status, estados de página) |
| GET | `/documents/{id}/pages` | Lista páginas con patches_count y preview URIs |
| GET | `/documents/{id}/corrections` | Lista todas las correcciones (MVP2 Lote 2: con category, severity, explanation) |
| DELETE | `/documents/{id}` | Elimina documento |

### Análisis editorial
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents/{id}/analysis` | Resultado análisis (secciones, glosario, distribución párrafos, perfil inferido) (MVP2 Lote 3) |
| GET | `/documents/{id}/correction-flow` | Flujo de correcciones (debug/visualización de contexto jerárquico) |
| GET | `/documents/{id}/correction-batches` | Lotes de corrección paralela (si aplica) (MVP2 Lote 4+) |

### Previews y descargas
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents/{id}/pages/{no}/preview` | Stream PNG preview página original |
| GET | `/documents/{id}/pages/{no}/preview-corrected` | Stream PNG preview página con anotaciones de correcciones |
| GET | `/documents/{id}/pages/{no}/annotations` | JSON con posiciones de correcciones en página |
| GET | `/documents/{id}/download/pdf` | Stream PDF corregido (candidate o final) |
| GET | `/documents/{id}/download/docx` | Stream DOCX corregido (candidate o final) |

### Revisión humana (HITL)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents/{id}/review-summary` | Resumen de correcciones pendientes revisión (gate_rejected, manual_review) |
| POST | `/documents/{id}/corrections/{patch_id}/review` | Acción sobre un patch: approve/reject/edit |
| POST | `/documents/{id}/finalize` | Finaliza documento (status=finalizing → completed) después de revisión |
| POST | `/documents/{id}/reopen` | Reabre documento en revisión (candidate_ready → correcting) |
| POST | `/documents/{id}/recorrect` | Relanza corrección (para patches editados manualmente) |
| POST | `/documents/{id}/rerender` | Regenera outputs DOCX/PDF desde patches |

### Costos y métricas
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/costs/summary` | Resumen de costos (total LLM, por modelo, por documento) |
| GET | `/costs/documents` | Costos agregados por documento |
| GET | `/documents/{id}/costs` | Desglose de costos por párrafo/llamada LLM |

### Tareas asíncronas (opcional)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/task-status/{task_id}` | Estado de tarea Celery (para monitoreo avanzado) |

---

## Integración LLM (OpenAI)

- **Modelo**: gpt-4o-mini (configurable en .env)
- **Temperature**: 0.3 (conservador)
- **Max tokens respuesta**: 500 (configurable)
- **Formato respuesta**: JSON forzado (`response_format={"type": "json_object"}`)
- **Fallback sin API key**: `_simulate_correction()` con reemplazos hardcoded

**Prompt principal** (en `openai_client.py`):
- System: "Eres un corrector de estilo experto en español. Siempre respondes en formato JSON válido."
- User: Instrucciones + contexto (últimos 3 párrafos corregidos) + límite de caracteres (110% original) + texto a corregir
- Respuesta esperada: `{"corrected_text": "...", "changes_made": [...], "character_count": N}`

**Validación post-respuesta**: Si el texto corregido excede max_length, se retorna el texto original sin cambios.

---

## Ruta de corrección activa: Ruta 1 (DOCX-first)

La corrección se hace directamente sobre los párrafos del DOCX (no sobre bloques del PDF) para evitar fragmentación y errores de mayúsculas. El flujo:

1. Parsear DOCX con python-docx
2. Recolectar párrafos con ubicación: `body:N`, `table:T:R:C:P`, `header:S:P`, `footer:S:P`
3. Para cada párrafo (>3 chars):
   - LanguageTool: POST a `/v2/check`, aplicar reemplazos de atrás hacia adelante
   - ChatGPT: Enviar texto post-LT + contexto (últimos 3 corregidos), max 110% largo
4. Guardar patches en MinIO como JSON
5. Renderizado: Abrir DOCX original, localizar párrafo por location string, verificar texto, aplicar corrección en `runs[0]`, vaciar resto de runs

---

## Frontend

- **Dark-only**: Siempre tema oscuro (html className="dark")
- **Paleta**: carbon (#121212), krypton (#D4FF00, acento), bruma (#F5F5F7, texto), plomo (#8E8E93, secundario)
- **State management**: React hooks locales (no Redux/Zustand)
- **Polling**: Dinámico por etapa (heartbeat con fallback fijo de 5-30s según estado del documento) (no WebSocket)
- **Upload**: Solo .docx via react-dropzone
- **Rutas principales**: 
  - `/` (dashboard: upload, lista, selector perfil)
  - `/documents/[id]` (detalle con 5 tabs)
  - `/costs` (resumen de costos)
- **Tabs detalle**: 
  1. **Resumen** (estado, progreso, perfiles inferido/seleccionado)
  2. **Análisis** (secciones, glosario, distribución párrafos) (MVP2 Lote 3)
  3. **Correcciones** (lista con diff word-level, filtros categoría/severidad/ruta, badges) (MVP2 Lote 2/4)
  4. **Comparar** (vista side-by-side original/corregido con modo diff avanzado)
  5. **Flujo API** (timeline de requests a LanguageTool y ChatGPT con contexto jerárquico)

---

## Variables de entorno (.env)

```
APP_NAME=StyleCorrector
DEBUG=true

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://stylecorrector:changeme@postgres:5432/stylecorrector
DATABASE_URL_SYNC=postgresql+psycopg2://stylecorrector:changeme@postgres:5432/stylecorrector

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=stylecorrector
MINIO_SECURE=false

# LanguageTool
LANGUAGETOOL_URL=http://languagetool:8010

# OpenAI
OPENAI_API_KEY=<tu-key>
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=500
OPENAI_TEMPERATURE=0.3

# Procesamiento
MAX_UPLOAD_SIZE_MB=500
MAX_DOCUMENT_PAGES=1000
```

---

## Convenciones de código

### Backend (Python)
- Funciones sync con sufijo `_sync` cuando se ejecutan en Celery (ej: `correct_docx_sync`, `render_docx_first_sync`)
- Logging estructurado con `logger.info/warning/error` indicando etapa y doc_id
- Rutas de corrección nombradas como "Ruta 1" (DOCX-first), "Ruta 2" (PDF digital), "Ruta 3" (OCR)
- Etapas del pipeline nombradas A, B, C, D, E (la C se agrega en MVP 2: análisis editorial)
- Archivos de servicios organizados por etapa: ingestion, extraction, correction, rendering
- Modelos SQLAlchemy usan UUID como primary key
- Schemas Pydantic separados de modelos ORM

### Frontend (TypeScript/React)
- Componentes como archivos individuales `.tsx` en `/components`
- API client centralizado en `lib/api.ts` con tipos TypeScript
- Páginas usan `"use client"` para interactividad
- Clases CSS via Tailwind utilities inline (sin CSS modules)
- Sin librería de componentes UI externa — todo custom con Tailwind
- Iconos via SVG inline (no lucide-react a pesar de estar instalado)

---

## Límites y restricciones configurables

| Parámetro | Valor | Ubicación |
|-----------|-------|-----------|
| Max upload | 500 MB | `config.py` → `max_upload_size_mb` |
| Max páginas | 1000 | `config.py` → `max_document_pages` |
| Max expansión texto | 110% | `config.py` → `max_overflow_ratio` |
| Min reducción fuente | 90% | `config.py` → `font_size_min_ratio` |
| Ventana contexto LLM | 3 párrafos | `correction.py` → `corrected_context[-3:]` |
| Celery retries | 3 | `tasks_pipeline.py` → `max_retries=3` |
| Celery timeout | 600s | `celery_app.py` → `task_time_limit` |
| Celery retry delay | 60s | `tasks_pipeline.py` → `countdown=60` |
| Polling frontend home | 5000ms | `page.tsx` → `setInterval(5000)` |
| Polling frontend detalle | 4000ms | `documents/[id]/page.tsx` → `setInterval(4000)` |

---

## Fase actual y roadmap

**Fase 1 (MVP 1) — COMPLETADA**:
- Pipeline DOCX completo (A: ingesta → B: extracción → D: corrección → E: render)
- LanguageTool + OpenAI gpt-4o-mini
- Dashboard con upload, lista, visualización pipeline
- Vista de correcciones con diff word-level
- Descarga PDF/DOCX corregido

**Fase 2 (MVP 2) — COMPLETADA (Lotes 1-5)**:
Rediseño completo del pipeline de corrección con análisis editorial, prompts parametrizados, router de complejidad y validación multi-gate. Implementación verificable por lotes.

Documentación:
- `mvp2.md` → Visión y diseño del pipeline editorial completo
- `IMPLEMENTACION-MVP2.md` → Guía paso a paso de implementación (fases 2A-2E)
- `REGISTRO-MVP2.md` → Tracking de progreso IA + humano por lote
- `CLAUDE-LOGIC.md` → Lógica interna, workflow y flujo de datos

### Lotes de implementación MVP2 (todos completados):

**Lote 1 (COMPLETADO)**: Perfiles editoriales + flujo upload/process separado + selector UI
- Tabla `document_profiles` con 10 perfiles predeterminados
- Upload ya NO lanza pipeline → usuario elige perfil → POST /process
- Frontend: ProfileSelector + ProfileEditor
- Endpoints CRUD: POST/GET/PUT /documents/{id}/profile

**Lote 2 (COMPLETADO)**: Prompts parametrizados + patches enriquecidos
- PromptBuilder: system prompt cacheable + user prompt dinámico con perfil
- Modelo Patch extendido: category, severity, explanation, confidence, rewrite_ratio, pass_number, model_used
- Frontend: CorrectionHistory con filtros categoría/severidad y badges coloreados

**Lote 3 (COMPLETADO)**: Etapa C análisis editorial + tablas section_summaries/term_registry
- Nuevo status "analyzing" en pipeline (entre extracting y correcting)
- Análisis de secciones, glosario, clasificación de párrafos (11 tipos)
- Términos protegidos se agregan al perfil antes de corrección
- Endpoint GET /documents/{id}/analysis
- Frontend: tab "Análisis" con secciones, glosario, distribución tipos

**Lote 4 (COMPLETADO)**: Router de complejidad + contexto jerárquico
- Router SKIP/CHEAP/EDITORIAL por párrafo según tipo, longitud, posición, nivel intervención
- Contexto jerárquico: section_summary + active_terms + paragraph_type en prompts
- Modelo override para modelo distinto por ruta (openai_cheap_model, openai_editorial_model)
- Patch.route_taken para tracking de ruta elegida
- Frontend: badges de ruta + contadores en stats bar

**Lote 5 (COMPLETADO)**: Quality gates + INFLESZ
- 5 gates: not_empty (crítico), expansion_ratio (crítico), protected_terms (crítico), rewrite_ratio (no-crítico), language_preserved (no-crítico), readability_inflesz (no-crítico)
- Patch.gate_results (JSONB) y Patch.review_reason para validación y trazabilidad
- Gates críticos descartan corrección (gate_rejected); no-críticos marcan manual_review
- Frontend: barras de progreso, badges de review_status, detalle de gates

**Fases futuras (post MVP 2)**:
- **Fase 3**: Soporte PDF born-digital (Ruta 2: extrae bloques del PDF, corrige y regenera overlay)
- **Fase 4**: OCR para PDFs escaneados (Ruta 3: OCR → texto → corrección → overlay)
- **Fase 5**: Autenticación, métricas, Kubernetes, escalado productivo

---

## Decisiones arquitectónicas clave

1. **DOCX-first (Ruta 1)**: Se corrige directamente del DOCX, no del PDF extraído, para evitar fragmentación de párrafos y errores de capitalización
2. **Celery monolítico**: Una sola tarea para todo el pipeline en MVP; se dividirá en tareas encadenadas en fases posteriores
3. **MinIO local**: S3-compatible sin lock-in cloud, funciona idéntico con AWS S3
4. **Polling REST**: Sin WebSocket en MVP; polling simple cada 4-5 segundos
5. **Context accumulation**: Ventana deslizante de último párrafo corregido + contexto jerárquico de sección (resumen, términos activos, tipo de párrafo) para coherencia del LLM
6. **Formato JSON forzado**: `response_format={"type": "json_object"}` para evitar respuestas malformadas del LLM
7. **Verificación pre-apply**: Antes de aplicar un patch, se verifica que el texto original del párrafo coincida con el esperado
8. **Auto-create tables**: En MVP se crean tablas en startup (sin Alembic), no apto para producción

---

## Notas para desarrollo

- Los hostnames Docker (`postgres`, `redis`, `minio`, `languagetool`, `backend`) se usan en `.env` para Docker Compose. Para desarrollo local cambiar a `localhost`.
- El frontend proxea `/api/v1/*` al backend via `next.config.js` rewrites.
- Sin API key de OpenAI, el sistema usa simulación con reemplazos hardcoded (funcional pero no útil).
- CORS configurado solo para `localhost:3000` y `127.0.0.1:3000`.
- La eliminación de documentos no limpia archivos en MinIO (TODO pendiente).
- `context_accumulator.py` contiene un servicio de simulación/demo separado del pipeline real.

---

## Documentación complementaria

| Archivo | Contenido |
|---------|-----------|
| `CLAUDE-LOGIC.md` | Lógica interna: cómo fluye la información, cómo se construyen prompts, cómo se editan documentos, flujo del usuario |
| `mvp2.md` | Visión del rediseño: pipeline editorial, perfiles, multi-pasada, quality gates |
| `IMPLEMENTACION-MVP2.md` | Guía de implementación fase por fase con archivos a crear/modificar y checkpoints de verificación |
