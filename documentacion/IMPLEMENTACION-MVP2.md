# STYLIA — Guía de Implementación MVP 2

## Documento de referencia para IA y desarrollador

Este documento es la hoja de ruta operativa para transformar STYLIA de un "corrector automático de párrafos" a un "motor editorial con inteligencia contextual". Cada fase produce cambios verificables desde el frontend como usuario final.

**Prerequisito**: MVP 1 completado y funcional (`docker-compose up --build` levanta el stack completo).

---

## Inventario: qué existe hoy y qué cambia

### Archivos que se MODIFICAN (no se borran, se extienden)

| Archivo | Qué tiene hoy | Qué se le agrega |
|---------|---------------|-----------------|
| `backend/app/config.py` | 15 settings básicos | Settings de profiles, modelos por pasada, quality gates |
| `backend/app/models/document.py` | Document con config_json genérico | Relationship a `document_profiles` |
| `backend/app/models/block.py` | block_type, bbox, original_text | `paragraph_type`, `requires_llm`, `section_id` |
| `backend/app/models/patch.py` | source, original/corrected, operations_json | `category`, `severity`, `explanation`, `confidence`, `rewrite_ratio`, `pass_number`, `model_used` |
| `backend/app/schemas/document.py` | DocumentConfigUpdate básico | `StyleProfileCreate`, `StyleProfileResponse` |
| `backend/app/schemas/patch.py` | PatchListItem sin categoría | Campos `category`, `severity`, `explanation` |
| `backend/app/services/correction.py` | correct_docx_sync con prompt genérico | Prompt parametrizado, router de complejidad, multi-pasada |
| `backend/app/utils/openai_client.py` | OpenAIClient con un solo prompt | System prompt estático separado, user prompt dinámico, soporte multi-modelo |
| `backend/app/workers/tasks_pipeline.py` | Pipeline A→B→D→E | Insertar Etapa C (análisis) entre B y D |
| `backend/app/api/v1/documents.py` | Endpoints CRUD + corrections | Endpoints de profiles, endpoint de análisis editorial |
| `frontend/src/lib/api.ts` | Tipos básicos de patch/document | Tipos de profile, funciones API de profiles |
| `frontend/src/app/page.tsx` | Upload directo sin config | Selector de perfil post-upload |
| `frontend/src/app/documents/[id]/page.tsx` | 4 tabs sin categorías | Tabs con filtro por categoría, vista de profile |
| `frontend/src/components/CorrectionHistory.tsx` | Filtro source only | Filtro por categoría + severity, explicación visible |

### Archivos que se CREAN (nuevos)

| Archivo | Propósito |
|---------|-----------|
| `backend/app/models/style_profile.py` | Modelo ORM `DocumentProfile` |
| `backend/app/models/section_summary.py` | Modelo ORM `SectionSummary` |
| `backend/app/models/term_registry.py` | Modelo ORM `TermRegistry` |
| `backend/app/schemas/style_profile.py` | Schemas Pydantic para profiles |
| `backend/app/services/analysis.py` | Etapa C: análisis editorial completo |
| `backend/app/services/quality_gates.py` | Validación post-corrección |
| `backend/app/services/prompt_builder.py` | Constructor de prompts parametrizados |
| `backend/app/services/complexity_router.py` | Router: skip LLM / barato / editorial |
| `backend/app/data/profiles.py` | 10 perfiles predeterminados como constantes |
| `frontend/src/components/ProfileSelector.tsx` | UI selector de perfil editorial |
| `frontend/src/components/ProfileEditor.tsx` | UI edición de perfil |
| `frontend/src/components/AnalysisView.tsx` | UI vista de análisis editorial |
| `frontend/src/components/CorrectionCard.tsx` | Card de corrección con categoría/severidad |

---

## FASE 2A — Perfiles editoriales + prompt parametrizado

**Objetivo**: El usuario selecciona un perfil antes de procesar y ve correcciones categorizadas. El pipeline sigue siendo el mismo pero el prompt cambia según el perfil.

**Duración estimada**: Es la fase más grande porque toca muchas capas.

### 2A.1 — Modelo de datos del perfil editorial

**Qué hacer**: Crear la tabla `document_profiles` y vincularla a `documents`.

**Archivo nuevo**: `backend/app/models/style_profile.py`
```python
class DocumentProfile(Base):
    __tablename__ = "document_profiles"

    id: UUID (PK)
    doc_id: UUID (FK → documents.id, unique)
    preset_name: str | None          # "psicologia_divulgativa", "infantil_6_8", etc.
    source: str                      # "user" | "preset" | "inferred"
    genre: str | None
    subgenre: str | None
    audience_type: str | None
    audience_age_range: str | None
    audience_expertise: str          # "bajo" | "medio" | "alto" | "experto"
    register: str                    # "informal_claro" | "neutro" | "formal_claro" | "formal_tecnico" | "persuasivo"
    tone: str | None                 # "reflexivo" | "didactico" | "narrativo" | "persuasivo"
    intervention_level: str          # "minima" | "sutil" | "moderada" | "agresiva"
    preserve_author_voice: bool
    max_rewrite_ratio: float         # 0.0-1.0 (default 0.35)
    max_expansion_ratio: float       # default 1.10
    style_priorities: JSONB          # ["claridad", "fluidez", "cohesion", "precision_lexica"]
    protected_terms: JSONB           # ["apego", "sesgo cognitivo"]
    forbidden_changes: JSONB         # ["simplificar_terminos_tecnicos"]
    lt_disabled_rules: JSONB         # ["WHITESPACE_RULE"]
    target_inflesz_min: int | None
    target_inflesz_max: int | None
    created_at: datetime
    updated_at: datetime
```

