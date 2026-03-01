# 🧭 Agents.md — Guía maestra para el asistente de IA

> **Proyecto:** Sistema de corrección de estilo con preservación de formato
> **Documento fuente:** `idea de proyecto.tex` (arquitectura conceptual)
> **Planificación técnica:** `planificacion-tecnica.md` (especificaciones detalladas)

---

## Propósito de este archivo

Este archivo es la **brújula del proyecto**. Le dice al asistente de IA:

1. Qué es el proyecto y cuál es el objetivo final.
2. Dónde encontrar cada pieza de información.
3. En qué orden implementar.
4. Qué decisiones técnicas ya están tomadas.
5. Qué restricciones respetar.

**Lee siempre este archivo primero antes de hacer cualquier cambio o implementación.**

---

## 1. Visión del proyecto

Un sistema que recibe documentos largos (PDF o DOCX, 200–600 páginas) con diagramación compleja (tablas, imágenes, columnas) y:

- Corrige ortografía, gramática y estilo de forma automatizada.
- **Preserva la maquetación visual** página por página (imágenes, tablas, diseño).
- Ejecuta todo localmente (OCR, LLM, corrector) para minimizar costes y proteger privacidad.
- Permite revisión humana con vista diff lado a lado antes de generar la salida final.

---

## 2. Mapa de archivos del proyecto

```
corrector-de-estilos/
│
├── agents.md                    ← ESTE ARCHIVO (léelo primero)
├── planificacion-tecnica.md     ← Especificaciones técnicas detalladas
├── idea de proyecto.tex         ← Documento conceptual original (LaTeX)
│
├── backend/                     ← API FastAPI + lógica de negocio
│   ├── app/
│   │   ├── main.py              ← Punto de entrada FastAPI
│   │   ├── config.py            ← Settings con Pydantic
│   │   ├── models/              ← Modelos SQLAlchemy (documents, pages, patches...)
│   │   ├── schemas/             ← Schemas Pydantic (request/response)
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── documents.py ← Endpoints de documentos
│   │   │       ├── pages.py     ← Endpoints de páginas
│   │   │       └── patches.py   ← Endpoints de parches/correcciones
│   │   ├── services/            ← Lógica de negocio
│   │   │   ├── ingestion.py     ← Etapa A: subida, conversión, conteo
│   │   │   ├── extraction.py    ← Etapa B: extracción de layout
│   │   │   ├── context.py       ← Etapa C: snapshots de contexto
│   │   │   ├── correction.py    ← Etapa D: LanguageTool + LLM
│   │   │   ├── rendering.py     ← Etapa E: renderizado final
│   │   │   ├── font_manager.py  ← Gestión de fuentes (mapeo, extracción, fallback)
│   │   │   └── classifier.py    ← Clasificador de tipo de documento/página
│   │   ├── workers/             ← Tareas Celery
│   │   │   ├── celery_app.py
│   │   │   ├── tasks_ingest.py
│   │   │   ├── tasks_extract.py
│   │   │   ├── tasks_correct.py
│   │   │   └── tasks_render.py
│   │   └── utils/
│   │       ├── pdf_utils.py     ← Helpers PyMuPDF
│   │       ├── minio_client.py  ← Cliente MinIO
│   │       ├── diff_utils.py    ← Comparación pixel a pixel
│   │       └── llm_client.py    ← Cliente para llama.cpp/vLLM
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                    ← UI Next.js / React
│   ├── src/
│   │   ├── app/                 ← App Router de Next.js
│   │   ├── components/
│   │   │   ├── DocumentUploader.tsx
│   │   │   ├── DiffViewer.tsx   ← Vista lado a lado original vs corregido
│   │   │   ├── PageNavigator.tsx
│   │   │   ├── PatchReviewPanel.tsx
│   │   │   └── SettingsPanel.tsx
│   │   └── lib/
│   │       └── api.ts           ← Cliente API
│   ├── package.json
│   └── Dockerfile
│
├── infra/                       ← Infraestructura y despliegue
│   ├── docker-compose.yml       ← Despliegue local (MVP)
│   ├── docker-compose.gpu.yml   ← Override con acceso a GPU
│   ├── k8s/                     ← Manifiestos Kubernetes (fase posterior)
│   ├── nginx.conf               ← Proxy reverso
│   └── .env.example
│
├── models/                      ← Modelos de IA descargados
│   └── README.md                ← Instrucciones para descargar modelos
│
├── fonts/                       ← Repositorio de fuentes del sistema
│   ├── liberation/
│   ├── noto/
│   └── font_map.json            ← Mapeo PostScript → archivo TTF/OTF
│
└── scripts/
    ├── setup_dev.sh             ← Script de setup para desarrollo
    ├── download_models.sh       ← Descarga modelos LLM y OCR
    └── seed_fonts.sh            ← Copia fuentes al repositorio
```

