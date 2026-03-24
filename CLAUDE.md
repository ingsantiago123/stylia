# CLAUDE.md — Corrector de Estilos (STYLIA)

## Proyecto

Sistema de corrección de estilo literario/editorial para documentos DOCX en español. Procesa documentos párrafo por párrafo a través de un pipeline de dos niveles: LanguageTool (ortografía/gramática) seguido de OpenAI GPT (estilo/claridad/fluidez), preservando formato original del documento. Actualmente en MVP 1 (Fase 1 completada). El proyecto está diseñado para escalar a múltiples fases futuras.

**Nombre del producto**: STYLIA
**Versión**: 0.1.0 (MVP 1)
**Idioma principal del código**: Python (backend), TypeScript (frontend)
**Idioma del contenido/UI**: Español

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
├── backend/                          # API FastAPI + Celery worker
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                   # Entry point FastAPI (lifespan, CORS, router)
│   │   ├── config.py                 # Pydantic Settings (todas las env vars)
│   │   ├── database.py               # SQLAlchemy async engine + session
│   │   ├── api/v1/
│   │   │   └── documents.py          # Todos los endpoints REST (517 líneas)
│   │   ├── models/                   # ORM: Document, Page, Block, Patch, Job
│   │   ├── schemas/                  # Pydantic: request/response validation
│   │   ├── services/                 # Lógica de negocio
│   │   │   ├── ingestion.py          # Etapa A: upload + DOCX→PDF
│   │   │   ├── extraction.py         # Etapa B: layout extraction (PyMuPDF)
│   │   │   ├── correction.py         # Etapa D: LanguageTool + ChatGPT
│   │   │   ├── rendering.py          # Etapa E: aplicar patches + generar output
│   │   │   └── context_accumulator.py # Gestión de contexto acumulado para LLM
│   │   ├── workers/
│   │   │   ├── celery_app.py         # Configuración Celery + Redis
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
│   │   │   ├── page.tsx              # Dashboard: upload + lista documentos
│   │   │   ├── globals.css           # Estilos globales + variables CSS
│   │   │   └── documents/[id]/
│   │   │       └── page.tsx          # Vista detalle: pipeline, correcciones, páginas
│   │   ├── components/
│   │   │   ├── DocumentUploader.tsx  # Drag-drop .docx (react-dropzone)
│   │   │   ├── DocumentList.tsx      # Grid de documentos con status
│   │   │   ├── PipelineFlow.tsx      # Visualización pipeline 6 etapas
│   │   │   ├── CorrectionHistory.tsx # Lista de correcciones con diff word-level
│   │   │   └── CorrectionFlowViewer.tsx # Flujo API ChatGPT con contexto
│   │   └── lib/
│   │       └── api.ts                # Cliente API fetch + tipos TypeScript
│
├── docker-compose.yml                # 7 servicios: postgres, redis, minio, languagetool, backend, worker, frontend
├── .env.example                      # Template de variables de entorno
├── fonts/                            # Liberation + Noto (para LibreOffice)
├── scripts/                          # start.bat, start.ps1
└── models/                           # Modelos LLM locales (futura Fase 2, .gitignored)
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
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
- LanguageTool: http://localhost:8010
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

## Arquitectura del pipeline

El procesamiento de un documento sigue 5 etapas secuenciales ejecutadas en un solo Celery task (`process_document_pipeline`):

```
ETAPA A: INGESTA        → Recibe DOCX, convierte a PDF (LibreOffice), cuenta páginas
ETAPA B: EXTRACCIÓN     → Extrae layout/texto de cada página (PyMuPDF), genera previews PNG
ETAPA D: CORRECCIÓN     → Por cada párrafo: LanguageTool → ChatGPT (con contexto acumulado)
ETAPA E: RENDERIZADO    → Aplica patches al DOCX original, genera PDF corregido
ESTADO FINAL            → completed | failed
```

**Estados del documento**: `uploaded → converting → extracting → correcting → rendering → completed/failed`
**Estados de página**: `pending → extracting → extracted → correcting → corrected → rendering → rendered/failed`