**Archivo modificar**: `backend/app/models/document.py`
- Agregar relationship: `profile = relationship("DocumentProfile", uselist=False, back_populates="document", cascade="all, delete-orphan")`

**Archivo modificar**: `backend/app/models/__init__.py`
- Importar `DocumentProfile`

**Verificación**: Levantar stack → las tablas se crean automáticamente sin errores.

---

### 2A.2 — Perfiles predeterminados (10 presets)

**Qué hacer**: Definir los 10 perfiles como constantes Python accesibles por nombre.

**Archivo nuevo**: `backend/app/data/profiles.py`

Definir un dict `PRESETS` con 10 entradas:

| Clave | Nombre UI | Registro | Intervención | Rewrite ratio |
|-------|-----------|----------|-------------|---------------|
| `infantil_6_8` | Infantil (6-8 años) | informal_claro | moderada | 0.40 |
| `infantil_9_12` | Infantil (9-12 años) | neutro_claro | moderada | 0.35 |
| `juvenil` | Juvenil | neutro | moderada | 0.30 |
| `novela_literaria` | Novela literaria | variable | sutil | 0.20 |
| `ensayo` | Ensayo | formal | sutil | 0.25 |
| `psicologia_academica` | Psicología académica | formal_tecnico | minima | 0.15 |
| `psicologia_divulgativa` | Psicología divulgativa | formal_claro | sutil | 0.25 |
| `manual_tecnico` | Manual técnico | tecnico | minima | 0.15 |
| `texto_marketing` | Marketing/Comercial | persuasivo | agresiva | 0.50 |
| `no_ficcion_general` | No ficción general | neutro | moderada | 0.30 |

Cada preset es un dict con TODOS los campos de `DocumentProfile` pre-rellenados. El usuario puede partir de uno y ajustar.

**Verificación**: Import test — `from app.data.profiles import PRESETS; assert len(PRESETS) == 10`

---

### 2A.3 — API de perfiles

**Qué hacer**: Endpoints para crear, leer y actualizar el perfil editorial de un documento.

**Archivo nuevo**: `backend/app/schemas/style_profile.py`
```
StyleProfileCreate   → preset_name + overrides opcionales
StyleProfileResponse → todos los campos del perfil
StyleProfileUpdate   → todos los campos opcionales
```

**Archivo modificar**: `backend/app/api/v1/documents.py` — Agregar 3 endpoints:

```
POST   /documents/{doc_id}/profile   → Crear perfil (desde preset o custom)
GET    /documents/{doc_id}/profile   → Leer perfil actual
PUT    /documents/{doc_id}/profile   → Actualizar perfil
```

Lógica del POST:
1. Si `preset_name` viene → cargar preset desde `PRESETS`, aplicar overrides
2. Si no viene preset → crear perfil vacío con defaults seguros
3. Guardar en DB vinculado al documento

**Verificación desde frontend (manual)**:
1. Subir un documento
2. `curl POST /api/v1/documents/{id}/profile -d '{"preset_name": "ensayo"}'`
3. `curl GET /api/v1/documents/{id}/profile` → retorna perfil completo
4. `curl PUT /api/v1/documents/{id}/profile -d '{"intervention_level": "moderada"}'` → actualiza

---

### 2A.4 — Frontend: selector de perfil al subir documento

**Qué hacer**: Después de subir el DOCX, antes de lanzar el pipeline, mostrar un selector de perfil.

**Cambio de flujo**:
```
ANTES: Upload → pipeline se lanza automáticamente
AHORA: Upload → selector de perfil → confirmar → pipeline se lanza
```

**Archivo nuevo**: `frontend/src/components/ProfileSelector.tsx`

Componente con:
- Grid de 10 cards con nombre + descripción corta de cada preset
- Card seleccionada se resalta con borde krypton
- Botón "Procesar con este perfil" (krypton, prominente)
- Opción "Personalizar" que abre el editor (2A.5)
- Opción "Sin perfil (corrección genérica)" para mantener el flujo MVP1

**Archivo modificar**: `frontend/src/app/page.tsx`

Cambiar el flujo de `DocumentUploader`:
1. `uploadDocument(file)` ya NO llama al pipeline (se necesita nuevo endpoint o separar upload de pipeline)
2. Mostrar `ProfileSelector` con el `doc_id` recibido
3. Al confirmar perfil → `POST /documents/{id}/profile` + `POST /documents/{id}/process` (nuevo endpoint)

**Archivo modificar**: `backend/app/api/v1/documents.py`

- Modificar `POST /upload`: ya NO lanza `process_document_pipeline.delay()`. Solo sube y guarda.
- Nuevo endpoint `POST /documents/{doc_id}/process`: lanza el pipeline Celery. Requiere que el documento exista y tenga status="uploaded".

**Archivo modificar**: `frontend/src/lib/api.ts`
- Agregar tipos `StyleProfile`, `StyleProfileCreate`
- Agregar funciones `createProfile()`, `getProfile()`, `updateProfile()`
- Agregar función `processDocument(id)` para lanzar el pipeline

**Verificación como usuario**:
1. Abrir http://localhost:3000
2. Arrastrar un .docx → aparece el selector de perfiles
3. Seleccionar "Ensayo" → click "Procesar"
4. Ver el documento en la lista con status progresando
5. Verificar en DB que `document_profiles` tiene registro con `preset_name='ensayo'`

---

### 2A.5 — Frontend: editor de perfil (opcional, ajustes finos)