> **IMPORTANTE**: Esta estructura es el objetivo final. Se implementa por fases (ver sección 6).

---

## 3. Decisiones técnicas ya tomadas

Estas decisiones están **cerradas**. No las cambies salvo que el usuario lo pida explícitamente.

| Decisión | Elección | Razón |
|---|---|---|
| Lenguaje backend | Python 3.11+ | Ecosistema PDF/ML más maduro |
| Framework API | FastAPI | Async, tipado, documentación automática |
| Framework frontend | Next.js 14+ (App Router) + React | SSR, componentes modernos |
| Base de datos | PostgreSQL 16+ | Robustez, JSON nativo, extensiones |
| Cola de tareas | Celery + Redis | Distribución de trabajos pesados |
| Almacenamiento objetos | MinIO (S3-compatible) | Local, alto rendimiento, escalable |
| Extracción PDF digital | PyMuPDF (fitz) | `get_text("dict")` a nivel span |
| OCR escaneados | docTR (Mindee) | Pipeline 2 etapas, local, GPU |
| Layout complejo | Layout Parser | Deep learning para estructura de página |
| Conversión DOCX→PDF | LibreOffice headless | `soffice --convert-to pdf` |
| Corrector determinista | LanguageTool (servidor local, Java) | Ortografía + gramática + estilo |
| LLM local | llama.cpp (servidor HTTP) | CPU+GPU, cuantización 4-8 bits |
| Modelo LLM sugerido | Qwen2.5-7B-Instruct (Q4_K_M) | Buen español, cabe en 8GB VRAM |
| Containerización | Docker + Docker Compose (MVP) | Simplicidad para fase inicial |
| Monitorización | Prometheus + Grafana (fase posterior) | Métricas de workers y tiempos |

---

## 4. Las tres rutas de renderizado

El sistema **clasifica cada página** y elige la ruta óptima. Esto es CRÍTICO.

### Ruta 1: DOCX-first
- **Cuándo:** El documento original es DOCX.
- **Cómo:** `python-docx` modifica texto preservando runs/formato → LibreOffice genera PDF.
- **Implementar en:** `backend/app/services/rendering.py` → `render_docx_first()`

### Ruta 2: Redact + insert_htmlbox
- **Cuándo:** PDF born-digital con texto vectorial.
- **Cómo:** PyMuPDF `get_text("dict")` → corrección → `add_redact_annot` + `apply_redactions(images=0, graphics=0)` → `insert_htmlbox` con CSS + fuentes.
- **Implementar en:** `backend/app/services/rendering.py` → `render_pdf_digital()`

### Ruta 3: Imagen + capa de texto
- **Cuándo:** PDF escaneado (sin texto vectorial).
- **Cómo:** OCR → corrección → pintar sobre imagen → nueva capa de texto invisible.
- **Implementar en:** `backend/app/services/rendering.py` → `render_pdf_scanned()`

**El clasificador** (`backend/app/services/classifier.py`) decide la ruta por página analizando si `page.get_text()` devuelve contenido significativo o no.

---

## 5. Pipeline de procesamiento (5 etapas)

```
Etapa A (Ingesta) → Etapa B (Extracción) → Etapa C (Contexto) → Etapa D (Corrección) → Etapa E (Renderizado)
```

### Etapa A: Ingesta
- **Archivo:** `services/ingestion.py`, `workers/tasks_ingest.py`
- **Qué hace:** Recibe documento → guarda en MinIO `source/` → si es DOCX convierte a PDF con LibreOffice → guarda en `pdf/` → cuenta páginas → crea registros en DB.
- **Salida:** Registro `documents` + registros `pages` con estado `pending`.

