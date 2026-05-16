# CLAUDE.md — Corrector de Estilos (STYLIA)

## Proyecto

Sistema de corrección editorial para documentos DOCX en español con pipeline de análisis y corrección en múltiples etapas. Combina LanguageTool (ortografía/gramática) con OpenAI GPT (estilo/claridad/fluidez) bajo perfiles editoriales parametrizados. Incluye análisis editorial automático, extracción de estructura DOCX nativa, corrección grupal de listas y tablas, router de complejidad por párrafo, prompts dinámicos por tipo de elemento y validación multi-gate post-corrección. Preserva formato original del documento.

**Nombre del producto**: STYLIA
**Versión**: 0.3.0 (MVP 2 completado + Structural Awareness B.5/D.5)
**Idioma principal del código**: Python (backend), TypeScript (frontend)
**Idioma del contenido/UI**: Español
**Estado**: Operativo en desarrollo; pipeline con conciencia estructural activo; roadmap: fases 3+ (PDF digital, OCR, escalado)

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
│   │   │   └── documents.py          # Todos los endpoints REST
│   │   ├── models/                   # ORM: 11+ tablas
│   │   │   ├── block.py              # Block con 15 columnas nuevas (list_*, table_*, docx_location...)
│   │   │   ├── patch.py              # Patch con group_id, group_call_index, structural_role
│   │   │   ├── style_profile.py      # DocumentProfile con prompt_blocks JSONB
│   │   │   └── element_group.py      # NUEVO: ElementGroup (lista o tabla detectada en B.5)
│   │   ├── schemas/                  # Pydantic: request/response validation
│   │   ├── data/
│   │   │   └── profiles.py           # 10 perfiles editoriales predeterminados
│   │   ├── services/                 # Lógica de negocio
│   │   │   ├── ingestion.py          # Etapa A: upload + DOCX→PDF
│   │   │   ├── extraction.py         # Etapa B: layout extraction (PyMuPDF)
│   │   │   ├── extraction_docx.py    # NUEVO: Etapa B.5: estructura nativa DOCX
│   │   │   ├── group_collector.py    # NUEVO: Recolector de grupos para B.5
│   │   │   ├── analysis.py           # Etapa C: análisis editorial (secciones, glosario, clasificación)
│   │   │   ├── correction.py         # Etapa D: corrección individual + D.5 grupal
│   │   │   ├── prompt_builder.py     # Prompts parametrizados + bloques dinámicos
│   │   │   ├── complexity_router.py  # Router SKIP/CHEAP/EDITORIAL/GROUP_LIST/GROUP_TABLE
│   │   │   ├── quality_gates.py      # Validación post-corrección (5 gates + estructurales)
│   │   │   └── rendering.py          # Etapa E: aplicar patches (group-aware) + generar output
│   │   ├── workers/
│   │   │   ├── celery_app.py         # Configuración Celery + Redis
│   │   │   └── tasks_pipeline.py     # Pipeline con etapas A, B, B.5, C, D, D.5, E
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
│   │   │   └── documents/[id]/
│   │   │       └── page.tsx          # Vista detalle: 5 tabs
│   │   ├── components/
│   │   │   ├── DocumentUploader.tsx  # Drag-drop .docx (react-dropzone)
│   │   │   ├── DocumentList.tsx      # Grid de documentos con status
│   │   │   ├── CorrectionHistory.tsx # Correcciones con GroupCard (grupos colapsados)
│   │   │   ├── DiffCompareView.tsx   # Modo comparación detallado
│   │   │   ├── EditorialProfilePanel.tsx # Panel perfil con PromptBlocksPanel integrado
│   │   │   ├── PromptBlocksPanel.tsx # NUEVO: 9 toggles de bloques del prompt
│   │   │   └── StructuralTree.tsx    # NUEVO: árbol de secciones → grupos
│   │   └── lib/
│   │       └── api.ts                # Cliente API + tipos TypeScript (incluye estructurales)
│
├── scripts/
│   └── migrate_b5.py                 # NUEVO: migración idempotente B.5 (element_groups + columnas)
├── docker-compose.yml                # 11 servicios
├── .env.example
└── CLAUDE.md / CLAUDE-LOGIC.md / README.md
```

---

## Pipeline de procesamiento

El pipeline ejecuta 7 etapas secuenciales en un solo Celery task (`process_document_pipeline`):

```
ETAPA A: INGESTA           → Recibe DOCX, convierte a PDF (LibreOffice), cuenta páginas
ETAPA B: EXTRACCIÓN        → Extrae layout/texto de cada página (PyMuPDF), genera previews PNG
ETAPA B.5: STRUCT. DOCX   → Extrae estructura nativa del DOCX (listas, tablas, estilos)
                             Crea ElementGroup por cada lista/tabla detectada
                             Enriquece Block con list_id, table_id, style_name, docx_location
                             Crea blocks sintéticos para celdas sin match en PyMuPDF
