# STYLIA — Estado Actual del Repositorio (Abril 2026)

Sistema de corrección editorial para documentos en español con preservación de formato.

Estado real hoy:

- Entrada soportada en producción del pipeline: DOCX
- Corrección activa: LanguageTool + OpenAI (gpt-4o-mini por defecto)
- Renderizado activo: Ruta 1 (DOCX-first)
- Frontend operativo con flujo completo de carga, perfil, procesamiento, revisión y descarga

## 1) Qué hace hoy (funcionamiento real)

1. Subes un DOCX.
2. Opcionalmente seleccionas/ajustas un perfil editorial.
3. Lanzas el procesamiento con una llamada explícita al endpoint de process.
4. El pipeline ejecuta 6 etapas: A Ingesta, B Extracción, C Análisis, D Corrección, E Renderizado, cierre.
5. Revisas resultados en UI (pipeline, análisis, correcciones, diff por páginas, flujo API).
6. Descargas DOCX y PDF corregidos.

Nota:

- El endpoint de upload ya no dispara procesamiento automáticamente.
- PDF born-digital y OCR de escaneados siguen como fases futuras (Ruta 2 y Ruta 3).

## 2) Arquitectura actual

### Backend

- FastAPI + SQLAlchemy async
- Celery con 2 workers dedicados (pipeline y batch)
- PostgreSQL + Redis + MinIO
- LanguageTool balanceado con 2 instancias detrás de Nginx

### Frontend

- Next.js 14 (App Router) + React + Tailwind
- Dashboard principal en / con carga de documentos, selector de perfil y lista de procesamiento
- Detalle en /documents/[id] con pestañas de resumen, análisis, correcciones, comparar y flujo API
- Vista de costos en /costs

### Landing separada

- Proyecto independiente en carpeta landing
- Next.js en puerto 3001 (dev)

## 3) Pipeline actual (A-B-C-D-E)

```text
DOCX
  -> A) Ingesta (upload MinIO + DOCX->PDF LibreOffice)
  -> B) Extraccion (PyMuPDF: layout/text/previews)
  -> C) Analisis editorial (secciones, glosario, clasificacion)
  -> D) Correccion (LanguageTool + LLM + quality gates)
  -> E) Renderizado (aplicar patches al DOCX + generar PDF)
  -> completed | failed
```

Estados de documento (canónicos):

- `uploaded` — documento subido, esperando procesamiento
- `converting` — Etapa A: DOCX → PDF
- `extracting` — Etapa B: extracción de layout y texto
- `analyzing` — Etapa C: análisis editorial (secciones, glosario)
- `correcting` — Etapa D: corrección (LanguageTool + LLM + quality gates)
- `candidate_rendering` — Etapa E: generando candidato DOCX/PDF
- `candidate_ready` — candidato listo para revisión humana
- `finalizing` — finalizando después de revisión humana
- `completed` — completado y listo para descarga
- `failed` — error durante procesamiento

Legacy (sin uso activo):
- `pending_review` — compatibilidad anterior
- `rendering` — compatibilidad anterior

## 3.5) Flujo de revisión humana (HITL) - MVP2

Después que el pipeline completa las 5 etapas (A-B-C-D-E), el documento entra en estado `candidate_ready`:

```text
Pipeline completo (A→B→C→D→E)
  ↓
candidate_ready (documento candidato generado)
  ↓
Usuario revisa en frontend:
  - Tab "Análisis": secciones, glosario, tipos de párrafo
  - Tab "Correcciones": lista de patches con diff, categoría, severidad, ruta, confianza
  - Tab "Comparar": vista side-by-side con anotaciones
  - Aprueba/rechaza/edita patches individuales (MVP2 Lotes 4-5)
  ↓
POST /documents/{id}/finalize
  ↓
finalizing (rerender final si hay cambios, generar estadísticas)
  ↓
completed (listo para descarga)
```

Características HITL (MVP2 Lotes 4-5):
- **Quality gates** pre-HITL: 5 gates (not_empty, expansion_ratio, protected_terms, rewrite_ratio, language_preserved, inflesz)
- **Patches con anotaciones**: category, severity, explanation, confidence %, route_taken (SKIP|CHEAP|EDITORIAL)
- **Acciones en HITL**: approve/reject/edit patch individual
- **Recorrección manual**: API para editar corrección y validar manualmente