**Archivo nuevo**: `frontend/src/components/ProfileEditor.tsx`

Formulario con:
- **Sección "Audiencia"**: audience_type (dropdown), expertise (slider 4 niveles)
- **Sección "Estilo"**: register (dropdown), tone (dropdown), intervention_level (slider 4 niveles)
- **Sección "Límites"**: max_rewrite_ratio (slider 0-50%), max_expansion_ratio (slider 100-130%)
- **Sección "Protecciones"**: protected_terms (input de tags), preserve_author_voice (toggle)
- **Sección "Prioridades"**: style_priorities (checkboxes ordenables: claridad, fluidez, cohesión, precisión léxica)

Se muestra como modal o panel lateral cuando el usuario clickea "Personalizar" en el ProfileSelector.

**Verificación como usuario**:
1. Upload .docx → ProfileSelector → click "Personalizar"
2. Ajustar intervention_level a "agresiva", agregar término protegido "STYLIA"
3. Click "Guardar y procesar"
4. El perfil se guarda y el pipeline se lanza

---

### 2A.6 — Prompt parametrizado según perfil

**Qué hacer**: El prompt que se envía al LLM ya no es genérico. Se construye dinámicamente según el perfil del documento.

**Archivo nuevo**: `backend/app/services/prompt_builder.py`

Clase `PromptBuilder`:

```python
class PromptBuilder:
    def build_system_prompt(self) -> str:
        """
        System prompt ESTÁTICO (cacheable).
        NO incluir datos dinámicos (ni doc_id, ni timestamps, ni contadores).
        ~800-1200 tokens.
        """
        # Rol + reglas de estilo + formato de salida JSON + ejemplos few-shot
        # + ejemplos negativos + restricciones

    def build_user_prompt(self, profile: DocumentProfile, paragraph: str,
                          context_prev: str | None, section_summary: str | None) -> str:
        """
        User prompt DINÁMICO por párrafo.
        ~200-500 tokens.
        """
        # Brief codificado + política del bloque + texto a corregir + contexto
```

**System prompt estático** (contenido real a implementar):
```
Eres un corrector de estilo profesional en español. Tu trabajo es mejorar la
redacción preservando el significado y la voz del autor.

REGLAS DE CORRECCIÓN:
1. NUNCA cambies el significado del texto
2. Preserva el tono y la voz del autor
3. Los términos protegidos NO se reemplazan por sinónimos
4. Respeta el nivel de intervención indicado
5. Categoriza cada cambio que hagas
...

FORMATO DE RESPUESTA (JSON estricto):
{
  "action": "correct" | "flag" | "skip",
  "corrected_text": "...",
  "changes": [
    {
      "original_fragment": "fragmento exacto original",
      "corrected_fragment": "reemplazo propuesto",
      "category": "redundancia|claridad|registro|cohesion|lexico|estructura|puntuacion|ritmo|muletilla",
      "severity": "critico|importante|sugerencia",
      "explanation": "Razón del cambio en español"
    }
  ],
  "confidence": 0.0-1.0,
  "rewrite_ratio": 0.0-1.0
}

EJEMPLOS CORRECTOS:
[2-3 ejemplos de correcciones bien hechas]

EJEMPLOS INCORRECTOS (NO hacer esto):
[2-3 ejemplos de sobrecorrección o pérdida de voz]
```

**User prompt dinámico** (template):
```
PERFIL: {register} | Intervención: {intervention_level} | Audiencia: {audience_type}
PRIORIDADES: {style_priorities}
PROTEGER: {protected_terms}
SECCIÓN: {section_summary o "N/A"}

CONTEXTO PREVIO:
{último párrafo corregido o "Inicio de documento"}

PÁRRAFO A CORREGIR:
{paragraph_text}
```

**Archivo modificar**: `backend/app/utils/openai_client.py`

- Separar `correct_text_style()` en:
  - Recibe el system prompt completo (ya construido, para cacheo)
  - Recibe el user prompt ya construido
  - Ya no construye prompts internamente
- Agregar parámetros para schema de respuesta estructurado

**Archivo modificar**: `backend/app/services/correction.py`

- `correct_docx_sync()` ahora:
  1. Lee el perfil del documento de la DB (o lo recibe como parámetro)
  2. Instancia `PromptBuilder`
  3. Construye el system prompt UNA VEZ (se reutiliza para todos los párrafos)
  4. Por cada párrafo: construye user prompt dinámico con `PromptBuilder`
  5. Parsea la respuesta JSON estructurada (action, changes, confidence, etc.)

**Verificación como usuario**:
1. Subir documento con perfil "infantil_6_8"
2. Subir MISMO documento con perfil "psicologia_academica"
3. Comparar correcciones: el perfil infantil debe producir cambios más agresivos/simplificadores
4. Las correcciones deben tener `category` y `explanation` visibles

---

### 2A.7 — Campos enriquecidos en patches (categoría, severidad, explicación)

**Archivo modificar**: `backend/app/models/patch.py`

Agregar columnas:
```python
category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # coherencia|cohesion|lexico|registro|claridad|redundancia|estructura|puntuacion|ritmo|muletilla
severity: Mapped[str | None] = mapped_column(String(15), nullable=True)
    # critico|importante|sugerencia
explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
rewrite_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
pass_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 1=LanguageTool, 2=léxica, 3=estilística
model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # "gpt-4o-mini", "claude-sonnet-4-5", "languagetool"
```

**Archivo modificar**: `backend/app/schemas/patch.py`