ETAPA C: ANÁLISIS EDITORIAL → Inferencia de perfil, secciones, glosario, clasificación párrafos
                              Escribe paragraph_type en blocks de la DB (match por docx_location)
ETAPA D: CORRECCIÓN INDIVIDUAL → Por cada párrafo no grupal: LT → ChatGPT (con perfil + contexto)
                                  Omite párrafos cuya ubicación pertenece a un ElementGroup
ETAPA D.5: CORRECCIÓN GRUPAL   → Por cada ElementGroup: una llamada LLM con todos los ítems
                                   Lista: corrige ítems en conjunto (paralelismo, puntuación uniforme)
                                   Tabla: corrige celdas en conjunto (capitalización uniforme, roles)
ETAPA E: RENDERIZADO       → Aplica patches (grupos primero, individuales después), genera DOCX+PDF
ESTADO INTERMEDIO          → candidate_ready (listo para revisión humana)
ESTADO FINAL               → completed | failed
```

**Estados del documento (canónicos)**:
```
uploaded → converting → extracting → analyzing → correcting
→ candidate_rendering → candidate_ready → [revisión humana] → finalizing → completed/failed
```

---

## Base de datos (PostgreSQL)

11 tablas principales:

| Tabla | Propósito | Campos clave |
|-------|-----------|-------------|
| `documents` | Documento maestro | id (UUID), filename, status, source_uri, pdf_uri, docx_uri, config_json, total_pages, prompt_tokens, llm_cost_usd, review_status, final_review_notes |
| `document_profiles` | Perfil editorial | doc_id (FK unique), preset_name, register, intervention_level, audience_type/expertise, tone, genre, preserve_author_voice, max_rewrite_ratio, max_expansion_ratio, style_priorities, protected_terms, register_constraints, idiolect_protections, **prompt_blocks** (JSONB) |
| `pages` | Páginas individuales | doc_id (FK), page_no, page_type, layout_uri, text_uri, preview_uri, status |
| `blocks` | Bloques de texto/imagen | page_id (FK), block_no, block_type, bbox, original_text, font_info, **paragraph_type**, **docx_location**, **style_name**, **style_level**, **list_id**, **list_position**, **list_total**, **list_format_type**, **list_level**, **table_id**, **row_index**, **column_index**, **row_total**, **col_total**, **table_cell_role**, **element_group_id** |
| `element_groups` | **NUEVO** Grupos lista/tabla de B.5 | id (UUID), document_id (FK), group_type ('list'\|'table'), docx_native_id, item_count, metadata_json (JSONB), section_id (FK), correction_status, created_at |
| `patches` | Correcciones aplicadas | block_id (FK), version, source, original_text, corrected_text, operations_json, category, severity, explanation, confidence, route_taken, gate_results, review_reason, pass_number, model_used, rewrite_ratio, **group_id**, **group_call_index**, **group_call_id**, **structural_role** |
| `jobs` | Tracking de tareas Celery | doc_id (FK), task_type, celery_task_id, status, error |
| `llm_usage` | Costos LLM por párrafo | doc_id (FK), paragraph_index, call_type, model_used, prompt_tokens, completion_tokens, cost_usd |
| `section_summaries` | Secciones detectadas (Etapa C) | doc_id (FK), section_index, section_title, start/end_paragraph, summary_text, topic, active_terms |
| `term_registry` | Glosario de términos (Etapa C) | doc_id (FK), term, normalized_form, frequency, is_protected, decision |
| `correction_batches` | Lotes de corrección paralela | doc_id (FK), batch_no, paragraph_indices, status, results_json |

**Nota**: Las columnas en **negrita** en blocks y patches son las añadidas en v0.3.0. La migración `scripts/migrate_b5.py` las crea con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (idempotente).

---

## Análisis estructural (B.5) — detalle

### Detección de listas

`extraction_docx.py` detecta dos tipos:

**Listas nativas** (numPr en XML DOCX):
- Identificadas por el atributo `numId` en el XML del párrafo
- Agrupadas por `numId` → mismo `list_id`
- `list_format_type`: `bullet`, `decimal`, `alpha`, `roman`

**Listas manuales** (regex sobre el texto):
- Patrón: `^\s*(?:[•\-–*]|\d{1,3}[.)]\s|[a-zA-Z][.)]\s|[ivxIVX]+[.)]\s)`
- Requiere cuerpo >= 4 caracteres después del prefijo
- Excluye párrafos que parecen títulos numerados ("1. Introducción")
- Excluye secuencias donde todos los ítems tienen estilo Heading
- `list_format_type`: `decimal_dot`, `decimal_paren`, `bullet`, `alpha_dot`, `roman_dot`, `mixed`

**Filtros anti-falsos positivos**:
- `_looks_like_numbered_heading()`: texto corto + sin puntuación final + sin cuerpo largo
- Estilo DOCX contiene "heading"/"título"
- Secuencia de 3+ ítems donde todos son headings → descartada como lista

### Detección de tablas

- Itera `doc.tables` con índice
- Excluye tablas decorativas: 1×1, <2 celdas con texto real, Nx1 con <=3 filas
- `table_cell_role`: `header` (primera fila) | `total` (última fila con números) | `data`
- Cada tabla genera un `ElementGroup` con `group_type='table'`

### Sincronización Block ↔ DOCX

`_guess_location_for_block()` intenta matchear cada ítem del grupo con un Block existente en DB (extraído por PyMuPDF), usando 3 pasos:
1. Match exacto normalizado (strip + lower)
2. Match por prefijo 80 chars
3. Match por containment (texto de item contenido en block o viceversa)

Si no hay match → se crea un Block sintético (`block_type='docx_synthetic'`) con la ubicación DOCX para que la corrección grupal tenga su propio registro.

---

## Corrección grupal (D.5) — detalle

### Prompt de lista

`build_group_user_prompt_list()` en `prompt_builder.py`:
- Incluye preámbulo de perfil (registro, intervención, audiencia, prioridades)
- Contexto previo y posterior a la lista
- Patrón detectado: capitalización mayoritaria, puntuación al cierre, estructura paralela
- **Detección nativa**: pide devolver ítems SIN prefijo (el DOCX lo gestiona)
- **Detección manual**: pide preservar el prefijo EXACTAMENTE como está en cada ítem (no normalizar "2)" a "2.")
- Formato de respuesta: `{"items": [{"index": N, "action": "correct"|"skip", "corrected_text": "..."}]}`

### Prompt de tabla

`build_group_user_prompt_table()`:
- Incluye preámbulo de perfil
- Estructura de la tabla (filas × columnas, roles de celdas)
- Reglas: capitalización uniforme por columna, no modificar totales, no inventar datos
- Formato: array de celdas con `row`, `col`, `role`, `corrected_text`

### Parsing robusto

`correct_group_with_llm_sync()` en `correction.py`:
- Acepta índices int o string en la respuesta del LLM
- Deduplica ítems repetidos (keep first)
- Verifica que el índice esté en rango [0, N-1]
- Si el LLM devuelve menos ítems de los esperados → `correction_status = 'partial_failure'`

### Renderizado group-aware

`_apply_docx_patches()` en `rendering.py`:
1. Separa patches por `group_id` (grupales) vs sin `group_id` (individuales)
2. Aplica primero los grupales (ordenados por `group_call_index`)
3. Para listas manuales (`:manual` en `structural_role`): NO elimina el prefijo
4. Para listas nativas: elimina el prefijo antes de aplicar

---

## Prompts dinámicos — detalle

### Los 9 bloques configurables

Definidos en `prompt_builder.py` (`_ALL_BLOCKS`):

| Clave | Qué incluye |
|-------|-------------|
| `global_context` | ADN editorial: tema, voz dominante, registro, fingerprint estilístico |
| `profile_header` | Resumen de perfil: registro, intervención, audiencia, tono, prioridades, términos protegidos |
| `ubicacion` | Sección actual, página, vecinos, tipo siguiente párrafo |
| `structural_rules` | Reglas por tipo de elemento (título sin punto, listas con paralelismo, celdas sin totales) |
| `context_prev` | Ventana de 15 párrafos corregidos anteriores |
| `substitution_rules` | Cambios aplicados por reglas de usuario antes del LLM |
| `register_constraints` | Lenguaje inclusivo, sin anglicismos, tuteo/voseo, etc. |
| `idiolect_protections` | Patrones del autor/personajes que no deben corregirse |
| `protected_regions` | Citas, fórmulas, código, regiones marcadas sin tocar |

### Filtrado por tipo de elemento

`_BLOCKS_BY_TYPE` en `prompt_builder.py` mapea cada `paragraph_type` a los bloques que aplican:

- **`titulo`**: `global_context`, `profile_header`, `ubicacion`, `structural_rules`, `register_constraints` (sin `context_prev` — los títulos no necesitan coherencia con texto anterior)
- **`lista`**: todos excepto `substitution_rules`
- **`celda_tabla`**: todos excepto `context_prev` y `substitution_rules`
- **`cita`**: solo `global_context`, `profile_header`, `protected_regions`
- **Resto**: todos los bloques

### Cómo se activan/desactivan

1. El usuario configura `prompt_blocks` en el perfil (UI: PromptBlocksPanel con 9 toggles)
2. En `build_user_prompt()`, por cada bloque: `effective = user_flag AND type_applicable`
3. Si el bloque no aplica para el tipo → siempre OFF, aunque el usuario lo active
4. Si no hay configuración de usuario → se usa `defaultOn` del bloque (casi todos activos)

---

## API REST (Backend)

Base: `/api/v1`

### Endpoints clave

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/upload` | Sube DOCX |
| POST | `/documents/{id}/process` | Lanza pipeline |
| GET | `/documents/{id}` | Detalle documento |
| GET | `/documents/{id}/corrections` | Lista correcciones (con paragraph_type, group_id, structural_role) |
| GET | `/documents/{id}/analysis` | Resultado análisis editorial |
| GET | `/documents/{id}/structure` | **NUEVO**: Árbol secciones → grupos (ElementGroup) |
| POST | `/documents/{id}/profile` | Crea perfil editorial (incluye prompt_blocks) |
| PUT | `/documents/{id}/profile` | Actualiza perfil (incluye prompt_blocks) |
| GET | `/presets` | Lista 10 perfiles predeterminados |
| POST | `/documents/{id}/corrections/{patch_id}/review` | Aprobar/rechazar/editar patch |
| POST | `/documents/{id}/finalize` | Finaliza revisión humana |
| POST | `/documents/{id}/reopen` | Reabre para re-corrección |
| GET | `/documents/{id}/download/pdf` | Stream PDF corregido |
| GET | `/documents/{id}/download/docx` | Stream DOCX corregido |
| GET | `/costs/summary` | Resumen costos LLM |