---

## Base de datos (PostgreSQL)

5 tablas principales:

| Tabla | Propósito | Campos clave |
|-------|-----------|-------------|
| `documents` | Documento maestro | id (UUID), filename, status, source_uri, pdf_uri, docx_uri, config_json, total_pages |
| `pages` | Páginas individuales | doc_id (FK), page_no, page_type, layout_uri, text_uri, preview_uri, status |
| `blocks` | Bloques de texto/imagen | page_id (FK), block_no, block_type, bbox (x0,y0,x1,y1), original_text, font_info |
| `patches` | Correcciones aplicadas | block_id (FK), version, source, original_text, corrected_text, operations_json, review_status, applied |
| `jobs` | Tracking de tareas Celery | doc_id (FK), task_type, celery_task_id, status, error |

**Nota**: En MVP las tablas se crean con `Base.metadata.create_all` en startup. No hay Alembic aún.

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

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/upload` | Sube DOCX, lanza pipeline Celery |
| GET | `/documents` | Lista documentos (skip, limit) |
| GET | `/documents/{id}` | Detalle con pages_summary |
| GET | `/documents/{id}/pages` | Lista páginas con patches_count |
| GET | `/documents/{id}/corrections` | Lista todas las correcciones |
| GET | `/documents/{id}/pages/{no}/preview` | Stream PNG preview |
| GET | `/documents/{id}/download/pdf` | Stream PDF corregido |
| GET | `/documents/{id}/download/docx` | Stream DOCX corregido |
| DELETE | `/documents/{id}` | Elimina documento |
| GET | `/documents/{id}/correction-flow` | Flujo de correcciones (debug/visualización) |
| GET | `/health` | Health check |

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
- **Polling**: 5s en home, 4s en detalle (no WebSocket)
- **Upload**: Solo .docx via react-dropzone
- **Rutas**: `/` (dashboard), `/documents/[id]` (detalle con 4 tabs)
- **Tabs detalle**: Pipeline, Correcciones (con diff word-level), Flujo API, Páginas

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
- Pipeline DOCX completo (ingest → extract → correct → render)
- LanguageTool + OpenAI gpt-4o-mini
- Dashboard con upload, lista, visualización pipeline
- Vista de correcciones con diff word-level
- Descarga PDF/DOCX corregido

**Fase 2 (MVP 2) — EN DESARROLLO**:
El rediseño completo del pipeline de corrección. Documentación detallada en:
- `mvp2.md` → Visión y diseño del pipeline editorial completo
- `IMPLEMENTACION-MVP2.md` → Guía paso a paso de implementación (fases 2A-2E)
- `CLAUDE-LOGIC.md` → Lógica interna, workflow y flujo de datos del MVP 1

Sub-fases:
- 2A: Perfiles editoriales + prompt parametrizado + correcciones categorizadas
- 2B: Etapa C (análisis editorial) + contexto jerárquico
- 2C: Router de complejidad + quality gates
- 2D: Revisión humana + track changes en DOCX
- 2E: Multi-pasada + multi-modelo + prompt caching + métricas INFLESZ

**Fases futuras (post MVP 2)**:
- Fase 3: Soporte PDF born-digital
- Fase 4: OCR para PDFs escaneados
- Fase 5: Autenticación, métricas, Kubernetes

---

## Decisiones arquitectónicas clave

1. **DOCX-first (Ruta 1)**: Se corrige directamente del DOCX, no del PDF extraído, para evitar fragmentación de párrafos y errores de capitalización
2. **Celery monolítico**: Una sola tarea para todo el pipeline en MVP; se dividirá en tareas encadenadas en fases posteriores
3. **MinIO local**: S3-compatible sin lock-in cloud, funciona idéntico con AWS S3
4. **Polling REST**: Sin WebSocket en MVP; polling simple cada 4-5 segundos
5. **Context accumulation**: Ventana deslizante de 3 párrafos corregidos para coherencia del LLM
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