Agregar a `PatchListItem` y `PatchDetail`:
```python
category: str | None = None
severity: str | None = None
explanation: str | None = None
confidence: float | None = None
rewrite_ratio: float | None = None
pass_number: int | None = None
model_used: str | None = None
```

**Archivo modificar**: `backend/app/api/v1/documents.py` → `list_corrections()`
- Pasar los nuevos campos al response

**Archivo modificar**: `backend/app/services/correction.py` → `correct_docx_sync()`
- Al parsear la respuesta JSON del LLM, extraer `changes[]` y crear un Patch por cada `change` (o un Patch con todos los changes en operations_json — decidir según granularidad deseada)
- Popular `category`, `severity`, `explanation` desde la respuesta

**Verificación en DB**: Después de procesar un documento, `SELECT category, severity, explanation FROM patches WHERE doc_id=X` debe retornar valores no-null.

---

### 2A.8 — Frontend: correcciones con categoría y explicación

**Archivo modificar**: `frontend/src/lib/api.ts`
- Extender `PatchListItem` con `category`, `severity`, `explanation`, `confidence`

**Archivo modificar**: `frontend/src/components/CorrectionHistory.tsx`

Cambios:
1. **Filtro por categoría**: Además de filtrar por fuente (LT/LLM), agregar dropdown de categoría (redundancia, claridad, léxico, etc.)
2. **Filtro por severidad**: Toggles para critico/importante/sugerencia
3. **Badge de categoría**: En cada card, mostrar badge de color según categoría
4. **Explicación visible**: En la card expandida, mostrar el campo `explanation` como texto explicativo
5. **Indicador de confianza**: Barra sutil de `confidence` (0-100%)

Colores sugeridos por categoría:
```
redundancia   → amber
claridad      → blue
léxico        → purple
registro      → pink
cohesión      → cyan
estructura    → orange
puntuación    → gray
ritmo         → indigo
muletilla     → yellow
```

Colores por severidad:
```
crítico     → red badge
importante  → amber badge
sugerencia  → plomo/gray badge
```

**Verificación como usuario**:
1. Abrir documento completado → tab "Correcciones"
2. Ver que cada corrección tiene badge de categoría (ej: "redundancia" en amber)
3. Expandir corrección → ver explicación del cambio
4. Filtrar por "redundancia" → solo aparecen esas
5. Filtrar por "crítico" → solo aparecen críticas

---

### Checkpoint de FASE 2A

Al completar 2A, el usuario puede:
- [x] Subir documento y elegir perfil editorial (o personalizar)
- [x] Ver correcciones categorizadas con explicación
- [x] Filtrar correcciones por categoría y severidad
- [x] El mismo documento con perfiles diferentes produce correcciones diferentes
- [x] Descargar DOCX/PDF corregido como antes

Lo que NO cambió aún:
- El pipeline sigue siendo LanguageTool → 1 pasada LLM (no multi-pasada)
- No hay análisis editorial automático (Etapa C)
- No hay quality gates
- No hay router de complejidad

---

## FASE 2B — Etapa C (análisis editorial) + contexto jerárquico

**Objetivo**: Antes de corregir, el sistema analiza el documento como un todo. El LLM recibe contexto semántico (resumen de sección, términos activos) en vez de solo "3 párrafos anteriores crudos".

### 2B.1 — Modelo de datos para análisis editorial

**Archivo nuevo**: `backend/app/models/section_summary.py`
```python
class SectionSummary(Base):
    __tablename__ = "section_summaries"

    id: UUID (PK)
    doc_id: UUID (FK → documents.id)
    section_index: int
    section_title: str | None
    start_paragraph: int          # índice del primer párrafo
    end_paragraph: int            # índice del último párrafo
    summary_text: str             # ~50 palabras
    topic: str                    # tema principal
    local_tone: str | None
    active_terms: JSONB           # términos técnicos activos en esta sección
    transition_from_previous: str | None  # cómo conecta con la sección anterior
```

**Archivo nuevo**: `backend/app/models/term_registry.py`
```python
class TermRegistry(Base):
    __tablename__ = "term_registry"

    id: UUID (PK)
    doc_id: UUID (FK → documents.id)
    term: str
    normalized_form: str
    frequency: int
    first_occurrence_paragraph: int
    is_protected: bool
    decision: str                 # "use_as_is" | "normalize_to"
```

**Archivo modificar**: `backend/app/models/block.py`
- Agregar: `paragraph_type: str | None` (titulo, narrativo, explicacion, dialogo, cita, tabla, lista, etc.)
- Agregar: `requires_llm: bool = True`
- Agregar: `section_id: UUID | None` (FK → section_summaries.id)

---

### 2B.2 — Servicio de análisis editorial (Etapa C)

**Archivo nuevo**: `backend/app/services/analysis.py`

```python
def analyze_document_sync(doc_id: str, docx_uri: str, profile: DocumentProfile) -> dict:
    """
    Etapa C: Análisis editorial del documento.
    Se ejecuta UNA VEZ antes de cualquier corrección.

    Sub-etapas:
      C.1: Inferencia de género/audiencia (si no hay perfil explícito)
      C.2: Completar/validar el style profile
      C.3: Generar resúmenes por sección
      C.4: Extraer glosario y términos protegidos
      C.5: Clasificar párrafos por tipo y asignar política

    Returns: {sections, terms, paragraph_classifications, inferred_profile_updates}
    """
```

**C.1 + C.2: Inferencia y validación de perfil**

Extraer muestras del documento:
- Primeros 5 párrafos del cuerpo
- Último párrafo de cada "sección" (detectar secciones por headings/estilos)
- Títulos si los hay