---

## Convenciones de código

### Backend (Python)
- Funciones sync con sufijo `_sync` cuando se ejecutan en Celery (ej: `correct_docx_sync`, `extract_docx_structure_sync`)
- Logging estructurado con `logger.info/warning/error` indicando etapa y doc_id
- Rutas de corrección: `route_taken = skip | cheap | editorial | group_list | group_table`
- Etapas del pipeline: A, B, B.5, C, D, D.5, E (letras + sub-letras)
- B.5 y D.5 son NO bloqueantes (try/except que continúa si falla)
- `grouped_locations: set[str]` se pasa de B.5 a D para evitar duplicados
- Blocks sintéticos: `block_type='docx_synthetic'` para ítems DOCX sin match PyMuPDF
- `structural_role` en patches: `list_item:bullet:manual`, `table_cell:header`, etc.

### Frontend (TypeScript/React)
- Componentes como archivos individuales `.tsx` en `/components`
- API client centralizado en `lib/api.ts` con tipos TypeScript
- `PromptBlockKey` type literal con los 9 keys
- `PromptBlocksConfig = Partial<Record<PromptBlockKey, boolean>>`
- `GroupCard` component en `CorrectionHistory`: colapsa patches con mismo `group_id`
- Sin librería de componentes UI externa — todo custom con Tailwind
- Dark-only siempre (html className="dark")