## 4) Corrección: rutas y validaciones

### Ruta activa

- Ruta 1 (DOCX-first): se corrige sobre párrafos DOCX y se regenera PDF.

### Rutas no activas aún

- Ruta 2 (PDF digital)
- Ruta 3 (OCR escaneados)

### Etapa D (corrección)

- Pass 1: LanguageTool
- Pass 2: OpenAI con respuesta JSON estructurada
- Router de complejidad por párrafo: skip | cheap | editorial
- Corrección paralela por lotes existe, pero está desactivada por defecto

### Quality gates implementados

- not_empty (crítico)
- expansion_ratio (crítico)
- protected_terms (crítico)
- rewrite_ratio (no crítico)
- language_preserved (no crítico)
- readability_inflesz (no crítico, aplica si hay rango configurado)

## 5) API REST actual

Base: /api/v1

### Flujo principal

- POST /upload
- POST /documents/{doc_id}/process

### Perfiles editoriales

- GET /presets
- POST /documents/{doc_id}/profile
- GET /documents/{doc_id}/profile
- PUT /documents/{doc_id}/profile

### Documentos y resultados

- GET /documents
- GET /documents/{doc_id}
- GET /documents/{doc_id}/pages
- GET /documents/{doc_id}/corrections
- DELETE /documents/{doc_id}

### Previews y descargas

- GET /documents/{doc_id}/pages/{page_no}/preview
- GET /documents/{doc_id}/pages/{page_no}/preview-corrected
- GET /documents/{doc_id}/pages/{page_no}/annotations
- GET /documents/{doc_id}/download/pdf
- GET /documents/{doc_id}/download/docx

### Análisis, flujo y costos

- GET /documents/{doc_id}/analysis — resultado análisis editorial (secciones, glosario, clasificación párrafos) (MVP2 Lote 3)
- GET /documents/{doc_id}/correction-flow — flujo de correcciones con contexto jerárquico
- GET /documents/{doc_id}/correction-batches — lotes de corrección paralela (si aplica) (MVP2 Lote 4+)
- GET /costs/summary — resumen de costos (total LLM, por modelo, por documento)
- GET /costs/documents — costos agregados por documento
- GET /documents/{doc_id}/costs — desglose de costos por párrafo/llamada LLM

### Revisión humana (HITL) - MVP2 Lotes 4-5

- GET /documents/{doc_id}/review-summary — resumen de correcciones pendientes revisión (gate_rejected, manual_review)
- POST /documents/{doc_id}/corrections/{patch_id}/review — acción sobre un patch: approve/reject/edit
- POST /documents/{doc_id}/finalize — finaliza documento después de revisión (status=finalizing → completed)
- POST /documents/{doc_id}/reopen — reabre documento en revisión (candidate_ready → correcting)
- POST /documents/{doc_id}/recorrect — relanza corrección para patches editados manualmente
- POST /documents/{doc_id}/rerender — regenera outputs DOCX/PDF desde patches actualizados

### Salud del servicio

- GET /health

## 6) Stack y versiones (vigentes en código)

| Capa | Tecnología | Versión |
|---|---|---|
| Backend API | FastAPI | 0.115.6 |
| Python runtime | Python | 3.11 |
| ORM | SQLAlchemy | 2.0.36 |
| Base de datos | PostgreSQL | 16-alpine |
| Broker/cola | Redis + Celery | 7-alpine + 5.4.0 |
| Almacenamiento | MinIO | latest |
| Corrector | LanguageTool (2 instancias) | latest |
| LLM | OpenAI SDK | 1.51.0 |
| Conversión DOCX->PDF | LibreOffice headless | sistema |
| Extracción PDF | PyMuPDF | 1.25.1 |
| Frontend | Next.js + React | 14.2.21 + 18.3.1 |
| UI styles | Tailwind CSS | 3.4.17 |

## 7) Servicios Docker Compose actuales

Servicios levantados por docker-compose.yml:

- postgres
- pgadmin
- redis
- minio
- languagetool-1
- languagetool-2
- languagetool (nginx balanceador)
- backend
- worker-pipeline
- worker-batch
- frontend