Enviar a GPT-4o-mini (una sola llamada, barata):
```
Analiza este extracto de documento y responde en JSON:
{
  "genre": "...",
  "audience": "...",
  "register": "...",
  "key_terms": ["...", "..."],
  "suggested_intervention": "sutil|moderada|agresiva",
  "spanish_variant": "es-ES|es-MX|es-CO|..."
}
```

Si el usuario YA eligió un perfil → usar el perfil del usuario, solo completar lo que no definió.
Si el usuario no eligió → usar la inferencia como default.

**C.3: Resúmenes por sección**

Detectar secciones (heurística):
- Párrafos con estilo "Heading 1/2/3" en python-docx → nuevo section
- Si no hay headings → cada N párrafos es una sección (o detectar cambio de tema)

Por cada sección → una llamada a GPT-4o-mini:
```
Resume esta sección en ~50 palabras. Indica:
- Tema principal
- Términos técnicos activos
- Tono local
- Cómo conecta con la sección anterior
```

**C.4: Glosario automático**

Extraer términos técnicos recurrentes (frecuencia > 2 en el documento):
- Puede ser heurístico (n-gramas con capital o poco frecuentes en español general)
- O con una llamada LLM sobre el texto completo/resúmenes

Combinar con `protected_terms` del perfil del usuario.

Guardar en `term_registry`.

**C.5: Clasificación de párrafos**

Para cada párrafo, asignar `paragraph_type`:
- **Heurístico** (sin LLM, rápido):
  - Empieza con `—` o `"` → `dialogo`
  - Es un heading (por estilo python-docx) → `titulo` / `subtitulo`
  - Dentro de tabla → `celda_tabla`
  - Dentro de header/footer → `encabezado` / `footer`
  - Empieza con `•`, `-`, número → `lista`
  - Es una cita (sangría, cursiva, comillas) → `cita`
  - Tiene muchos términos técnicos del glosario → `explicacion_tecnica`
  - Default → `narrativo`

- **Con LLM** (refinamiento, solo si necesario):
  - Enviar batch de párrafos dudosos a GPT-4o-mini para clasificación

Actualizar `blocks.paragraph_type` y `blocks.requires_llm` en la DB.

---

### 2B.3 — Integrar Etapa C en el pipeline Celery

**Archivo modificar**: `backend/app/workers/tasks_pipeline.py`

Insertar entre Etapa B y Etapa D:

```python
# =============================================
# ETAPA C: ANÁLISIS EDITORIAL
# =============================================
_update_document_status(db, doc_id, "analyzing")  # nuevo status
logger.info(f"[Etapa C] Analizando documento...")

# Cargar perfil del documento (o crear default si no existe)
profile = db.execute(
    select(DocumentProfile).where(DocumentProfile.doc_id == doc_id)
).scalar_one_or_none()

if not profile:
    profile = DocumentProfile(doc_id=doc_id, source="inferred", **DEFAULT_PROFILE)
    db.add(profile)
    db.commit()

analysis_result = analyze_document_sync(
    doc_id=str(doc_id),
    docx_uri=doc.source_uri,
    profile=profile,
)

# Guardar secciones, términos, clasificaciones en DB
# Actualizar perfil si se infirieron campos faltantes
```

**Archivo modificar**: `backend/app/models/document.py`
- Actualizar comment del status para incluir "analyzing":
  `uploaded → converting → extracting → analyzing → correcting → rendering → completed → failed`

**Archivo modificar**: `frontend/src/components/PipelineFlow.tsx`
- Agregar etapa "Analizando" entre "Extrayendo" y "Corrigiendo"
- Nuevo icono y descripción: "Análisis editorial: género, audiencia, terminología"

---

### 2B.4 — Contexto jerárquico en corrección

**Archivo modificar**: `backend/app/services/correction.py` → `correct_docx_sync()`

Cambiar de:
```python
context_blocks=corrected_context[-3:]
```

A:
```python
# Construir contexto jerárquico
section = _get_section_for_paragraph(db, doc_id, paragraph_index)
section_summary = section.summary_text if section else None
active_terms = section.active_terms if section else []
previous_corrected = corrected_context[-1] if corrected_context else None

user_prompt = prompt_builder.build_user_prompt(
    profile=profile,
    paragraph=text,
    context_prev=previous_corrected,
    section_summary=section_summary,
    active_terms=active_terms,
    paragraph_type=paragraph_type,
)
```

**Verificación como usuario**:
1. Subir un documento largo (>10 páginas) con perfil "ensayo"
2. Ver en tab "Pipeline" la nueva etapa "Analizando" completarse
3. Ver que las correcciones mencionan contexto de sección en `explanation`
4. Verificar que términos técnicos NO fueron reemplazados por sinónimos

---

### 2B.5 — API y frontend para ver análisis editorial

**Archivo modificar**: `backend/app/api/v1/documents.py`
- Nuevo endpoint `GET /documents/{doc_id}/analysis`:
  - Retorna: perfil inferido, secciones detectadas, glosario extraído, clasificación de párrafos

**Archivo nuevo**: `frontend/src/components/AnalysisView.tsx`
- Muestra el resultado del análisis editorial:
  - Card "Perfil detectado": género, audiencia, registro, tono
  - Card "Secciones": lista de secciones con resumen
  - Card "Glosario": términos protegidos con frecuencia
  - Card "Tipos de párrafo": distribución (N narrativos, N técnicos, N diálogos, etc.)

**Archivo modificar**: `frontend/src/app/documents/[id]/page.tsx`
- Agregar nuevo tab "Análisis" entre "Pipeline" y "Correcciones"