---

## Variables de entorno (.env)

```
APP_NAME=StyleCorrector
DEBUG=true

DATABASE_URL=postgresql+asyncpg://stylecorrector:changeme@postgres:5432/stylecorrector
DATABASE_URL_SYNC=postgresql+psycopg2://stylecorrector:changeme@postgres:5432/stylecorrector

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=stylecorrector
MINIO_SECURE=false

LANGUAGETOOL_URL=http://languagetool:8010

OPENAI_API_KEY=<tu-key>
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=500
OPENAI_TEMPERATURE=0.3

MAX_UPLOAD_SIZE_MB=500
MAX_DOCUMENT_PAGES=1000
CONTEXT_WINDOW_SIZE=15
```

---

## Límites y restricciones configurables

| Parámetro | Valor | Ubicación |
|-----------|-------|-----------|
| Max upload | 500 MB | `config.py` → `max_upload_size_mb` |
| Max páginas | 1000 | `config.py` → `max_document_pages` |
| Max expansión texto | 110% | `config.py` → `max_overflow_ratio` |
| Min reducción fuente | 90% | `config.py` → `font_size_min_ratio` |
| Ventana contexto LLM | 15 párrafos | `config.py` → `context_window_size` |
| Celery retries | 3 | `tasks_pipeline.py` → `max_retries=3` |
| Celery timeout | 600s | `celery_app.py` → `task_time_limit` |
| Polling frontend home | 5000ms | `page.tsx` → `setInterval(5000)` |
| Polling frontend detalle | 4000ms | `documents/[id]/page.tsx` → `setInterval(4000)` |