Puertos principales:

- Frontend: 3000
- Backend API: 8000
- LanguageTool LB: 8010
- PostgreSQL: 5432
- Redis: 6379
- MinIO API/Console: 9000/9001
- pgAdmin: 5050

## 8) Inicio rápido actualizado

### Requisitos

- Docker Desktop
- Git

### Arranque

```bash
git clone https://github.com/ingsantiago123/stylia.git
cd stylia
cp .env.example .env
docker compose up -d --build
```

### URLs

- App: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- MinIO Console: http://localhost:9001
- pgAdmin: http://localhost:5050

## 9) Flujo recomendado de uso vía API

1. Subir DOCX.

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@mi_documento.docx"
```

2. (Opcional) Crear perfil editorial (preset o custom).

```bash
curl -X POST http://localhost:8000/api/v1/documents/{DOC_ID}/profile \
  -H "Content-Type: application/json" \
  -d '{"preset_name":"novela_contemporanea"}'
```

3. Iniciar procesamiento.

```bash
curl -X POST http://localhost:8000/api/v1/documents/{DOC_ID}/process
```

4. Consultar estado.

```bash
curl http://localhost:8000/api/v1/documents/{DOC_ID}
```

5. Descargar resultados.

```bash
curl -L http://localhost:8000/api/v1/documents/{DOC_ID}/download/pdf -o salida.pdf
curl -L http://localhost:8000/api/v1/documents/{DOC_ID}/download/docx -o salida.docx
```

## 10) Variables de entorno importantes

Archivo base: .env.example

Variables clave del backend:

- DATABASE_URL
- DATABASE_URL_SYNC
- REDIS_URL
- CELERY_BROKER_URL
- CELERY_RESULT_BACKEND
- MINIO_ENDPOINT
- MINIO_ACCESS_KEY
- MINIO_SECRET_KEY
- MINIO_BUCKET
- LANGUAGETOOL_URL
- OPENAI_API_KEY
- OPENAI_MODEL
- OPENAI_CHEAP_MODEL
- OPENAI_EDITORIAL_MODEL
- OPENAI_MAX_TOKENS
- OPENAI_TEMPERATURE
- MAX_UPLOAD_SIZE_MB
- MAX_DOCUMENT_PAGES
- PARALLEL_CORRECTION_ENABLED

Nota:

- OPENAI_* no está completo en .env.example actual; si usarás LLM, agrega esas variables en tu .env.

## 11) Estructura del repositorio

```text
backend/         API FastAPI, modelos, servicios, workers
frontend/        Aplicacion web principal (operacion)
landing/         Sitio landing separado (marketing, puerto 3001)
fonts/           Fuentes locales
infra/           Infraestructura adicional
models/          Carpeta para modelos locales futuros
scripts/         Scripts de arranque
```

Documentación interna relevante:

- agents.md
- CLAUDE.md
- CLAUDE-LOGIC.md
- mvp2.md
- IMPLEMENTACION-MVP2.md
- REGISTRO-MVP2.md
- planificacion-tecnica.md
- PIPELINE-REFACTOR.md

## 12) Limitaciones actuales

- Entrada operativa del pipeline centrada en DOCX (PDF directo pendiente).
- Ruta 2 y Ruta 3 no están habilitadas en producción.
- LLM local (llama.cpp) no está integrado en flujo activo.
- Eliminación de documento no limpia todos los artefactos en MinIO de forma integral.
- El directorio backend/tests está vacío (sin suite automatizada formal aún).

## 13) Comandos de desarrollo

### Solo backend local

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Solo frontend local

```bash
cd frontend
npm install
npm run dev
```

### Workers local

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info --queues=pipeline --concurrency=4
celery -A app.workers.celery_app worker --loglevel=info --queues=batch --concurrency=6
```

### Landing local

```bash
cd landing
npm install
npm run dev
```

## 14) Estado de roadmap

- MVP1: completado
- MVP2 (Lotes 1-5): implementado en código (perfiles, prompts parametrizados, análisis, router, quality gates)
- Fase 3+: pendientes (PDF digital, OCR escaneados, escalado productivo)

## 15) Licencia

MIT