**Verificación como usuario**:
1. Subir documento y procesarlo
2. Ir a detalle → tab "Análisis"
3. Ver perfil detectado (género, audiencia)
4. Ver lista de secciones con resúmenes
5. Ver glosario de términos encontrados
6. Ver distribución de tipos de párrafo

---

### Checkpoint de FASE 2B

Al completar 2B, el usuario puede:
- [x] Todo lo de 2A
- [x] Ver una nueva etapa "Analizando" en el pipeline
- [x] Ver el análisis editorial del documento (perfil, secciones, glosario)
- [x] Las correcciones usan contexto semántico (no 3 párrafos crudos)
- [x] Los términos técnicos se preservan automáticamente
- [x] Los párrafos tipo "cita" o "diálogo" se corrigen diferente a los narrativos

---

## FASE 2C — Router de complejidad + quality gates

**Objetivo**: No todos los párrafos van al LLM. Los que van, se validan post-corrección. Ahorro de costos y mejor calidad.

### 2C.1 — Router de complejidad

**Archivo nuevo**: `backend/app/services/complexity_router.py`

```python
class CorrectionRoute(Enum):
    SKIP = "skip"         # No enviar al LLM
    CHEAP = "cheap"       # GPT-4o-mini solo
    EDITORIAL = "editorial"  # Modelo potente (GPT-4o / Claude Sonnet)

def route_paragraph(
    text: str,
    paragraph_type: str,
    lt_matches_count: int,
    profile: DocumentProfile,
    is_section_transition: bool,
    section_position: str,  # "first" | "middle" | "last"
) -> CorrectionRoute:
    """
    Decide qué ruta toma un párrafo.
    """
    # Skip LLM si:
    # - paragraph_type en ("titulo", "subtitulo", "encabezado", "footer", "cita")
    # - lt_matches_count == 0 AND texto corto (<50 chars) AND no es transición

    # Ruta barata si:
    # - paragraph_type en ("celda_tabla", "lista", "pie_imagen")
    # - Texto limpio en LT + sintaxis simple
    # - intervention_level == "minima"

    # Ruta editorial si:
    # - Es transición entre secciones
    # - Tiene subordinadas anidadas
    # - Es primer/último párrafo de sección
    # - paragraph_type == "narrativo" y texto largo
    # - Tiene riesgo tonal (detectable por heurísticas)
```

**Archivo modificar**: `backend/app/services/correction.py`

En `correct_docx_sync()`, antes de llamar al LLM:
```python
route = complexity_router.route_paragraph(
    text=text,
    paragraph_type=block.paragraph_type,
    lt_matches_count=len(lt_result.operations),
    profile=profile,
    is_section_transition=...,
    section_position=...,
)

if route == CorrectionRoute.SKIP:
    # Solo aplicar LanguageTool, no enviar al LLM
    pass
elif route == CorrectionRoute.CHEAP:
    # Usar GPT-4o-mini
    pass
elif route == CorrectionRoute.EDITORIAL:
    # Usar modelo potente (configurable)
    pass
```

**Archivo modificar**: `backend/app/config.py`
- Agregar: `editorial_model: str = "gpt-4o-mini"` (se puede cambiar a Claude Sonnet)
- Agregar: `cheap_model: str = "gpt-4o-mini"`

**Verificación**: Comparar logs antes/después — se debe ver que ~20-40% de párrafos hacen skip del LLM.

---

### 2C.2 — Quality gates

**Archivo nuevo**: `backend/app/services/quality_gates.py`

```python
@dataclass
class GateResult:
    passed: bool
    gate_name: str
    value: float
    threshold: float
    message: str

def validate_correction(
    original: str,
    corrected: str,
    profile: DocumentProfile,
    protected_terms: list[str],
) -> list[GateResult]:
    """
    Ejecuta todos los quality gates sobre una corrección.
    Retorna lista de resultados. Si alguno falla → descartar o flag.
    """

def gate_expansion_ratio(original: str, corrected: str, max_ratio: float) -> GateResult:
    """len(corrected) / len(original) <= max_ratio"""

def gate_rewrite_ratio(original: str, corrected: str, max_ratio: float) -> GateResult:
    """Distancia de edición normalizada <= max_ratio"""
    # Levenshtein(original, corrected) / max(len(original), len(corrected))

def gate_protected_terms(corrected: str, terms: list[str]) -> GateResult:
    """Todos los protected_terms deben estar presentes en corrected"""

def gate_not_empty(corrected: str) -> GateResult:
    """El texto corregido no debe estar vacío"""

def gate_language_preserved(original: str, corrected: str) -> GateResult:
    """El idioma del texto no debe cambiar (heurístico rápido)"""
```

Gates avanzados (Fase 2D+):
- `gate_semantic_similarity()` — BERTScore F1 > 0.85
- `gate_nli_consistency()` — No contradicción entre original y corregido

**Archivo modificar**: `backend/app/services/correction.py`

Después de recibir la respuesta del LLM:
```python
gates = quality_gates.validate_correction(
    original=text,
    corrected=chatgpt_text,
    profile=profile,
    protected_terms=protected_terms,
)

failed_gates = [g for g in gates if not g.passed]
if any(g.gate_name in ("expansion_ratio", "protected_terms") for g in failed_gates):
    # Gate crítico falló → descartar corrección, usar original
    final_text = post_lt_text
    source = "languagetool"
elif failed_gates:
    # Gate no-crítico → marcar como flag para revisión
    review_status = "manual_review"
```