### Etapa B: Extracción de layout
- **Archivo:** `services/extraction.py`, `workers/tasks_extract.py`
- **Qué hace:** Por cada página: clasifica (digital/escaneado) → extrae bloques/spans con posición, fuente, tamaño, color → extrae imágenes → genera preview.
- **Herramientas:** PyMuPDF `get_text("dict")` para digitales, docTR para escaneados, Layout Parser para layouts complejos.
- **Salida:** JSON layout en MinIO `pages/layout/`, texto plano en `pages/text/`, preview en `pages/preview/`.

### Etapa C: Construcción de contexto
- **Archivo:** `services/context.py`
- **Qué hace:** Cada N páginas (ej: 10), crea snapshot con glosario acumulado, entidades, preferencias de estilo, resumen narrativo.
- **Salida:** Registro `context_snapshots` + JSON en MinIO.

### Etapa D: Corrección por página
- **Archivo:** `services/correction.py`, `workers/tasks_correct.py`
- **Qué hace por bloque:**
  1. LanguageTool → corrección determinista (ortografía, gramática).
  2. LLM local → parches de estilo como JSON estructurado.
  3. Validar cabida (medir ancho corregido vs bbox original).
  4. Post-chequeo con LanguageTool.
- **Salida:** Registro `patches` + JSON de parches en MinIO `pages/patch/`.

### Etapa E: Renderizado
- **Archivo:** `services/rendering.py`, `workers/tasks_render.py`
- **Qué hace:** Aplica la ruta correcta (1, 2 o 3) por página → valida con diff pixel → ensambla PDF final.
- **Salida:** Páginas en MinIO `pages/output/` → PDF final en `final/`.

---

## 6. Fases de implementación (ORDEN OBLIGATORIO)

### Fase 1 — Esqueleto y flujo mínimo (Semanas 1-3)
**Objetivo:** Un documento DOCX entra, se corrige ortografía, sale un PDF.

1. Crear estructura de carpetas `backend/` y `frontend/`.
2. Configurar `docker-compose.yml` con: PostgreSQL, Redis, MinIO, LanguageTool.
3. Implementar modelos SQLAlchemy (`documents`, `pages`, `patches`, `jobs`).
4. Implementar Etapa A (ingesta) solo para DOCX → conversión a PDF.
5. Implementar Etapa B (extracción) solo con PyMuPDF `get_text("dict")`.
6. Implementar Etapa D (corrección) solo con LanguageTool (sin LLM).
7. Implementar Etapa E (renderizado) Ruta 1 (DOCX-first con python-docx).
8. Frontend mínimo: subir documento + descargar resultado.

### Fase 2 — LLM local y vista diff (Semanas 4-6)
**Objetivo:** Añadir corrección de estilo con LLM y revisión humana.

1. Integrar llama.cpp como servidor HTTP en docker-compose.
2. Implementar `llm_client.py` con constrained decoding (GBNF grammar para JSON).
3. Añadir corrección LLM a Etapa D.
4. Implementar Etapa C (snapshots de contexto).
5. Frontend: vista diff lado a lado, aceptar/rechazar correcciones.

### Fase 3 — PDFs born-digital (Semanas 7-9)
**Objetivo:** Corregir PDFs digitales sin el DOCX fuente.

1. Implementar `font_manager.py` (mapeo de fuentes, extracción, fallback).
2. Implementar Ruta 2 (Redact + insert_htmlbox).
3. Implementar `classifier.py` para decidir ruta por página.
4. Implementar `diff_utils.py` (validación pixel a pixel).
5. Poblar `fonts/font_map.json` con mapeos comunes.

### Fase 4 — PDFs escaneados + OCR (Semanas 10-12)
**Objetivo:** Soportar documentos escaneados.

1. Integrar docTR en docker-compose (con GPU).
2. Implementar Ruta 3 (imagen + capa de texto).
3. Integrar Layout Parser para layouts complejos.
4. Manejar documentos mixtos (páginas digitales + escaneadas).

### Fase 5 — Producción y escalado (Semanas 13+)
**Objetivo:** Robustez, monitorización, escalado.

1. Añadir Prometheus + Grafana.
2. Migrar a Kubernetes si hay necesidad de escalado.
3. Añadir autenticación y roles.
4. Testing de regresión visual automatizado.
5. Optimización de rendimiento (paralelismo por ventana, caché).

---

## 7. Reglas para el asistente de IA

