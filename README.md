# Stylia — Corrector de Estilo con Preservación de Formato

Sistema de corrección ortográfica, gramatical y de estilo para documentos largos (DOCX/PDF de 200–600 páginas) que **preserva la maquetación visual** y funciona completamente en local.

## ¿Qué hace?

1. **Recibe** un documento DOCX o PDF
2. **Corrige** ortografía y gramática con LanguageTool (local, sin coste)
3. **Mejora** el estilo y la redacción con un LLM (ChatGPT o modelo local)
4. **Genera** el documento corregido preservando fuentes, tablas, imágenes y diseño
5. **Permite** revisión humana con vista diff antes de la salida final

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend API | FastAPI + Python 3.11 |
| Corrector determinista | LanguageTool (servidor local Java) |
| LLM de estilo | OpenAI gpt-4o-mini (o llama.cpp local) |
| Extracción PDF | PyMuPDF (`get_text("dict")`) |
| Edición DOCX | python-docx |
| Conversión DOCX→PDF | LibreOffice headless |
| Cola de tareas | Celery + Redis |
| Base de datos | PostgreSQL 16 |
| Almacenamiento | MinIO (S3-compatible) |
| Frontend | Next.js 14 + React |
| Contenedores | Docker + Docker Compose |

## Inicio rápido

### Requisitos

- Docker Desktop 4.x+
- Git

### 1. Clonar y configurar

```bash
git clone https://github.com/ingsantiago123/stylia.git
cd stylia
cp .env.example .env
```

Edita `.env` y añade tu API key de OpenAI (opcional — sin ella usará solo LanguageTool):

```env
OPENAI_API_KEY=sk-proj-...
```

### 2. Levantar servicios

```bash
docker compose up -d
```

Esto levanta: PostgreSQL, Redis, MinIO, LanguageTool, backend FastAPI y worker Celery.

### 3. Usar la API

**Subir un documento:**
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@mi_documento.docx"
```

Respuesta:
```json
{
  "id": "uuid-del-documento",
  "filename": "mi_documento.docx",
  "status": "uploaded",
  "message": "Documento recibido. Procesamiento iniciado."
}
```

**Consultar estado:**
```bash
curl http://localhost:8000/api/v1/documents/{id}
```

**Descargar el resultado:**
```bash
curl http://localhost:8000/api/v1/documents/{id}/download
```

**Documentación interactiva:** http://localhost:8000/docs

## Pipeline de procesamiento

```
DOCX/PDF → [Etapa A] Ingesta
         → [Etapa B] Extracción de layout (PyMuPDF)
         → [Etapa D] Corrección por párrafo
                       ├── LanguageTool (ortografía + gramática)
                       └── ChatGPT/LLM (estilo + claridad + fluidez)
         → [Etapa E] Renderizado (DOCX preservando formato)
         → DOCX + PDF corregidos
```

### Rutas de renderizado

| Ruta | Documento | Cómo |
|---|---|---|
| **Ruta 1** (implementada) | DOCX original | python-docx modifica párrafos → LibreOffice genera PDF |
| **Ruta 2** (próxima) | PDF born-digital | PyMuPDF redact + insert_htmlbox |
| **Ruta 3** (próxima) | PDF escaneado | OCR (docTR) + capa de texto |

## Estructura del proyecto

```
stylia/
├── backend/                # API FastAPI + lógica de negocio
│   ├── app/
│   │   ├── main.py         # Punto de entrada
│   │   ├── api/v1/         # Endpoints REST
│   │   ├── services/       # Corrección, extracción, renderizado
│   │   ├── workers/        # Tareas Celery
│   │   ├── models/         # Modelos SQLAlchemy
│   │   └── utils/          # MinIO, OpenAI, PyMuPDF helpers
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # UI Next.js (en desarrollo)
├── infra/                  # docker-compose, nginx, Kubernetes
├── scripts/                # Setup y descarga de modelos
├── fonts/                  # Repositorio de fuentes
├── models/                 # Modelos LLM locales (no versionados)
├── docker-compose.yml
└── .env.example
```

## Configuración

Todas las variables están en `.env` (copia de `.env.example`):

```env
# Base de datos
DATABASE_URL=postgresql+asyncpg://stylia:stylia@postgres:5432/stylia