**Verificación como usuario**:
1. Subir documento con perfil que tiene `max_rewrite_ratio: 0.15` (muy conservador)
2. Verificar que correcciones agresivas del LLM se descartaron (review_status muestra razón)
3. Subir documento con términos protegidos → verificar que NO se reemplazaron

---

### 2C.3 — Frontend: indicadores de quality gates

**Archivo modificar**: `frontend/src/components/CorrectionHistory.tsx`

En cada CorrectionCard expandida, agregar sección "Control de calidad":
- Indicador de rewrite_ratio (barra de progreso, rojo si >threshold)
- Indicador de confidence del LLM (barra)
- Si review_status == "manual_review" → badge naranja "Requiere revisión"
- Si review_status == "auto_accepted" → badge verde "Validado"

**Verificación como usuario**:
1. Abrir correcciones de un documento
2. Ver barras de rewrite_ratio y confidence
3. Ver badges de "Validado" vs "Requiere revisión"

---

### Checkpoint de FASE 2C

Al completar 2C, el usuario puede:
- [x] Todo lo de 2A + 2B
- [x] El sistema es más rápido (skip LLM en párrafos limpios)
- [x] Las correcciones excesivas se rechazan automáticamente
- [x] Los términos protegidos nunca se tocan
- [x] Indicadores de calidad visibles en cada corrección
- [x] Correcciones dudosas marcadas para revisión

---

## FASE 2D — Revisión humana + track changes

**Objetivo**: El usuario puede aceptar/rechazar/editar correcciones individuales. El DOCX final incluye track changes.

### 2D.1 — Endpoints de revisión

**Archivo modificar**: `backend/app/api/v1/documents.py`

```
PUT  /documents/{doc_id}/corrections/{patch_id}/review
     body: { "action": "accept" | "reject" | "edit", "edited_text": "..." }
     → Actualiza review_status y opcionalmente corrected_text

POST /documents/{doc_id}/apply-reviewed
     → Re-renderiza el DOCX aplicando solo patches aceptados/editados
```

**Archivo modificar**: `backend/app/services/rendering.py`
- `render_docx_first_sync()` debe filtrar: solo aplicar patches con `review_status in ("accepted", "auto_accepted")` y `applied=False`

---

### 2D.2 — Frontend: interfaz de revisión

**Archivo nuevo**: `frontend/src/components/ReviewInterface.tsx`

Componente que muestra cada corrección con 3 botones:
- **Aceptar** (✓ verde) → `PUT .../review` con action="accept"
- **Rechazar** (✕ rojo) → `PUT .../review` con action="reject"
- **Editar** (✎ amarillo) → abre textarea editable, guarda con action="edit"

Contadores en header:
- "12 por revisar | 8 aceptadas | 2 rechazadas | 1 editada"

Botón "Aplicar y descargar" → `POST /documents/{id}/apply-reviewed` → descargar resultado.

---

### 2D.3 — Track changes en DOCX

**Dependencia nueva**: `python-redlines` (pip install python-redlines)

**Archivo modificar**: `backend/app/services/rendering.py`

Agregar función alternativa:
```python
def render_docx_with_track_changes(docx_path: str, patches: list[dict]) -> str:
    """
    Genera DOCX con tracked changes (marcas de revisión de Word).
    Usa python-redlines para comparar original vs corregido.
    """
```

**Archivo modificar**: `backend/app/api/v1/documents.py`
- Nuevo endpoint: `GET /documents/{doc_id}/download/docx-tracked`
  - Retorna DOCX con track changes (para que el usuario revise en Word)

**Verificación como usuario**:
1. Subir documento → procesarlo
2. Ir a tab "Revisión" → aceptar algunas, rechazar otras, editar una
3. Click "Aplicar y descargar"
4. Abrir DOCX en Word → solo las correcciones aceptadas/editadas están aplicadas
5. Descargar versión con track changes → abrir en Word → ver marcas de revisión

---

### Checkpoint de FASE 2D

Al completar 2D, el usuario puede:
- [x] Todo lo anterior
- [x] Revisar cada corrección individualmente (aceptar/rechazar/editar)
- [x] Descargar DOCX con solo las correcciones aceptadas
- [x] Descargar DOCX con track changes para revisar en Word
- [x] El sistema mantiene historial de decisiones del usuario

---

## FASE 2E — Multi-pasada + multi-modelo (optimización)

**Objetivo**: Separar corrección léxica de corrección estilística. Usar modelos diferentes por pasada. Optimizar costos con caching.

### 2E.1 — Pasada léxica separada (D.2)

**Archivo modificar**: `backend/app/services/correction.py`

Separar la corrección en dos pasadas:

```python
# PASADA D.2: LÉXICA (modelo barato: GPT-4o-mini)
# Busca: muletillas, redundancias, repeticiones cercanas, pleonasmos
lexical_prompt = prompt_builder.build_lexical_prompt(text, profile)
lexical_result = openai_client.correct(model="gpt-4o-mini", ...)

# PASADA D.3: ESTILÍSTICA (modelo potente: configurable)
# Busca: coherencia, tono, registro, flujo, estructura oracional
style_prompt = prompt_builder.build_style_prompt(
    text=lexical_result.corrected_text,  # input de D.2
    profile=profile,
    context=...,
)
style_result = openai_client.correct(model=settings.editorial_model, ...)
```

### 2E.2 — Soporte multi-proveedor (OpenAI + Anthropic)

**Archivo modificar**: `backend/app/utils/openai_client.py`

Refactorizar a una interfaz agnóstica:
```python
class LLMClient:
    def correct(self, model: str, system_prompt: str, user_prompt: str) -> dict:
        if model.startswith("claude"):
            return self._call_anthropic(model, system_prompt, user_prompt)
        else:
            return self._call_openai(model, system_prompt, user_prompt)
```