### Al implementar código:
- **Siempre consultar `planificacion-tecnica.md`** para especificaciones detalladas antes de escribir código.
- **Respetar la estructura de carpetas** definida en la sección 2.
- **Respetar las decisiones técnicas** de la sección 3.
- **Implementar en el orden de fases** de la sección 6. No saltar fases.
- **Cada servicio debe ser testeable** de forma aislada con datos mock.
- **Usar tipado estricto** en Python (type hints en todas las funciones).
- **Los workers Celery** deben ser idempotentes y resistentes a reintentos.

### Al tomar decisiones:
- Si hay ambigüedad, elegir la opción más simple que funcione para el MVP.
- Si algo no está especificado, preguntar antes de asumir.
- Si un cambio afecta la arquitectura general, validar contra este archivo primero.
- Preferir librerías ya listadas en las decisiones técnicas sobre alternativas.

### Al generar prompts para el LLM de corrección:
- El LLM debe devolver **JSON estructurado**, nunca texto libre.
- El prompt debe incluir el **contexto acumulado** (glosario, estilo, entidades).
- Se debe especificar un **límite de longitud** (máx 110% caracteres del original).
- Se debe instruir al LLM para que **no cambie el significado**, solo el estilo.

### Archivos de referencia:
| Qué necesitas saber | Dónde mirar |
|---|---|
| Visión general del proyecto | `idea de proyecto.tex` |
| Especificaciones técnicas detalladas | `planificacion-tecnica.md` |
| Guía de implementación y orden | `agents.md` (este archivo) |
| Estructura de la base de datos | `planificacion-tecnica.md` § Modelo de datos |
| Estrategia de renderizado | `planificacion-tecnica.md` § Rutas de renderizado |
| Dependencias y versiones | `planificacion-tecnica.md` § Stack tecnológico |
| Formato de parches del LLM | `planificacion-tecnica.md` § Schema de parches |

---

## 8. Comandos útiles de desarrollo

```bash
# Levantar todos los servicios
docker compose up -d

# Solo backend + dependencias
docker compose up -d postgres redis minio languagetool
cd backend && uvicorn app.main:app --reload

# Solo frontend
cd frontend && npm run dev

# Ejecutar workers Celery
cd backend && celery -A app.workers.celery_app worker --loglevel=info

# Tests
cd backend && pytest tests/ -v

# Descargar modelo LLM
./scripts/download_models.sh qwen2.5-7b-q4km
```

---

## 9. Checklist de validación por fase

### Fase 1 ✅ cuando:
- [ ] Docker compose levanta PostgreSQL, Redis, MinIO, LanguageTool sin errores.
- [ ] Se puede subir un DOCX vía API y se guarda en MinIO.
- [ ] La conversión DOCX→PDF funciona con LibreOffice headless.
- [ ] Se extraen bloques de texto con posición del PDF.
- [ ] LanguageTool corrige al menos errores ortográficos simples.
- [ ] Se genera un DOCX corregido con python-docx preservando formato básico.
- [ ] Se genera un PDF final desde el DOCX corregido.
- [ ] El frontend permite subir y descargar.

### Fase 2 ✅ cuando:
- [ ] llama.cpp servidor responde en docker compose.
- [ ] El LLM devuelve parches JSON válidos para texto en español.
- [ ] El contexto acumulado funciona para ventanas de 10 páginas.
- [ ] El frontend muestra diff lado a lado con resaltado de cambios.
- [ ] Se pueden aceptar/rechazar correcciones individuales.

### Fase 3 ✅ cuando:
- [ ] El clasificador distingue páginas digitales de escaneadas.
- [ ] Redact + insert_htmlbox funciona sin dañar imágenes ni gráficos.
- [ ] El font_manager mapea fuentes comunes correctamente.
- [ ] La validación pixel a pixel detecta regresiones fuera del texto.
- [ ] Un PDF de 50 páginas se procesa sin corrupción visual.

### Fase 4 ✅ cuando:
- [ ] docTR reconoce texto en páginas escaneadas con >90% precisión.
- [ ] La Ruta 3 genera PDFs con imagen corregida + texto buscable.
- [ ] Documentos mixtos se procesan con la ruta correcta por página.

### Fase 5 ✅ cuando:
- [ ] Prometheus recoge métricas de todos los workers.
- [ ] Autenticación JWT funciona con roles.
- [ ] Un libro de 300 páginas se procesa en <2 horas.