---

## Migración B.5 (primera vez en entorno existente)

```bash
# Copiar y ejecutar migración idempotente
docker cp scripts/migrate_b5.py correctordeestilos-backend-1:/app/migrate_b5.py
docker exec correctordeestilos-backend-1 python /app/migrate_b5.py
```

La migración crea `element_groups`, añade 15 columnas a `blocks`, 4 a `patches`, y `prompt_blocks` a `document_profiles`, todo con `IF NOT EXISTS` (idempotente).

---

## Historial de versiones

| Versión | Descripción |
|---------|-------------|
| 0.1.0 | MVP 1: pipeline A→B→D→E, LT + GPT, descarga DOCX/PDF |
| 0.2.0 | MVP 2: perfiles editoriales, prompts parametrizados, análisis editorial, router de complejidad, quality gates, HITL |
| 0.3.0 | Structural Awareness: B.5 extracción DOCX nativa, ElementGroup, D.5 corrección grupal, bloques dinámicos por tipo, paragraph_type en DB, skip de grupos en D individual |

---

## Documentación complementaria

| Archivo | Contenido |
|---------|-----------|
| `CLAUDE-LOGIC.md` | Lógica interna detallada: flujo de datos, construcción de prompts, cómo se editan documentos, structural awareness completo |
| `README.md` | Documentación pública completa del producto |
| `fixestructura.md` | Plan de implementación del análisis estructural (Structural Awareness) |