**Archivo modificar**: `backend/app/config.py`
- Agregar: `anthropic_api_key: str = ""`
- Agregar: `editorial_model: str = "gpt-4o-mini"` (configurable a "claude-sonnet-4-5-20250514")

**Dependencia nueva**: `anthropic` (pip install anthropic)

### 2E.3 — Prompt caching

**Archivo modificar**: `backend/app/services/prompt_builder.py`

Asegurar que el system prompt:
- Sea >1024 tokens (requisito OpenAI para cache)
- NO contenga datos dinámicos
- Sea idéntico en todas las llamadas del mismo documento

Para Anthropic:
- Usar `cache_control: {"type": "ephemeral"}` en el system message
- Las llamadas dentro de 5 minutos reutilizan el cache

### 2E.4 — Métricas INFLESZ post-corrección

**Dependencia nueva**: `legibilidad` (pip install legibilidad)

**Archivo modificar**: `backend/app/services/quality_gates.py`

```python
def gate_readability_inflesz(corrected: str, target_min: int, target_max: int) -> GateResult:
    """Verifica que el INFLESZ del texto corregido esté en el rango objetivo."""
    from legibilidad import inflesz
    score = inflesz(corrected)
    return GateResult(
        passed=target_min <= score <= target_max,
        value=score,
        ...
    )
```

---

### Checkpoint de FASE 2E

Al completar 2E:
- [x] Corrección léxica y estilística son pasadas separadas, auditables
- [x] Se puede usar Claude Sonnet para la pasada estilística
- [x] El prompt caching reduce costos ~50-90% por documento
- [x] Métricas de legibilidad INFLESZ verifican que el texto mantiene el nivel

---

## Resumen de dependencias nuevas por fase

| Fase | Dependencia Python | Dependencia Frontend |
|------|-------------------|---------------------|
| 2A | ninguna | ninguna |
| 2B | ninguna | ninguna |
| 2C | `python-Levenshtein` (para rewrite ratio) | ninguna |
| 2D | `python-redlines` | ninguna |
| 2E | `anthropic`, `legibilidad` | ninguna |

---

## Resumen de migraciones de DB por fase

Como el MVP usa `Base.metadata.create_all()` (auto-create), agregar columnas a modelos existentes requiere recrear las tablas o usar ALTER TABLE manual. Opciones:

**Opción A (MVP)**: Borrar y recrear la DB en cada despliegue (perder datos — OK para desarrollo)
```bash
docker-compose down -v  # borra volúmenes
docker-compose up --build
```

**Opción B (Recomendada para Fase 2B+)**: Implementar Alembic
```bash
cd backend
alembic init alembic
alembic revision --autogenerate -m "add style profiles and analysis tables"
alembic upgrade head
```

---

## Orden recomendado de implementación (por archivo)

### Sprint 1 (Fase 2A — cimiento)
1. `backend/app/models/style_profile.py` (crear)
2. `backend/app/data/profiles.py` (crear)
3. `backend/app/schemas/style_profile.py` (crear)
4. `backend/app/models/document.py` (agregar relationship)
5. `backend/app/models/patch.py` (agregar 7 columnas)
6. `backend/app/schemas/patch.py` (agregar campos)
7. `backend/app/api/v1/documents.py` (endpoints profile + separar upload/process)
8. `backend/app/services/prompt_builder.py` (crear)
9. `backend/app/utils/openai_client.py` (refactorizar prompts)
10. `backend/app/services/correction.py` (usar prompt_builder + profile)
11. `frontend/src/lib/api.ts` (tipos + funciones profile)
12. `frontend/src/components/ProfileSelector.tsx` (crear)
13. `frontend/src/app/page.tsx` (integrar ProfileSelector)
14. `frontend/src/components/CorrectionHistory.tsx` (categorías + explicación)

### Sprint 2 (Fase 2B — análisis)
15. `backend/app/models/section_summary.py` (crear)
16. `backend/app/models/term_registry.py` (crear)
17. `backend/app/models/block.py` (agregar paragraph_type)
18. `backend/app/services/analysis.py` (crear)
19. `backend/app/workers/tasks_pipeline.py` (insertar Etapa C)
20. `frontend/src/components/PipelineFlow.tsx` (agregar etapa)
21. `frontend/src/components/AnalysisView.tsx` (crear)
22. `backend/app/services/correction.py` (contexto jerárquico)

### Sprint 3 (Fase 2C — calidad)
23. `backend/app/services/complexity_router.py` (crear)
24. `backend/app/services/quality_gates.py` (crear)
25. `backend/app/services/correction.py` (integrar router + gates)
26. `frontend/src/components/CorrectionHistory.tsx` (indicadores QA)

### Sprint 4 (Fase 2D — revisión humana)
27. `backend/app/api/v1/documents.py` (endpoints review)
28. `backend/app/services/rendering.py` (filtrar por review_status)
29. `frontend/src/components/ReviewInterface.tsx` (crear)
30. `backend/requirements.txt` (agregar python-redlines)
31. `backend/app/services/rendering.py` (track changes)

### Sprint 5 (Fase 2E — optimización)
32. `backend/app/utils/openai_client.py` (multi-proveedor)
33. `backend/app/services/correction.py` (multi-pasada)
34. `backend/app/config.py` (settings multi-modelo)
35. `backend/requirements.txt` (agregar anthropic, legibilidad)
36. `backend/app/services/quality_gates.py` (INFLESZ gate)