# Redis
CELERY_BROKER_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123

# LanguageTool
LANGUAGETOOL_URL=http://languagetool:8010

# OpenAI (opcional)
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=1000
OPENAI_TEMPERATURE=0.3
```

## Compartir con amigos (ngrok)

Puedes exponer la aplicación temporalmente a internet para que alguien externo la pruebe sin necesidad de despliegue en servidor.

### Requisitos previos

1. Crear cuenta gratuita en [ngrok.com](https://ngrok.com) y obtener el auth token en el [dashboard](https://dashboard.ngrok.com/get-started/your-authtoken).
2. Descargar ngrok desde [ngrok.com/download](https://ngrok.com/download) (versión ≥ 3.20).

### Pasos

**1. Instala ngrok (solo la primera vez):**
```powershell
# Windows — descarga el ZIP y extrae ngrok.exe a una carpeta de tu elección
# O usa winget (puede instalar versión antigua; si falla, descarga manualmente):
winget install ngrok.ngrok
```

**2. Configura tu auth token (solo la primera vez):**
```powershell
ngrok config add-authtoken TU_TOKEN_DE_NGROK
```

**3. Levanta los servicios:**
```powershell
docker compose up -d
```

**4. Arranca el túnel:**
```powershell
ngrok http 3000
```

Ngrok mostrará en la terminal una línea como:
```
Forwarding  https://xxxx-xxxx.ngrok-free.app -> http://localhost:3000
```

**5. Comparte esa URL** con tus amigos. Al entrar verán una pantalla de ngrok con un botón "Visit Site" (es normal en el plan gratuito, solo hay que hacer clic una vez).

### Notas importantes

- La URL cambia cada vez que reinicias ngrok (plan gratuito). Si la quieres fija, necesitas plan de pago.
- El túnel solo funciona mientras ngrok esté corriendo en tu máquina. Al cerrar la terminal, la URL deja de funcionar.
- Si `ngrok` no se reconoce tras la instalación, abre una **nueva terminal** (el PATH se actualiza solo al reiniciar la sesión).
- La app enruta todas las llamadas API internamente (`/api/v1/*` → backend), por lo que solo necesitas exponer el puerto 3000.

### Fix del worker tras cada reinicio

Hasta que se reconstruya la imagen Docker por completo, el worker pierde el paquete `openai` al reiniciar. Ejecuta esto cada vez que levantes los servicios:

```powershell
docker exec correctordeestilos-worker-1 pip install openai==1.51.0 httpx==0.27.2 -q
docker restart correctordeestilos-worker-1
```

---

## Fases de implementación

- [x] **Fase 1** — Pipeline mínimo: DOCX entra, se corrige, sale DOCX+PDF corregido
- [x] **Fase 1** — Integración LanguageTool + ChatGPT (gpt-4o-mini)
- [x] **Fase 1** — Sin bug de mayúsculas aleatorias (corrección párrafo a párrafo)
- [ ] **Fase 2** — Vista diff lado a lado + revisión humana
- [ ] **Fase 2** — LLM local con llama.cpp (Qwen2.5-7B)
- [ ] **Fase 3** — Soporte PDF born-digital (Ruta 2)
- [ ] **Fase 4** — OCR para PDFs escaneados (docTR)
- [ ] **Fase 5** — Autenticación, métricas, Kubernetes

## Desarrollo local

```bash
# Solo backend (sin Docker para desarrollo rápido)
docker compose up -d postgres redis minio languagetool
cd backend && uvicorn app.main:app --reload

# Worker Celery
cd backend && celery -A app.workers.celery_app worker --loglevel=info

# Tests
cd backend && pytest tests/ -v
```

## Licencia

MIT
