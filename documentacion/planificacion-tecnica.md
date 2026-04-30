# Planificación técnica — Sistema de corrección de estilo

> Versión: 1.0  
> Fecha: 2026-03-01  
> Referencia: `idea de proyecto.tex`, `agents.md`

---

## Índice

1. [Stack tecnológico y versiones](#1-stack-tecnológico-y-versiones)
2. [Requisitos de hardware](#2-requisitos-de-hardware)
3. [Modelo de datos (PostgreSQL)](#3-modelo-de-datos-postgresql)
4. [Almacenamiento de objetos (MinIO)](#4-almacenamiento-de-objetos-minio)
5. [Rutas de renderizado — Estrategia de fidelidad](#5-rutas-de-renderizado--estrategia-de-fidelidad)
6. [Gestión de fuentes](#6-gestión-de-fuentes)
7. [Corrección determinista (LanguageTool)](#7-corrección-determinista-languagetool)
8. [Corrección LLM — Schema de parches](#8-corrección-llm--schema-de-parches)
9. [Extracción de layout](#9-extracción-de-layout)
10. [OCR para escaneados](#10-ocr-para-escaneados)
11. [Pipeline Celery — Tareas y flujos](#11-pipeline-celery--tareas-y-flujos)
12. [API REST (FastAPI)](#12-api-rest-fastapi)
13. [Frontend (Next.js)](#13-frontend-nextjs)
14. [Docker Compose — Servicios](#14-docker-compose--servicios)
15. [Validación visual automatizada](#15-validación-visual-automatizada)
16. [Seguridad](#16-seguridad)
17. [Variables de entorno](#17-variables-de-entorno)

---

## 1. Stack tecnológico y versiones

### Backend

| Paquete | Versión mínima | Propósito |
|---|---|---|
| Python | 3.11+ | Runtime |
| FastAPI | 0.110+ | Framework API |
| Uvicorn | 0.29+ | Servidor ASGI |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.13+ | Migraciones de BD |
| Pydantic | 2.6+ | Validación de datos |
| Celery | 5.3+ | Cola de tareas distribuida |
| Redis (py) | 5.0+ | Cliente Redis para Celery y caché |
| PyMuPDF (fitz) | 1.24+ | Extracción y manipulación de PDFs |
| python-docx | 1.1+ | Manipulación de DOCX |
| language_tool_python | 2.8+ | Cliente LanguageTool |
| Pillow | 10.2+ | Manipulación de imágenes |
| boto3 / minio | 7.2+ | Cliente MinIO/S3 |
| httpx | 0.27+ | Cliente HTTP async (para llama.cpp API) |
| python-multipart | 0.0.9+ | Upload de archivos en FastAPI |
| psycopg2-binary | 2.9+ | Driver PostgreSQL |

### OCR y Layout (Fase 4)

| Paquete | Versión | Propósito |
|---|---|---|
| python-doctr | 0.9+ | OCR de dos etapas (detección + reconocimiento) |
| layoutparser | 0.3+ | Detección de estructura con deep learning |
| torch | 2.2+ | Backend para docTR y Layout Parser |
| torchvision | 0.17+ | Modelos de visión |
| opencv-python | 4.9+ | Procesamiento de imagen para Ruta 3 |

### Frontend

| Paquete | Versión | Propósito |
|---|---|---|
| Node.js | 20 LTS+ | Runtime |
| Next.js | 14.2+ | Framework React con SSR |
| React | 18.3+ | UI |
| TypeScript | 5.4+ | Tipado |
| Tailwind CSS | 3.4+ | Estilos |
| react-pdf | 9.0+ | Visor de PDF embebido |
| diff | 5.2+ (npm) | Cálculo de diferencias de texto |
| axios / fetch | - | Cliente HTTP |
| zustand | 4.5+ | Estado global |

### Infraestructura

| Servicio | Imagen Docker | Propósito |
|---|---|---|
| PostgreSQL | `postgres:16-alpine` | Base de datos relacional |
| Redis | `redis:7-alpine` | Broker Celery + caché |
| MinIO | `minio/minio:latest` | Almacenamiento S3-compatible |
| LanguageTool | `erikvl87/languagetool:latest` | Corrector ortográfico/gramatical |
| llama.cpp | `ghcr.io/ggerganov/llama.cpp:server` | Servidor LLM local |
| LibreOffice | (incluido en imagen backend) | Conversión DOCX→PDF |
| Nginx | `nginx:alpine` | Proxy reverso |

---

## 2. Requisitos de hardware

### Desarrollo (mínimo)

| Recurso | Mínimo | Recomendado |
|---|---|---|
| CPU | 4 cores | 8 cores |
| RAM | 16 GB | 32 GB |
| GPU | No requerida (CPU mode) | NVIDIA con 8 GB VRAM |
| Disco | 50 GB libres | 100 GB SSD |

### Producción

| Recurso | Mínimo | Recomendado |
|---|---|---|
| CPU | 8 cores | 16 cores |
| RAM | 32 GB | 64 GB |
| GPU | NVIDIA T4 (16 GB) | NVIDIA A10 (24 GB) |
| Disco | 200 GB SSD | 500 GB NVMe |

### Consumo estimado por componente

| Componente | RAM | GPU VRAM | CPU |
|---|---|---|---|
| LanguageTool server | 1.5-2 GB | — | 1 core |
| llama.cpp (Qwen2.5-7B Q4_K_M) | 2 GB | 6 GB | 2 cores |
| llama.cpp (sin GPU, CPU only) | 8 GB | — | 4 cores |
| docTR (GPU) | 2 GB | 2 GB | 1 core |
| docTR (CPU) | 4 GB | — | 2 cores |
| PostgreSQL | 0.5-1 GB | — | 1 core |
| Redis | 0.2-0.5 GB | — | 0.5 core |
| MinIO | 0.5-1 GB | — | 1 core |
| Celery worker (por worker) | 0.5-1 GB | — | 1 core |
| FastAPI | 0.3-0.5 GB | — | 1 core |

---

## 3. Modelo de datos (PostgreSQL)

### Tabla: `documents`

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        VARCHAR(512) NOT NULL,
    original_format VARCHAR(10) NOT NULL,          -- 'pdf', 'docx'
    source_uri      VARCHAR(1024) NOT NULL,         -- ruta en MinIO: source/{id}/{filename}
    pdf_uri         VARCHAR(1024),                  -- ruta en MinIO: pdf/{id}/{filename}.pdf
    docx_uri        VARCHAR(1024),                  -- ruta si el original era DOCX
    total_pages     INTEGER,
    status          VARCHAR(20) NOT NULL DEFAULT 'uploaded',
                    -- uploaded → converting → extracting → correcting → rendering → completed → failed
    config_json     JSONB NOT NULL DEFAULT '{}',    -- reglas de estilo, idioma, glosarios
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_status ON documents(status);
```

### Tabla: `pages`

```sql
CREATE TABLE pages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no         INTEGER NOT NULL,               -- 1-indexed
    page_type       VARCHAR(20) NOT NULL DEFAULT 'unknown',
                    -- 'digital', 'scanned', 'mixed', 'unknown'
    render_route    VARCHAR(20),                     -- 'docx_first', 'redact_htmlbox', 'image_overlay'
    layout_uri      VARCHAR(1024),                  -- MinIO: pages/{doc_id}/layout/{page_no}.json
    text_uri        VARCHAR(1024),                  -- MinIO: pages/{doc_id}/text/{page_no}.txt
    preview_uri     VARCHAR(1024),                  -- MinIO: pages/{doc_id}/preview/{page_no}.png
    output_uri      VARCHAR(1024),                  -- MinIO: pages/{doc_id}/output/{page_no}.pdf
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending → extracting → extracted → correcting → corrected → rendering → rendered → failed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(doc_id, page_no)
);

CREATE INDEX idx_pages_doc_status ON pages(doc_id, status);
```

### Tabla: `blocks`

```sql
CREATE TABLE blocks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id         UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    block_no        INTEGER NOT NULL,               -- orden dentro de la página
    block_type      VARCHAR(20) NOT NULL,           -- 'text', 'image', 'table', 'header', 'footer'
    bbox_x0         REAL NOT NULL,
    bbox_y0         REAL NOT NULL,
    bbox_x1         REAL NOT NULL,
    bbox_y1         REAL NOT NULL,
    original_text   TEXT,
    font_info       JSONB,                          -- [{"font": "Arial-BoldMT", "size": 12, "color": "#000000", "flags": 20}]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(page_id, block_no)
);

CREATE INDEX idx_blocks_page ON blocks(page_id);
```

### Tabla: `patches`

```sql
CREATE TABLE patches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_id        UUID NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL DEFAULT 1,
    source          VARCHAR(20) NOT NULL,           -- 'languagetool', 'llm', 'manual'
    original_text   TEXT NOT NULL,
    corrected_text  TEXT NOT NULL,
    operations_json JSONB NOT NULL,                 -- lista de operaciones (ver Schema de parches)
    qa_score        REAL,                           -- 0.0 a 1.0
    overflow_flag   BOOLEAN NOT NULL DEFAULT FALSE,
    font_adjusted   BOOLEAN NOT NULL DEFAULT FALSE, -- si se redujo fuente para caber
    review_status   VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending → accepted → rejected → manual_review
    applied         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(block_id, version)
);

CREATE INDEX idx_patches_review ON patches(review_status);
```

### Tabla: `context_snapshots`

```sql
CREATE TABLE context_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    upto_page_no    INTEGER NOT NULL,
    snapshot_uri    VARCHAR(1024) NOT NULL,          -- MinIO: context/{doc_id}/snapshot_{page_no}.json
    glossary        JSONB NOT NULL DEFAULT '{}',     -- {"término": "forma_preferida", ...}
    entities        JSONB NOT NULL DEFAULT '[]',     -- ["nombre propio 1", "institución X", ...]
    style_prefs     JSONB NOT NULL DEFAULT '{}',     -- {"tratamiento": "usted", "citas": "APA", ...}
    narrative_summary TEXT,                          -- resumen del hilo narrativo hasta esta página
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(doc_id, upto_page_no)
);
```

### Tabla: `font_map`

```sql
CREATE TABLE font_map (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ps_name         VARCHAR(256) NOT NULL,          -- nombre PostScript extraído del PDF
    resolved_path   VARCHAR(1024),                  -- ruta al archivo TTF/OTF
    is_fallback     BOOLEAN NOT NULL DEFAULT FALSE, -- si es un sustituto métrica-compatible
    is_subsetted    BOOLEAN NOT NULL DEFAULT FALSE, -- si la fuente estaba subseteada
    glyphs_missing  JSONB DEFAULT '[]',             -- caracteres que faltan en el subset
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(doc_id, ps_name)
);
```

### Tabla: `jobs`

```sql
CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id         UUID REFERENCES pages(id) ON DELETE SET NULL,
    task_type       VARCHAR(30) NOT NULL,           -- 'ingest', 'convert', 'extract', 'context', 'correct', 'render', 'assemble'
    celery_task_id  VARCHAR(256),
    status          VARCHAR(20) NOT NULL DEFAULT 'queued',
                    -- queued → running → completed → failed → retrying
    attempt         INTEGER NOT NULL DEFAULT 1,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jobs_doc_type ON jobs(doc_id, task_type);
CREATE INDEX idx_jobs_status ON jobs(status);
```

---

## 4. Almacenamiento de objetos (MinIO)

### Estructura de buckets y rutas

```
stylecorrector/                         ← bucket principal
├── source/{doc_id}/{filename}          ← documento original (PDF o DOCX)
├── pdf/{doc_id}/{filename}.pdf         ← PDF (convertido si era DOCX)
├── docx/{doc_id}/{filename}_corrected.docx  ← DOCX corregido (Ruta 1)
├── pages/{doc_id}/
│   ├── layout/{page_no}.json           ← estructura de la página (spans, bloques)
│   ├── text/{page_no}.txt              ← texto plano extraído
│   ├── preview/{page_no}.png           ← thumbnail para la UI (150 DPI)
│   ├── patch/{page_no}_v{ver}.json     ← parches de corrección
│   └── output/{page_no}.pdf           ← página renderizada individual
├── context/{doc_id}/
│   └── snapshot_{upto_page}.json       ← instantánea de contexto
├── fonts/{doc_id}/
│   └── {font_name}.ttf                ← fuentes extraídas del documento
└── final/{doc_id}/
    ├── {filename}_corrected.pdf        ← PDF final corregido
    └── {filename}_corrected.docx       ← DOCX final (opcional)
```

### Configuración MinIO

```yaml
# Políticas de retención
retention: 30 days             # artefactos intermedios
retention_final: 365 days      # documentos finales

# Límites
max_upload_size: 500 MB        # por documento
max_document_pages: 1000       # páginas máximas por documento
```

---

## 5. Rutas de renderizado — Estrategia de fidelidad

### 5.1 Clasificador de tipo de página

```python
def classify_page(page: fitz.Page) -> str:
    """
    Clasifica una página como 'digital', 'scanned' o 'mixed'.
    
    Heurística:
    1. Extraer texto con get_text("text")
    2. Contar caracteres extraídos
    3. Obtener imágenes con get_images()
    4. Calcular área de imágenes vs área de página
    
    Criterios:
    - Si chars > 50 y area_imagenes < 80% → 'digital'
    - Si chars < 10 y area_imagenes > 80% → 'scanned'
    - Si chars > 10 y area_imagenes > 50% → 'mixed'
    """
```

### 5.2 Ruta 1: DOCX-first

**Prerrequisito:** El documento original es DOCX (o se tiene el archivo DOCX fuente).

#### Flujo detallado

```python
def render_docx_first(doc_path: str, patches: list[Patch]) -> str:
    """
    1. Abrir DOCX con python-docx
    2. Iterar párrafos → runs
    3. Para cada run, buscar si hay parche aplicable
    4. Si hay parche aceptado → reemplazar run.text (preservar run.font, run.bold, etc.)
    5. Guardar DOCX corregido
    6. Convertir a PDF con LibreOffice headless
    7. Validar visualmente
    """
```

#### Mapeo de parches a runs de DOCX

El desafío es que los parches se generan a nivel de bloque/span del PDF, pero deben aplicarse a nivel de run del DOCX. Estrategia:

1. Extraer texto del DOCX párrafo por párrafo.
2. Extraer texto del PDF bloque por bloque.
3. Alinear bloques PDF ↔ párrafos DOCX por similitud de texto (difflib.SequenceMatcher).
4. Aplicar los parches del bloque PDF al párrafo DOCX correspondiente.
5. Dentro del párrafo, distribuir el cambio entre los runs correspondientes.

#### Preservación de formato en runs

```python
from docx import Document
from docx.shared import Pt, RGBColor

doc = Document("input.docx")
for paragraph in doc.paragraphs:
    for run in paragraph.runs:
        # PRESERVAR: run.font.name, run.font.size, run.bold, run.italic,
        #            run.font.color.rgb, run.underline, run.font.superscript, etc.
        # SOLO MODIFICAR: run.text
        corrected = apply_patch(run.text, relevant_patches)
        if corrected != run.text:
            run.text = corrected
            # El formato se preserva automáticamente
```

#### Manejo de tablas en DOCX

```python
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.text = apply_patch(run.text, patches)
```

#### Manejo de headers/footers

```python
for section in doc.sections:
    for paragraph in section.header.paragraphs:
        for run in paragraph.runs:
            run.text = apply_patch(run.text, patches)
    for paragraph in section.footer.paragraphs:
        for run in paragraph.runs:
            run.text = apply_patch(run.text, patches)
```

### 5.3 Ruta 2: Redact + insert_htmlbox (PDF born-digital)

#### Flujo detallado paso a paso

```python
def render_pdf_digital(page: fitz.Page, patches: list[Patch], font_map: dict) -> fitz.Page:
    """
    Para cada bloque con parche aceptado:
    """
    
    # PASO 1: Obtener spans originales con detalle completo
    text_dict = page.get_text("dict")
    # text_dict["blocks"][i]["lines"][j]["spans"][k] = {
    #     "text": "...", "font": "...", "size": 12.0,
    #     "flags": 20, "color": 0x000000,
    #     "bbox": (x0, y0, x1, y1), "origin": (x, y)
    # }
    
    # PASO 2: Para cada bloque que tiene parche aceptado
    for block in blocks_with_patches:
        patch = get_accepted_patch(block)
        
        # PASO 3: Validar cabida
        bbox = fitz.Rect(block.bbox_x0, block.bbox_y0, block.bbox_x1, block.bbox_y1)
        font_path = font_map[block.font_info[0]["font"]]
        font = fitz.Font(fontfile=font_path)
        text_width = font.text_length(patch.corrected_text, fontsize=block.font_info[0]["size"])
        
        if text_width > bbox.width * 1.1:
            # Reducir fuente hasta -10%
            adjusted_size = find_fitting_size(font, patch.corrected_text, bbox, 
                                              original_size=block.font_info[0]["size"],
                                              min_ratio=0.90)
            if adjusted_size is None:
                mark_for_manual_review(patch)
                continue
        
        # PASO 4: Redactar (borrar) el texto original
        page.add_redact_annot(bbox)
    
    # PASO 5: Aplicar todas las redacciones de una vez
    page.apply_redactions(
        images=0,    # NO tocar imágenes (PDF_REDACT_IMAGE_NONE)
        graphics=0   # NO tocar gráficos vectoriales
    )
    
    # PASO 6: Insertar texto corregido con insert_htmlbox
    for block in blocks_with_patches:
        patch = get_accepted_patch(block)
        bbox = fitz.Rect(block.bbox_x0, block.bbox_y0, block.bbox_x1, block.bbox_y1)
        
        # Construir HTML que replica los estilos originales
        html = build_styled_html(patch.corrected_text, block.font_info)
        
        # Crear archivo de fuentes para CSS @font-face
        archive = fitz.Archive(font_directory)
        
        # Insertar con auto-scaling
        excess = page.insert_htmlbox(
            bbox, 
            html,
            archive=archive,
            scale_low=0.90  # permite reducción hasta 90%
        )
        
        if excess < 0:
            # No cupo ni con reducción → marcar
            mark_for_manual_review(patch)
    
    return page
```

#### Generación de HTML estilizado

```python
def build_styled_html(corrected_text: str, font_info: list[dict]) -> str:
    """
    Genera HTML que replica estilos del PDF original.
    
    font_info es una lista de spans con sus propiedades:
    [{"font": "Arial-BoldMT", "size": 12, "color": "#000000", "flags": 20}]
    
    flags bits: superscript=1, italic=2, serif=4, monospaced=8, bold=16
    """
    css_parts = []
    html_parts = []
    
    for i, span_info in enumerate(font_info):
        font_family = map_ps_to_css_family(span_info["font"])
        font_size = span_info["size"]
        color = f'#{span_info["color"]:06x}' if isinstance(span_info["color"], int) else span_info["color"]
        
        is_bold = bool(span_info["flags"] & 16)
        is_italic = bool(span_info["flags"] & 2)
        
        style = (
            f'font-family:"{font_family}";'
            f'font-size:{font_size}pt;'
            f'color:{color};'
            f'{"font-weight:bold;" if is_bold else ""}'
            f'{"font-style:italic;" if is_italic else ""}'
        )
        html_parts.append(f'<span style="{style}">{corrected_text}</span>')
    
    # Si el bloque tiene un solo span (caso más común)
    if len(font_info) == 1:
        return html_parts[0]
    
    # Si tiene múltiples spans, hay que segmentar el texto corregido
    # y asignar cada segmento al span correspondiente
    return "".join(html_parts)
```

#### Parámetros críticos de apply_redactions

```python
# SEGURO: solo elimina texto, preserva imágenes y gráficos
page.apply_redactions(images=0, graphics=0)

# PELIGROSO: eliminaría imágenes que se superponen con el área de redacción
# page.apply_redactions(images=2, graphics=2)  # NO USAR

# Constantes de referencia:
# images=0 (PDF_REDACT_IMAGE_NONE): no tocar imágenes
# images=1 (PDF_REDACT_IMAGE_REMOVE): eliminar imágenes superpuestas
# images=2 (PDF_REDACT_IMAGE_PIXELS): solo borrar píxeles superpuestos  
# graphics=0: no tocar vectores
# graphics=1: eliminar vectores superpuestos
```

### 5.4 Ruta 3: Imagen + capa de texto (PDF escaneado)

#### Flujo detallado

```python
def render_pdf_scanned(page: fitz.Page, ocr_result: dict, patches: list[Patch]) -> fitz.Page:
    """
    1. Renderizar página como imagen de alta resolución
    2. Para cada bloque con parche: pintar sobre el texto original
    3. Dibujar texto corregido sobre la imagen
    4. Crear PDF con imagen + capa de texto invisible
    """
    
    # PASO 1: Renderizar a imagen (300 DPI)
    pix = page.get_pixmap(dpi=300)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(img)
    
    # PASO 2: Para cada bloque corregido
    for block, patch in corrected_blocks:
        # Escalar bbox de puntos PDF a píxeles de imagen
        bbox_px = scale_bbox_to_pixels(block.bbox, page.rect, pix.width, pix.height)
        
        # Detectar color de fondo del área (moda de píxeles en el borde del bbox)
        bg_color = detect_background_color(img, bbox_px)
        
        # Pintar rectángulo del color del fondo sobre el texto original
        draw.rectangle(bbox_px, fill=bg_color)
        
        # Dibujar texto corregido
        font_pil = ImageFont.truetype(font_path, size=font_size_px)
        draw.text((bbox_px[0], bbox_px[1]), patch.corrected_text, 
                  fill=text_color, font=font_pil)
    
    # PASO 3: Crear nueva página PDF con la imagen
    new_page = create_pdf_page_from_image(img)
    
    # PASO 4: Añadir capa de texto invisible (searchable)
    add_invisible_text_layer(new_page, ocr_result, patches)
    
    return new_page
```

#### Detección de color de fondo

```python
def detect_background_color(img: Image, bbox: tuple) -> tuple:
    """
    Detecta el color de fondo predominante en los bordes del bbox.
    Muestrea píxeles en un borde de 2px alrededor del área.
    Devuelve la moda (color más frecuente).
    """
    x0, y0, x1, y1 = bbox
    margin = 2
    
    border_pixels = []
    # Borde superior
    for x in range(x0, x1):
        for y in range(max(0, y0 - margin), y0):
            border_pixels.append(img.getpixel((x, y)))
    # Borde inferior
    for x in range(x0, x1):
        for y in range(y1, min(img.height, y1 + margin)):
            border_pixels.append(img.getpixel((x, y)))
    
    # Moda
    from collections import Counter
    return Counter(border_pixels).most_common(1)[0][0]
```

---

## 6. Gestión de fuentes

### 6.1 Mapeo de fuentes PostScript → TTF/OTF

El sistema mantiene una tabla de mapeo en `fonts/font_map.json`:

```json
{
  "ArialMT": "liberation-sans/LiberationSans-Regular.ttf",
  "Arial-BoldMT": "liberation-sans/LiberationSans-Bold.ttf",
  "Arial-ItalicMT": "liberation-sans/LiberationSans-Italic.ttf",
  "Arial-BoldItalicMT": "liberation-sans/LiberationSans-BoldItalic.ttf",
  "TimesNewRomanPSMT": "liberation-serif/LiberationSerif-Regular.ttf",
  "TimesNewRomanPS-BoldMT": "liberation-serif/LiberationSerif-Bold.ttf",
  "TimesNewRomanPS-ItalicMT": "liberation-serif/LiberationSerif-Italic.ttf",
  "CourierNewPSMT": "liberation-mono/LiberationMono-Regular.ttf",
  "Calibri": "carlito/Carlito-Regular.ttf",
  "Calibri-Bold": "carlito/Carlito-Bold.ttf",
  "Cambria": "caladea/Caladea-Regular.ttf",
  "Georgia": "fonts-georga/Georgia.ttf",
  "Verdana": "fonts-verdana/Verdana.ttf",
  "Helvetica": "liberation-sans/LiberationSans-Regular.ttf",
  "Helvetica-Bold": "liberation-sans/LiberationSans-Bold.ttf"
}
```

### 6.2 Algoritmo de resolución de fuentes

```python
def resolve_font(ps_name: str, doc_id: str) -> str:
    """
    Orden de prioridad:
    1. Fuente del sistema (Windows/Linux) por nombre exacto
    2. Fuente extraída del PDF (si no está subseteada)
    3. Mapeo en font_map.json (sustitutos métrica-compatibles)
    4. Google Noto Sans / Noto Serif como último recurso
    5. Si nada funciona → marcar bloque para revisión manual
    """
    
    # 1. Buscar en sistema
    system_path = find_system_font(ps_name)
    if system_path:
        return system_path
    
    # 2. Buscar fuente extraída del documento
    extracted = get_extracted_font(doc_id, ps_name)
    if extracted and not extracted.is_subsetted:
        return extracted.path
    
    # 3. Buscar en font_map.json
    # Limpiar prefijo de subset (ej: "BCDFGH+ArialMT" → "ArialMT")
    clean_name = re.sub(r'^[A-Z]{6}\+', '', ps_name)
    if clean_name in FONT_MAP:
        return os.path.join(FONTS_DIR, FONT_MAP[clean_name])
    
    # 4. Fallback Noto
    if is_serif(ps_name):
        return os.path.join(FONTS_DIR, "noto/NotoSerif-Regular.ttf")
    else:
        return os.path.join(FONTS_DIR, "noto/NotoSans-Regular.ttf")
```

### 6.3 Fuentes métrica-compatibles requeridas

Instalar estas fuentes en el servidor/contenedor:

| Fuente original (MS) | Sustituto libre | Paquete |
|---|---|---|
| Arial | Liberation Sans | `fonts-liberation` |
| Times New Roman | Liberation Serif | `fonts-liberation` |
| Courier New | Liberation Mono | `fonts-liberation` |
| Calibri | Carlito | `fonts-crosextra-carlito` |
| Cambria | Caladea | `fonts-crosextra-caladea` |
| (fallback universal) | Noto Sans / Noto Serif | `fonts-noto` |

```dockerfile
# En Dockerfile del backend
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    fonts-noto-core \
    fonts-noto-extra \
    && rm -rf /var/lib/apt/lists/*
```

### 6.4 Extracción de fuentes de un PDF

```python
def extract_fonts_from_pdf(doc: fitz.Document, doc_id: str) -> list[FontInfo]:
    """
    Extraer todas las fuentes embebidas del PDF y guardarlas.
    """
    fonts_extracted = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        font_list = page.get_fonts(full=True)
        
        for xref, ext, font_type, basefont, name, encoding in font_list:
            if xref in already_processed:
                continue
            
            # Extraer binario de la fuente
            basename, extension, subtype, buffer = doc.extract_font(xref)
            
            if buffer:
                # Guardar en MinIO
                font_path = f"fonts/{doc_id}/{basename}.{extension}"
                save_to_minio(font_path, buffer)
                
                # Detectar si está subseteada (prefijo tipo "ABCDEF+")
                is_subsetted = bool(re.match(r'^[A-Z]{6}\+', basefont))
                
                fonts_extracted.append(FontInfo(
                    ps_name=basefont,
                    path=font_path,
                    is_subsetted=is_subsetted,
                    extension=extension
                ))
    
    return fonts_extracted
```

---

## 7. Corrección determinista (LanguageTool)

### 7.1 Configuración del servidor

```yaml
# docker-compose.yml
languagetool:
  image: erikvl87/languagetool:latest
  ports:
    - "8010:8010"
  environment:
    - langtool_languageModel=/ngrams        # n-grams para mejor detección
    - Java_Xms=512m
    - Java_Xmx=2g
  volumes:
    - languagetool_ngrams:/ngrams
```

### 7.2 Uso desde Python

```python
import language_tool_python

# Conectar al servidor local
tool = language_tool_python.LanguageToolPublicAPI('es', remote_server='http://languagetool:8010')

# O con la librería que incluye servidor embebido:
# tool = language_tool_python.LanguageTool('es')

def correct_with_lt(text: str, config: dict) -> tuple[str, list[dict]]:
    """
    Corrige texto con LanguageTool.
    Devuelve (texto_corregido, lista_de_cambios).
    """
    matches = tool.check(text)
    
    # Filtrar por reglas habilitadas en config
    enabled_categories = config.get("lt_categories", [
        "TYPOS",
        "GRAMMAR", 
        "PUNCTUATION",
        "STYLE",          # solo si config["perfeccionista"] = True
        "REDUNDANCY",     # solo si config["perfeccionista"] = True
    ])
    
    filtered = [m for m in matches if m.category in enabled_categories]
    
    # Aplicar correcciones automáticas (solo la primera sugerencia)
    corrected = language_tool_python.utils.correct(text, filtered)
    
    changes = [{
        "offset": m.offset,
        "length": m.errorLength,
        "original": text[m.offset:m.offset + m.errorLength],
        "replacement": m.replacements[0] if m.replacements else None,
        "rule_id": m.ruleId,
        "category": m.category,
        "message": m.message
    } for m in filtered if m.replacements]
    
    return corrected, changes
```

### 7.3 Reglas personalizables por proyecto

```json
// Ejemplo de config_json en documents
{
  "language": "es",
  "perfeccionista": true,
  "lt_disabled_rules": ["UPPERCASE_SENTENCE_START", "ES_QUESTION_MARK"],
  "lt_enabled_only": [],
  "custom_dictionary": ["tokenización", "bounding box", "PyMuPDF"],
  "glossary": {
    "dossier": "documento",
    "customizar": "personalizar",
    "implementar": "ejecutar"
  }
}
```

---

## 8. Corrección LLM — Schema de parches

### 8.1 Formato del prompt

```
SISTEMA:
Eres un corrector de estilo profesional en español. Tu tarea es mejorar la redacción
del siguiente bloque de texto sin cambiar su significado.

REGLAS ESTRICTAS:
1. Devuelve SOLO un objeto JSON con el formato especificado.
2. No reescribas el texto completo. Genera solo las operaciones de reemplazo necesarias.
3. El texto corregido NO puede exceder el 110% de la longitud del original.
4. Respeta el glosario del proyecto.
5. Mantén el nivel de formalidad: {tratamiento}.
6. No cambies nombres propios, cifras, fechas ni términos técnicos del glosario.
7. Si el texto no necesita corrección, devuelve operations como lista vacía.

GLOSARIO DEL PROYECTO:
{glossary_json}

CONTEXTO PREVIO (resumen):
{narrative_summary}

ENTIDADES CONOCIDAS:
{entities_list}

BLOQUE A CORREGIR:
---
{block_text}
---

Responde SOLO con este JSON:
```

### 8.2 Schema JSON de respuesta del LLM

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["operations", "corrected_full"],
  "properties": {
    "operations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "original", "replacement", "reason"],
        "properties": {
          "type": {
            "type": "string",
            "enum": ["replace", "insert", "delete"]
          },
          "original": {
            "type": "string",
            "description": "Fragmento original exacto a reemplazar"
          },
          "replacement": {
            "type": "string",
            "description": "Texto de reemplazo"
          },
          "reason": {
            "type": "string",
            "description": "Razón breve de la corrección",
            "enum": [
              "ortografia",
              "concordancia",
              "puntuacion",
              "redundancia",
              "claridad",
              "formalidad",
              "coherencia",
              "estilo"
            ]
          }
        }
      }
    },
    "corrected_full": {
      "type": "string",
      "description": "El bloque completo con todas las correcciones aplicadas"
    }
  }
}
```

### 8.3 Ejemplo de respuesta esperada

```json
{
  "operations": [
    {
      "type": "replace",
      "original": "en base a",
      "replacement": "con base en",
      "reason": "estilo"
    },
    {
      "type": "replace",
      "original": "hay que tener en cuenta que",
      "replacement": "cabe considerar que",
      "reason": "redundancia"
    },
    {
      "type": "delete",
      "original": "realmente",
      "replacement": "",
      "reason": "redundancia"
    }
  ],
  "corrected_full": "Con base en los datos disponibles, cabe considerar que el proceso requiere ajustes significativos."
}
```

### 8.4 GBNF Grammar para constrained decoding (llama.cpp)

```gbnf
root ::= "{" ws "\"operations\"" ws ":" ws operations "," ws "\"corrected_full\"" ws ":" ws string "}" ws

operations ::= "[" ws (operation ("," ws operation)*)? "]"

operation ::= "{" ws
  "\"type\"" ws ":" ws op-type "," ws
  "\"original\"" ws ":" ws string "," ws
  "\"replacement\"" ws ":" ws string "," ws
  "\"reason\"" ws ":" ws reason
  "}" ws

op-type ::= "\"replace\"" | "\"insert\"" | "\"delete\""

reason ::= "\"ortografia\"" | "\"concordancia\"" | "\"puntuacion\"" | "\"redundancia\"" | "\"claridad\"" | "\"formalidad\"" | "\"coherencia\"" | "\"estilo\""

string ::= "\"" ([^"\\] | "\\" .)* "\""

ws ::= [ \t\n\r]*
```

### 8.5 Cliente llama.cpp

```python
import httpx

LLAMA_URL = "http://llama:8080"

async def correct_with_llm(
    block_text: str,
    context: ContextSnapshot,
    config: dict
) -> dict:
    """
    Envía bloque al LLM y obtiene parches JSON.
    Usa constrained decoding con GBNF grammar.
    """
    prompt = build_prompt(block_text, context, config)
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{LLAMA_URL}/completion",
            json={
                "prompt": prompt,
                "n_predict": 1024,
                "temperature": 0.3,      # baja para corrección (más determinista)
                "top_p": 0.9,
                "grammar": GBNF_GRAMMAR, # constrained decoding
                "stop": ["```"],
                "stream": False
            }
        )
    
    result = response.json()
    content = result["content"]
    
    # Parsear JSON (debería ser válido gracias a GBNF)
    try:
        patch_data = json.loads(content)
    except json.JSONDecodeError:
        # Fallback: intentar extraer JSON del texto
        patch_data = extract_json_from_text(content)
    
    # Validar longitud
    if len(patch_data["corrected_full"]) > len(block_text) * 1.10:
        raise OverflowError("Texto corregido excede 110% del original")
    
    return patch_data
```

### 8.6 Modelos LLM recomendados

| Modelo | Tamaño | Cuantización | VRAM | Calidad español | Notas |
|---|---|---|---|---|---|
| Qwen2.5-7B-Instruct | 7B | Q4_K_M | ~6 GB | Muy buena | **Recomendado para MVP** |
| Qwen2.5-14B-Instruct | 14B | Q4_K_M | ~10 GB | Excelente | Si hay GPU >12GB |
| Mistral-7B-Instruct-v0.3 | 7B | Q4_K_M | ~6 GB | Buena | Alternativa a Qwen |
| Llama-3.1-8B-Instruct | 8B | Q4_K_M | ~6 GB | Buena | Alternativa general |
| Gemma-2-9B-Instruct | 9B | Q4_K_M | ~7 GB | Buena | Alternativa |

**Criterios de selección:**
- Soporte de español nativo (no solo traducción).
- Capacidad de seguir instrucciones de formato JSON.
- Tamaño que quepa en la GPU disponible.
- Compatibilidad con GBNF grammar en llama.cpp.

---

## 9. Extracción de layout

### 9.1 PyMuPDF: Extracción a nivel diccionario

```python
def extract_page_layout(page: fitz.Page) -> dict:
    """
    Extrae la estructura completa de una página.
    """
    # Extracción detallada (bloques → líneas → spans)
    text_dict = page.get_text("dict", sort=True)
    
    # Estructura:
    # text_dict = {
    #     "width": 612.0, "height": 792.0,
    #     "blocks": [
    #         {
    #             "number": 0, "type": 0 (texto) o 1 (imagen),
    #             "bbox": (x0, y0, x1, y1),
    #             "lines": [
    #                 {
    #                     "bbox": (...), "wmode": 0, "dir": (1.0, 0.0),
    #                     "spans": [
    #                         {
    #                             "size": 12.0, "flags": 20,
    #                             "font": "Arial-BoldMT",
    #                             "color": 0, "ascender": 0.905,
    #                             "descender": -0.212,
    #                             "text": "Texto del span",
    #                             "bbox": (72.0, 100.5, 145.2, 114.5),
    #                             "origin": (72.0, 112.3)
    #                         }
    #                     ]
    #                 }
    #             ]
    #         }
    #     ]
    # }
    
    # Extraer imágenes también
    images = page.get_images(full=True)
    image_blocks = []
    for img in images:
        xref = img[0]
        img_rect = page.get_image_bbox(img)
        image_blocks.append({
            "type": "image",
            "xref": xref,
            "bbox": list(img_rect),
        })
    
    # Combinar
    layout = {
        "page_width": text_dict["width"],
        "page_height": text_dict["height"],
        "text_blocks": text_dict["blocks"],
        "image_blocks": image_blocks,
    }
    
    return layout
```

### 9.2 Layout Parser: Detección de estructura (Fase 4)

```python
import layoutparser as lp

def detect_page_structure(image_path: str) -> list[dict]:
    """
    Usa Layout Parser con Detectron2 para detectar regiones.
    """
    model = lp.Detectron2LayoutModel(
        config_path="lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config",
        label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
        extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5]
    )
    
    image = cv2.imread(image_path)
    layout = model.detect(image)
    
    regions = []
    for block in layout:
        regions.append({
            "type": block.type,
            "bbox": [block.block.x_1, block.block.y_1, block.block.x_2, block.block.y_2],
            "score": block.score
        })
    
    return regions
```

---

## 10. OCR para escaneados

### 10.1 docTR: Pipeline de dos etapas

```python
from doctr.models import ocr_predictor
from doctr.io import DocumentFile

def ocr_page(image_path: str) -> dict:
    """
    Ejecuta OCR con docTR.
    Devuelve palabras con posiciones normalizadas (0-1).
    """
    model = ocr_predictor(
        det_arch='db_resnet50',     # modelo de detección
        reco_arch='crnn_vgg16_bn',  # modelo de reconocimiento
        pretrained=True
    )
    
    doc = DocumentFile.from_images(image_path)
    result = model(doc)
    
    words = []
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    words.append({
                        "text": word.value,
                        "confidence": word.confidence,
                        "bbox": word.geometry,  # ((x0,y0), (x1,y1)) normalizado 0-1
                    })
    
    return {"words": words}
```

### 10.2 Reconstrucción de bloques desde palabras OCR

```python
def words_to_blocks(words: list[dict], page_width: float, page_height: float) -> list[dict]:
    """
    Agrupa palabras en líneas y bloques por proximidad espacial.
    """
    # Ordenar por posición Y (arriba a abajo), luego X (izquierda a derecha)
    words_sorted = sorted(words, key=lambda w: (w["bbox"][0][1], w["bbox"][0][0]))
    
    lines = []
    current_line = [words_sorted[0]]
    
    for word in words_sorted[1:]:
        prev = current_line[-1]
        # Si la palabra está en la misma línea (Y similar, diferencia < umbral)
        if abs(word["bbox"][0][1] - prev["bbox"][0][1]) < 0.01:  # 1% de la página
            current_line.append(word)
        else:
            lines.append(current_line)
            current_line = [word]
    lines.append(current_line)
    
    # Agrupar líneas en bloques por proximidad vertical
    blocks = group_lines_into_blocks(lines, gap_threshold=0.02)
    
    return blocks
```

---

## 11. Pipeline Celery — Tareas y flujos

### 11.1 Configuración de Celery

```python
# workers/celery_app.py
from celery import Celery

app = Celery(
    'stylecorrector',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/1',
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    task_acks_late=True,                  # ACK después de completar (tolerancia a fallos)
    worker_prefetch_multiplier=1,          # Un trabajo a la vez por worker
    task_reject_on_worker_lost=True,       # Re-encolar si el worker muere
    task_time_limit=600,                   # 10 min máx por tarea
    task_soft_time_limit=540,              # Warning a los 9 min
    result_expires=86400,                  # Resultados expiran en 24h
)

# Colas especializadas
app.conf.task_routes = {
    'tasks_ingest.*': {'queue': 'ingest'},
    'tasks_extract.*': {'queue': 'extract'},
    'tasks_correct.*': {'queue': 'correct'},
    'tasks_render.*': {'queue': 'render'},
}
```

### 11.2 Flujo orquestado por documento

```python
from celery import chain, group, chord

def process_document(doc_id: str):
    """
    Orquesta el pipeline completo para un documento.
    """
    workflow = chain(
        # Etapa A: Ingesta
        ingest_document.si(doc_id),
        
        # Etapa B: Extracción (paralelo por página)
        # chord ejecuta extract en paralelo y luego on_extraction_complete
        create_extraction_chord.si(doc_id),
        
        # Etapa C + D: Corrección por ventanas
        # Se ejecuta secuencialmente por ventanas de N páginas
        correct_by_windows.si(doc_id),
        
        # Etapa E: Renderizado (paralelo por página)
        create_render_chord.si(doc_id),
        
        # Ensamble final
        assemble_final_pdf.si(doc_id),
    )
    
    workflow.apply_async()
```

### 11.3 Tareas individuales

```python
# workers/tasks_ingest.py
@app.task(bind=True, max_retries=3)
def ingest_document(self, doc_id: str):
    """Etapa A: normalizar, convertir a PDF si necesario, contar páginas."""
    try:
        doc = get_document(doc_id)
        
        if doc.original_format == 'docx':
            pdf_path = convert_docx_to_pdf(doc.source_uri)
            update_document(doc_id, pdf_uri=pdf_path, status='converting')
        
        page_count = count_pages(doc.pdf_uri)
        create_page_records(doc_id, page_count)
        update_document(doc_id, total_pages=page_count, status='extracting')
        
    except Exception as exc:
        self.retry(exc=exc, countdown=60)

# workers/tasks_extract.py
@app.task(bind=True, max_retries=2)
def extract_page(self, doc_id: str, page_no: int):
    """Etapa B: extraer layout de una página."""
    try:
        page_type = classify_page(doc_id, page_no)
        
        if page_type == 'digital':
            layout = extract_with_pymupdf(doc_id, page_no)
        elif page_type == 'scanned':
            layout = extract_with_doctr(doc_id, page_no)
        else:  # mixed
            layout = extract_mixed(doc_id, page_no)
        
        save_layout(doc_id, page_no, layout)
        save_preview(doc_id, page_no)
        update_page(doc_id, page_no, page_type=page_type, status='extracted')
        
    except Exception as exc:
        self.retry(exc=exc, countdown=30)

# workers/tasks_correct.py
@app.task(bind=True, max_retries=2)
def correct_page(self, doc_id: str, page_no: int, context_snapshot_id: str):
    """Etapa D: corregir una página (LanguageTool + LLM)."""
    try:
        layout = load_layout(doc_id, page_no)
        context = load_context(context_snapshot_id)
        config = load_document_config(doc_id)
        
        for block in layout['text_blocks']:
            if block['type'] != 0:  # solo bloques de texto
                continue
            
            text = extract_block_text(block)
            
            # Paso 1: LanguageTool
            lt_corrected, lt_changes = correct_with_lt(text, config)
            
            # Paso 2: LLM
            llm_result = await correct_with_llm(lt_corrected, context, config)
            
            # Paso 3: Validar cabida
            overflow = check_overflow(
                llm_result["corrected_full"], 
                block["bbox"],
                block["lines"][0]["spans"][0]  # font info
            )
            
            # Paso 4: Guardar parche
            save_patch(
                block_id=block["id"],
                original=text,
                corrected=llm_result["corrected_full"],
                operations=llm_result["operations"],
                overflow_flag=overflow,
            )
        
        update_page(doc_id, page_no, status='corrected')
        
    except Exception as exc:
        self.retry(exc=exc, countdown=60)

# workers/tasks_render.py
@app.task(bind=True, max_retries=2)
def render_page(self, doc_id: str, page_no: int):
    """Etapa E: renderizar una página con los parches aceptados."""
    try:
        page_record = get_page(doc_id, page_no)
        patches = get_accepted_patches(page_record.id)
        
        if page_record.render_route == 'docx_first':
            result = render_docx_first(doc_id, page_no, patches)
        elif page_record.render_route == 'redact_htmlbox':
            result = render_pdf_digital(doc_id, page_no, patches)
        elif page_record.render_route == 'image_overlay':
            result = render_pdf_scanned(doc_id, page_no, patches)
        
        # Validación visual
        similarity = visual_compare(doc_id, page_no, result)
        if similarity < 0.85:  # umbral de alerta
            flag_for_review(doc_id, page_no, "visual_regression", similarity)
        
        save_rendered_page(doc_id, page_no, result)
        update_page(doc_id, page_no, status='rendered')
        
    except Exception as exc:
        self.retry(exc=exc, countdown=60)
```

---

## 12. API REST (FastAPI)

### 12.1 Endpoints principales

```
POST   /api/v1/documents/upload              ← Subir documento
GET    /api/v1/documents/{id}                ← Estado del documento
GET    /api/v1/documents/{id}/pages          ← Lista de páginas con estado
GET    /api/v1/documents/{id}/pages/{no}     ← Detalle de una página
GET    /api/v1/documents/{id}/pages/{no}/preview  ← Imagen preview
GET    /api/v1/documents/{id}/pages/{no}/diff     ← Texto original vs corregido

GET    /api/v1/patches/{page_id}             ← Parches de una página
PUT    /api/v1/patches/{id}/accept           ← Aceptar parche
PUT    /api/v1/patches/{id}/reject           ← Rechazar parche
PUT    /api/v1/patches/{id}/edit             ← Editar corrección manualmente

POST   /api/v1/documents/{id}/render         ← Trigger renderizado final
GET    /api/v1/documents/{id}/download        ← Descargar PDF final
GET    /api/v1/documents/{id}/download/docx   ← Descargar DOCX final (si aplica)

GET    /api/v1/documents/{id}/progress       ← Progreso en tiempo real (SSE)

PUT    /api/v1/documents/{id}/config         ← Actualizar config (glosario, reglas)
```

### 12.2 Schemas Pydantic

```python
# schemas/document.py
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    total_pages: int | None = None

class DocumentDetail(BaseModel):
    id: UUID
    filename: str
    original_format: str
    status: str
    total_pages: int | None
    config: dict
    created_at: datetime
    progress: float  # 0.0 a 1.0

class PageDetail(BaseModel):
    id: UUID
    page_no: int
    page_type: str
    render_route: str | None
    status: str
    preview_url: str | None
    patches_count: int
    patches_pending: int

class PatchDetail(BaseModel):
    id: UUID
    block_no: int
    original_text: str
    corrected_text: str
    operations: list[dict]
    source: str                  # 'languagetool', 'llm', 'manual'
    qa_score: float | None
    overflow_flag: bool
    review_status: str
    bbox: list[float]            # [x0, y0, x1, y1]

class DiffResponse(BaseModel):
    page_no: int
    blocks: list[BlockDiff]

class BlockDiff(BaseModel):
    block_no: int
    original: str
    corrected: str
    changes: list[dict]          # operaciones individuales
    review_status: str
    bbox: list[float]
```

---

## 13. Frontend (Next.js)

### 13.1 Páginas principales

```
/                           ← Dashboard: lista de documentos
/upload                     ← Subir nuevo documento + configurar reglas
/documents/{id}             ← Vista general del documento + progreso
/documents/{id}/review      ← Vista de revisión: diff lado a lado
/documents/{id}/review/{page} ← Revisión de una página específica
/documents/{id}/settings    ← Configuración: glosario, reglas, estilo
```

### 13.2 Componentes clave

#### DiffViewer: Vista lado a lado

```
┌─────────────────────────────────┬─────────────────────────────────┐
│         ORIGINAL (PDF)          │        CORREGIDO (PDF)          │
│  ┌───────────────────────────┐  │  ┌───────────────────────────┐  │
│  │                           │  │  │                           │  │
│  │   Renderizado del PDF     │  │  │   Renderizado del PDF     │  │
│  │   original con resaltado  │  │  │   corregido con resaltado │  │
│  │   en rojo de zonas        │  │  │   en verde de zonas       │  │
│  │   modificadas             │  │  │   modificadas             │  │
│  │                           │  │  │                           │  │
│  └───────────────────────────┘  │  └───────────────────────────┘  │
├─────────────────────────────────┴─────────────────────────────────┤
│                    PANEL DE CORRECCIONES                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ Bloque 3: "en base a" → "con base en"  [✓ Aceptar] [✗]    │  │
│  │ Bloque 5: "customizar" → "personalizar" [✓ Aceptar] [✗]   │  │
│  │ Bloque 7: "hay que tener en cuenta..." → "cabe..."  [✓][✗] │  │
│  └─────────────────────────────────────────────────────────────┘  │
│  ← Página anterior    [Página 12 de 245]    Página siguiente →   │
│  [Aceptar todos]  [Rechazar todos]  [Renderizar final]            │
└───────────────────────────────────────────────────────────────────┘
```

### 13.3 Librerías del frontend

| Función | Librería | Uso |
|---|---|---|
| Visor de PDF | `react-pdf` (pdf.js) | Renderizar PDF original y corregido |
| Diff de texto | `diff` (npm) | Calcular diferencias carácter/palabra |
| Resaltado | Canvas overlay o SVG | Dibujar rectángulos sobre zonas cambiadas |
| Estado | `zustand` | Gestión de estado global (documento activo, parches) |
| Notificaciones | SSE (EventSource) | Progreso en tiempo real desde el backend |
| Estilos | Tailwind CSS | UI responsive |

---

## 14. Docker Compose — Servicios

### 14.1 Configuración completa (MVP)

```yaml
# docker-compose.yml
version: '3.8'

services:
  # --- Base de datos ---
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: stylecorrector
      POSTGRES_USER: ${DB_USER:-stylecorrector}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U stylecorrector"]
      interval: 5s
      retries: 5

  # --- Cache / Broker ---
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  # --- Almacenamiento de objetos ---
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD:-minioadmin}
    ports:
      - "9000:9000"    # API S3
      - "9001:9001"    # Console web
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      retries: 5

  # --- LanguageTool ---
  languagetool:
    image: erikvl87/languagetool:latest
    ports:
      - "8010:8010"
    environment:
      - Java_Xms=512m
      - Java_Xmx=2g
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/v2/check?language=es&text=test"]
      interval: 10s
      retries: 5

  # --- LLM Server (llama.cpp) ---
  llama:
    image: ghcr.io/ggerganov/llama.cpp:server
    ports:
      - "8080:8080"
    volumes:
      - ./models:/models
    command: >
      --model /models/qwen2.5-7b-instruct-q4_k_m.gguf
      --host 0.0.0.0
      --port 8080
      --ctx-size 4096
      --n-gpu-layers 35
      --threads 4
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # --- Backend API ---
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER:-stylecorrector}:${DB_PASSWORD:-changeme}@postgres:5432/stylecorrector
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_USER:-minioadmin}
      - MINIO_SECRET_KEY=${MINIO_PASSWORD:-minioadmin}
      - LANGUAGETOOL_URL=http://languagetool:8010
      - LLAMA_URL=http://llama:8080
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./fonts:/app/fonts
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  # --- Celery Workers ---
  worker-ingest:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app worker -Q ingest --loglevel=info --concurrency=2
    environment:
      <<: *backend-env  # mismas variables que backend
    depends_on:
      - backend
    volumes:
      - ./fonts:/app/fonts

  worker-extract:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app worker -Q extract --loglevel=info --concurrency=4
    environment:
      <<: *backend-env
    depends_on:
      - backend

  worker-correct:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app worker -Q correct --loglevel=info --concurrency=2
    environment:
      <<: *backend-env
    depends_on:
      - backend
      - languagetool
      - llama

  worker-render:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app worker -Q render --loglevel=info --concurrency=4
    environment:
      <<: *backend-env
    depends_on:
      - backend
    volumes:
      - ./fonts:/app/fonts

  # --- Frontend ---
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend

  # --- Proxy reverso ---
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./infra/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### 14.2 Dockerfile del backend

```dockerfile
FROM python:3.11-slim

# Instalar LibreOffice headless y fuentes
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    fonts-noto-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 15. Validación visual automatizada

### 15.1 Comparación pixel a pixel

```python
import fitz
from PIL import Image
import numpy as np

def visual_compare(
    original_page: fitz.Page,
    corrected_page: fitz.Page, 
    dpi: int = 150,
    text_bboxes: list[tuple] = None
) -> dict:
    """
    Compara dos páginas pixel a pixel.
    Devuelve métricas de similitud.
    """
    # Renderizar ambas páginas
    pix_orig = original_page.get_pixmap(dpi=dpi)
    pix_corr = corrected_page.get_pixmap(dpi=dpi)
    
    arr_orig = np.frombuffer(pix_orig.samples, dtype=np.uint8).reshape(
        pix_orig.height, pix_orig.width, 3
    )
    arr_corr = np.frombuffer(pix_corr.samples, dtype=np.uint8).reshape(
        pix_corr.height, pix_corr.width, 3
    )
    
    # Diferencia absoluta
    diff = np.abs(arr_orig.astype(int) - arr_corr.astype(int))
    
    # Máscara de zonas de texto (donde esperamos diferencias)
    text_mask = np.zeros((pix_orig.height, pix_orig.width), dtype=bool)
    if text_bboxes:
        scale = dpi / 72.0
        for bbox in text_bboxes:
            x0 = int(bbox[0] * scale)
            y0 = int(bbox[1] * scale)
            x1 = int(bbox[2] * scale)
            y1 = int(bbox[3] * scale)
            text_mask[y0:y1, x0:x1] = True
    
    # Métricas
    total_pixels = arr_orig.shape[0] * arr_orig.shape[1]
    
    # Píxeles diferentes fuera de las zonas de texto (indica regresión visual)
    outside_text_diff = diff[~text_mask].sum()
    outside_text_pixels = (~text_mask).sum()
    
    # Similitud fuera de zonas de texto (debería ser ~1.0)
    outside_similarity = 1.0 - (outside_text_diff / (outside_text_pixels * 255 * 3 + 1e-10))
    
    # Similitud general
    overall_similarity = 1.0 - (diff.sum() / (total_pixels * 255 * 3))
    
    return {
        "overall_similarity": float(overall_similarity),
        "outside_text_similarity": float(outside_similarity),
        "regression_detected": outside_similarity < 0.98,
        "total_pixels_changed": int((diff.max(axis=2) > 10).sum()),
    }
```

### 15.2 Umbrales de calidad

| Métrica | Umbral OK | Umbral Warning | Umbral Error |
|---|---|---|---|
| `outside_text_similarity` | ≥ 0.99 | 0.95–0.99 | < 0.95 |
| `overall_similarity` | ≥ 0.90 | 0.80–0.90 | < 0.80 |
| `total_pixels_changed` | < 5% de la página | 5–15% | > 15% |

---

## 16. Seguridad

### 16.1 Autenticación (Fase 5)

```python
# JWT con roles
ROLES = {
    "editor": ["upload", "view", "download"],
    "reviewer": ["upload", "view", "download", "accept", "reject", "edit"],
    "admin": ["*"],
}
```

### 16.2 MinIO

- Bucket policies por proyecto/usuario.
- Cifrado en reposo habilitado (SSE-S3).
- Acceso solo mediante presigned URLs desde la API (nunca exponer MinIO al frontend directamente).

### 16.3 Red

- Todo el tráfico interno entre contenedores usa la red Docker (no expuesto).
- Solo Nginx expone el puerto 80/443 al exterior.
- TLS terminado en Nginx.

---

## 17. Variables de entorno

```env
# .env.example

# --- Base de datos ---
DB_USER=stylecorrector
DB_PASSWORD=change_this_password
DB_NAME=stylecorrector
DATABASE_URL=postgresql+asyncpg://stylecorrector:change_this_password@postgres:5432/stylecorrector

# --- Redis ---
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# --- MinIO ---
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=change_this_secret
MINIO_BUCKET=stylecorrector
MINIO_SECURE=false

# --- LanguageTool ---
LANGUAGETOOL_URL=http://languagetool:8010
LANGUAGETOOL_LANGUAGE=es

# --- LLM (llama.cpp) ---
LLAMA_URL=http://llama:8080
LLAMA_MODEL=/models/qwen2.5-7b-instruct-q4_k_m.gguf
LLAMA_CTX_SIZE=4096
LLAMA_GPU_LAYERS=35
LLAMA_THREADS=4

# --- Procesamiento ---
WINDOW_SIZE=10                    # páginas por ventana de contexto
MAX_OVERFLOW_RATIO=1.10           # máx 110% longitud del original
FONT_SIZE_MIN_RATIO=0.90          # reducción máx de fuente: 90%
VISUAL_SIMILARITY_THRESHOLD=0.95  # umbral de regresión visual
MAX_DOCUMENT_PAGES=1000           # páginas máx por documento
MAX_UPLOAD_SIZE_MB=500            # tamaño máx de upload

# --- JWT (Fase 5) ---
JWT_SECRET=change_this_jwt_secret
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
```
