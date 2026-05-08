# Plan — Renovación arquitectónica Stylia (Hoja de Estilo Editorial Dinámica)

## Contexto

El sistema MVP 2 funciona, pero el LLM corrige sin visión macroestructural, LanguageTool destruye términos técnicos globales por falta de wiring, no existen reglas personalizadas de sustitución/normalización/idiolecto, y el frontend no expone el ADN editorial al usuario. Este plan renueva el motor de perfiles, el pipeline de corrección y la UI para que Stylia se comporte como un corrector editorial profesional con reglas de usuario explícitas, fases de corrección controlables y revisión humana de la ficha editorial antes de procesar.

**Decisiones de alcance acordadas con el usuario:**
- Plan completo, dividido en sprints priorizados.
- Idiolect protections: solo input manual del usuario (no detección automática).
- Macro-corrección: sprint final, opt-in por perfil (default `none`).
- **El plan debe garantizar que los cambios apliquen al 100% del documento sin importar tamaño** — tanto en flujo monolítico (documentos pequeños/medianos) como en flujo paralelo por lotes (documentos grandes). Sección 7.10 dedicada a esta compatibilidad.

---

## 7.1 Diagnóstico confirmado en código

| # | Problema | Estado | Causa raíz precisa (file:line) |
|---|----------|--------|--------------------------------|
| P1 | LLM sin visión macro | ✅ confirmado con matiz | `correction.py:646` pasa `corrected_context[-3:]` pero `prompt_builder.py:236-256` solo consume `corrected_meta[-1]`. La ventana existe; el prompt no la usa. |
| P2 | LT destruye términos técnicos | ✅ confirmado | `engine_router.decide_engines` (línea 52) **acepta** `term_registry`; `correction.py:273-278` **no lo pasa**. Falta wiring de `DocumentGlobalContext.protected_globals_json`. |
| P3 | Sin reglas personalizadas | ✅ confirmado | Ninguno de `substitution_rules`, `entity_normalizations`, `idiolect_protections`, `register_constraints`, `macro_correction_level`, `correction_phases` existe en `style_profile.py`. |
| P4 | Frontend no expone ADN | ✅ confirmado | `AnalysisView.tsx:29-46` muestra `InferredProfile` pero NO `GlobalDocumentContext`. No hay vista pre-procesamiento. |
| P5 | Sin distinción macro/micro | ✅ confirmado | `complexity_router.py:18-21` solo SKIP/CHEAP/EDITORIAL. Mismo `build_user_prompt` para todas. |
| P6 | Pasada 2 sin reglas del perfil | ✅ confirmado con matiz | `audit_pass.py:19` recibe `global_context` (que sí incluye `protected_globals_json`). Lo que NO llega son las reglas del usuario (substitutions, idiolectos, register constraints) — porque no existen aún. |
| P7 | Páginas fragmentadas | ✅ confirmado | `rendering.py:_apply_text_with_page_break` divide por fracción + busca espacio en ventana de 30 chars. Heurística sin consciencia semántica. |

**Problemas adicionales detectados durante exploración:**

| # | Problema | Evidencia |
|---|----------|-----------|
| P8 | `analysis.py` no detecta idiolectos por personaje | `analysis.py:702-854` solo extrae voz dominante global y términos genéricos. No segmenta por personaje. → Refuerza decisión de que idiolect_protections sea solo input manual. |
| P9 | ADN editorial no entra a Pasada 1 | `correction.py` carga `global_context` (línea 522) pero `build_user_prompt` (Pasada 1) NO invoca `build_global_context_block`. Solo Pasada 2 ve el ADN (`prompt_builder.py:364`). |
| P10 | `register_constraints` requiere validación específica | No existen heurísticas para detectar lenguaje inclusivo / anglicismos. Implementación combinará: instrucciones en prompt + gate ligero post-corrección. |
| P11 | `corrected_context` son strings sin metadata | `correction.py:555` lo declara como `list[str]`. Para macro-corrección hace falta estructura tipada con sección, registro local, tipo de párrafo. |

---

## 7.2 Orden de implementación (sprints)

| Sprint | Objetivo | Resuelve | Riesgo | Complejidad | Dependencias |
|--------|----------|----------|--------|-------------|--------------|
| **S0** | Migración BD + schemas Pydantic + tipos TS | base para S1-S5 | bajo | pequeño | — |
| **S1** | Wiring de `protected_globals_json` a LT y a Pasada 1 | P2, P9 | bajo | pequeño | S0 |
| **S2** | Sustitution rules, entity normalizations, idiolect protections, register constraints (Fase 0 + propagación a prompts) | P3, P6, P10 | medio | grande | S0, S1 |
| **S3** | Ventana de contexto enriquecida + ADN en Pasada 1 + ficha editorial unificada | P1, P11 | medio | mediano | S0, S2 |
| **S4** | Frontend: Editorial Profile Panel + flujo de revisión pre-procesamiento + simulate-impact | P4 | medio | grande | S0, S2, S3 |
| **S5** | Macro-corrección **como pase post-merge** (no por lote) + router macro/micro + opcional mejora de page-break | P5, P7 | alto | grande | S2, S3, S4 |

**Por qué este orden:**
- S0 desbloquea todo lo demás sin tocar lógica.
- **S1 es la mayor relación valor/esfuerzo** del plan: ya están las APIs (`engine_router` acepta `term_registry`); falta solo conectar `DocumentGlobalContext.protected_globals_json` y agregar el bloque global al prompt de Pasada 1. Resuelve "STYLIA → ITALIA" inmediatamente.
- S2 introduce el motor de reglas personalizadas (lo más solicitado por el usuario en sección 4.A) sin tocar el frontend todavía.
- S3 cierra los bordes de prompts (Pasada 1 con ADN, Pasada 2 con perfil completo) y tipifica el contexto previo.
- S4 traduce S2-S3 en UI usable. Se puede empezar en paralelo a S2-S3 para los componentes que no dependen de endpoints, pero el flujo end-to-end se cierra al final.
- S5 es opt-in y experimental. Se difiere para después de validar S1-S4 en producción.

**Nota cross-sprint sobre paralelización:** Cada sprint debe verificarse en ambos modos (monolítico y paralelo por lotes). La sección 7.10 detalla cómo cada cambio se propaga al modo paralelo y qué cambios de arquitectura son necesarios (especialmente en S5).

---

## 7.3 Diseño de schema BD

Todas las migraciones se agregan al bloque `lifespan` de `backend/app/main.py` siguiendo el patrón `ALTER TABLE IF NOT EXISTS ADD COLUMN`. Ninguna columna existente se elimina.

### Sprint 0 — `document_profiles`

```sql
ALTER TABLE document_profiles ADD COLUMN IF NOT EXISTS substitution_rules JSONB DEFAULT '[]'::jsonb;
ALTER TABLE document_profiles ADD COLUMN IF NOT EXISTS entity_normalizations JSONB DEFAULT '[]'::jsonb;
ALTER TABLE document_profiles ADD COLUMN IF NOT EXISTS idiolect_protections JSONB DEFAULT '[]'::jsonb;
ALTER TABLE document_profiles ADD COLUMN IF NOT EXISTS register_constraints JSONB DEFAULT '[]'::jsonb;
ALTER TABLE document_profiles ADD COLUMN IF NOT EXISTS macro_correction_level VARCHAR(10) DEFAULT 'none';
ALTER TABLE document_profiles ADD COLUMN IF NOT EXISTS correction_phases JSONB DEFAULT '["lt", "llm_micro", "audit"]'::jsonb;

CREATE INDEX IF NOT EXISTS ix_document_profiles_macro_level ON document_profiles(macro_correction_level);
```

**Estructuras JSONB esperadas:**

```json
substitution_rules: [
  {"id": "uuid", "find": "los niños", "replace": "los y las niñas",
   "case_sensitive": false, "is_regex": false, "scope": "all|narrative|dialogue", "enabled": true}
]
entity_normalizations: [
  {"id": "uuid", "generic": "la institución", "canonical": "Universidad Nacional de Colombia",
   "aliases": ["la universidad", "la UNal"], "enabled": true}
]
idiolect_protections: [
  {"id": "uuid", "scope": "character:Juan|author_voice|fragment", "description": "habla coloquial costeña",
   "examples": ["¡Ajá pues!", "Ombe..."], "enabled": true}
]
register_constraints: ["lenguaje_inclusivo", "sin_anglicismos", "tuteo_exclusivo", "sin_imperativo", "voseo_rioplatense"]
correction_phases: ["substitutions", "lt", "llm_micro", "llm_macro", "audit"]  // orden controlable
macro_correction_level: "none" | "light" | "full"
```

**Restricciones:** ninguna restricción FK; validación de estructura en schema Pydantic. `CHECK (macro_correction_level IN ('none','light','full'))` opcional pero NO necesaria — Pydantic lo valida.

### Sprint 0 — `patches`

```sql
ALTER TABLE patches ADD COLUMN IF NOT EXISTS correction_phase VARCHAR(20);
ALTER TABLE patches ADD COLUMN IF NOT EXISTS substitution_rule_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS ix_patches_correction_phase ON patches(correction_phase);
```

**Valores de `correction_phase`:** `substitution | lt | llm_micro | llm_macro | audit | manual`. Es complementario a `source` (existente) y `route_taken` (existente).

### Sprint 5 — opcional, para tracking de coste macro

```sql
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS phase VARCHAR(20);
```

---

## 7.4 Diseño de API REST

Todos los endpoints nuevos siguen las convenciones existentes en `backend/app/api/v1/documents.py`. Los existentes no cambian su firma.

### S1-S2 — Endpoint de ficha editorial unificada

#### `GET /documents/{id}/editorial-profile`

Devuelve la ficha editorial completa: fusión de `DocumentProfile` (perfil seleccionado/editado) + `DocumentGlobalContext` (ADN auto-detectado).

**Response 200:**
```json
{
  "doc_id": "uuid",
  "profile": {
    "preset_name": "novela_literaria",
    "register": "narrativo_literario",
    "intervention_level": "moderada",
    "max_rewrite_ratio": 0.35,
    "max_expansion_ratio": 1.10,
    "preserve_author_voice": true,
    "style_priorities": ["voz_autor", "ritmo", "claridad"],
    "protected_terms": ["Macondo", "STYLIA"],
    "forbidden_changes": ["modernizar_lexico"],
    "substitution_rules": [...],
    "entity_normalizations": [...],
    "idiolect_protections": [...],
    "register_constraints": ["sin_anglicismos"],
    "macro_correction_level": "none",
    "correction_phases": ["substitutions","lt","llm_micro","audit"]
  },
  "auto_detected": {
    "global_summary": "...",
    "dominant_voice": "...",
    "dominant_register": "narrativo_literario",
    "key_themes": [{"theme":"...", "weight":0.8}],
    "protected_globals": [{"term":"Macondo", "reason":"locación recurrente"}],
    "style_fingerprint": {"avg_sentence_length": 18, "passive_voice_ratio": 0.12, ...}
  },
  "is_locked": false  // true si el documento ya está en correcting/candidate_ready
}
```

**Errores:** `404` si no existe documento, `409` si no existe `DocumentGlobalContext` (análisis no terminado).

#### `PATCH /documents/{id}/editorial-profile`

Actualiza la ficha editorial. Acepta cualquier subconjunto de campos del `profile`. Bloqueado si `is_locked = true`.

**Request body:** subconjunto del bloque `profile` de la respuesta GET.

**Response 200:** la ficha actualizada (mismo schema que GET).

**Errores:** `409` si el documento está en estado bloqueado para edición de perfil (`correcting`, `candidate_rendering`, `finalizing`, `completed`). En esos estados el usuario debe usar `/reopen` antes.

#### `POST /documents/{id}/editorial-profile/rules`

Endpoint de conveniencia para agregar una regla individual (find/replace, normalización, idiolecto). Devuelve la regla creada con su `id`.

**Request body:**
```json
{"type": "substitution|normalization|idiolect",
 "rule": { ... según type ... }}
```

**Response 201:** `{"id": "uuid", "type": "substitution", "rule": {...}}`

#### `DELETE /documents/{id}/editorial-profile/rules/{rule_id}`

Elimina una regla. Idempotente.

#### `POST /documents/{id}/simulate-impact`

Simula el efecto del perfil actual sin lanzar el pipeline. Cuenta sustituciones que aplicarían, párrafos clasificados como SKIP/MICRO/MACRO, estimación de tokens y costo USD.

**Request body:** opcional override del perfil para previsualizar cambios sin guardarlos.
```json
{"profile_override": {...}}  // o vacío para usar el guardado
```

**Response 200:**
```json
{
  "substitution_matches": 47,
  "entity_normalization_matches": 12,
  "paragraph_routing": {"skip": 30, "micro": 120, "macro": 38, "total": 188},
  "estimated_tokens_input": 145000,
  "estimated_tokens_output": 32000,
  "estimated_cost_usd": 0.042,
  "estimated_duration_seconds": 380,
  "warnings": ["Regla 'el colegio' aplica 0 veces", "..."]
}
```

**Errores:** `409` si extracción de texto no completada; `404` doc inexistente.

### S5 — Reapertura para macro

#### `POST /documents/{id}/recorrect-macro`

Re-lanza solo Fase 2 macro-corrección sobre patches ya aprobados. Útil para activar macro post-hoc tras revisar un primer pase.

**Response 202:** `{"task_id": "uuid", "status": "queued"}`

---

## 7.5 Diseño de prompts

### Prompt: bloque REGLAS DE SUSTITUCIÓN (S2)

Se agrega a `build_user_prompt` cuando hay `substitution_rules` ya aplicadas. Va después del bloque CONTEXTO PREVIO y antes del PÁRRAFO A CORREGIR.

```
── REGLAS DEL USUARIO YA APLICADAS ──
Las siguientes sustituciones se aplicaron antes de tu intervención. NO las reviertas:
- "los niños" → "los y las niñas" (lenguaje inclusivo)
- "el colegio" → "Colegio Hermanitas de la Santa Caridad" (entidad canónica)
La forma resultante es la correcta. Tu tarea es corregir ortografía/gramática SIN tocar estos fragmentos.
```

### Prompt: bloque RESTRICCIONES DE REGISTRO (S2)

```
── RESTRICCIONES DE REGISTRO ──
- lenguaje_inclusivo: usa formas inclusivas; cuando una sustitución ya esté aplicada, mantenla
- sin_anglicismos: prefiere términos en español (ej: "correo" no "email")
- tuteo_exclusivo: nunca usar "usted"
```

### Prompt: bloque IDIOLECTOS PROTEGIDOS (S2)

```
── IDIOLECTOS PROTEGIDOS ──
- Habla del personaje "Juan": coloquial costeña, NO normalizar ("¡Ajá pues!", "Ombe...")
- Voz autoral: preserva el uso intencionado de puntos suspensivos
Si detectas estos patrones, NO los corrijas aunque parezcan "incorrectos".
```

### Prompt: macro-corrección (S5) — `build_macro_correction_prompt`

System prompt nuevo (cacheable), distinto del de Pasada 1.

```
Eres un editor literario senior. Tu tarea NO es corregir errores ortográficos
ni gramaticales (eso ya se hizo). Tu tarea es revisar la coherencia del párrafo
con el resto del documento: registro, tono, voz autoral, transiciones.

Solo intervén si detectas:
- Cambio de registro respecto al ADN editorial
- Inconsistencia de persona narrativa (1ª vs 3ª) entre párrafos
- Anglicismos o formas prohibidas por register_constraints
- Transición abrupta con el párrafo anterior
- Uso inconsistente de tuteo/voseo/usted

Si el párrafo está bien, devuelve action="skip" sin tocarlo. NO reescribas
por reescribir. Tu rewrite_ratio máximo es {{max_macro_rewrite_ratio}}.

Responde JSON: {"action": "rewrite|skip", "corrected_text": "...",
"macro_issues": [{"type": "registro|voz|transicion|inclusion", "explanation": "..."}],
"confidence": 0.0-1.0, "rewrite_ratio": 0.0}
```

User prompt incluye:
- Bloque ADN editorial completo (`build_global_context_block`)
- Ventana de 5-8 párrafos previos enriquecidos (tipo, registro local, sección)
- Resumen de la sección actual + sección anterior
- Reglas del usuario (substitution_rules ya aplicadas, register_constraints, idiolectos)
- Párrafo a auditar (post-Pasada 1 o post-Pasada 2)

### Ampliación: `AUDIT_SYSTEM_PROMPT` (S2)

Agregar tras la regla 6 actual:
```
7. Las REGLAS DEL USUARIO (substitution_rules, entity_normalizations) ya fueron aplicadas
   en una fase previa. NO las reviertas — son decisiones del editor humano.
8. Los IDIOLECTOS PROTEGIDOS deben preservarse exactamente como están, incluso si parecen
   no estándar. Forman parte de la voz autoral o de personajes.
9. Las RESTRICCIONES DE REGISTRO son obligatorias. Si la Pasada 1 introdujo un anglicismo
   y register_constraints incluye "sin_anglicismos", revierte ese cambio.
```

### Ampliación de `build_user_prompt` para Pasada 1 (S3)

Agregar al inicio del prompt el bloque de contexto global (que hoy solo se inyecta en Pasada 2):

```python
# En build_user_prompt, antes de PERFIL:
if global_context:
    parts.append(build_global_context_block(global_context))
```

Esto resuelve P9 sin necesidad de macro-corrección.

---

## 7.6 Diseño de componentes UI

### `EditorialProfilePanel.tsx` (nuevo, Sprint 4)

Panel principal de la "Hoja de Estilo Editorial Dinámica". Se muestra después de elegir preset, antes de procesar.

**Props:**
```ts
interface EditorialProfilePanelProps {
  docId: string;
  onConfirm: () => void;        // dispara POST /process
  onCancel: () => void;
  isLocked?: boolean;            // true si doc ya en correcting+
}
```

**Estado interno:**
- `profile: EditorialProfile | null` — fusión de DocumentProfile + GlobalDocumentContext
- `loading, saving, simulating: boolean`
- `impact: ImpactEstimate | null`
- `expandedSection: 'adn' | 'rules' | 'normalizations' | 'idiolects' | 'constraints' | 'macro'`

**Wireframe ASCII:**
```
┌─ FICHA EDITORIAL — mi_libro.docx ─────────────────────┐
│                                                        │
│ ▼ ADN EDITORIAL DETECTADO                  [auto]     │
│   Resumen: "Novela coral en Macondo..."               │
│   Voz dominante: tercera persona omnisciente          │
│   Registro: narrativo_literario                       │
│   Términos protegidos globales:                       │
│     Macondo, Buendía, Aureliano   (auto)              │
│   ↳ [+ agregar término]                                │
│                                                        │
│ ▼ REGLAS DE SUSTITUCIÓN                  [0 → 3]      │
│   ┌──────────────────────┬──────────────────────┐    │
│   │ Buscar               │ Reemplazar           │    │
│   ├──────────────────────┼──────────────────────┤    │
│   │ los niños            │ los y las niñas      │    │
│   │ el colegio           │ Col. Hnas. S. Caridad│    │
│   └──────────────────────┴──────────────────────┘    │
│   [+ regla]   ☐ sensible a mayúsculas                 │
│                                                        │
│ ▼ NORMALIZACIONES DE ENTIDADES           [1]          │
│ ▼ IDIOLECTOS PROTEGIDOS                  [0]          │
│ ▼ RESTRICCIONES DE REGISTRO                           │
│   ☑ lenguaje_inclusivo  ☐ sin_anglicismos             │
│   ☐ tuteo_exclusivo     ☐ voseo_rioplatense           │
│                                                        │
│ ▼ NIVEL DE INTERVENCIÓN MACRO                         │
│   ⦿ ninguno    ○ ligero    ○ completo                 │
│                                                        │
│ ─────────────────────────────────────────────────────  │
│ IMPACTO ESTIMADO              [↻ recalcular]          │
│ ~47 sustituciones · ~120 micro · ~0 macro             │
│ ~$0.04 USD · ~6 min de procesamiento                  │
│                                                        │
│ [Cancelar]                  [Confirmar y procesar →]  │
└────────────────────────────────────────────────────────┘
```

**Interacciones API:**
- Mount → `getEditorialProfile(docId)` carga ficha
- Cada cambio → `patchEditorialProfile(docId, partial)` (debounced 500ms)
- Botón "↻ recalcular" → `simulateImpact(docId)`
- "Confirmar y procesar" → `processDocument(docId)` y navega a `/documents/[id]`

**Estados:**
- `loading`: skeleton del panel
- `error`: banner rojo con retry
- `empty` (sin global_context): "El análisis editorial aún no termina, espera..."
- `locked`: panel readonly + banner "Documento ya en corrección, usa /reopen"

### `SubstitutionRulesEditor.tsx` (nuevo, Sprint 4)

Subcomponente embebido en `EditorialProfilePanel`. Tabla editable con add/remove/edit inline.

**Props:**
```ts
interface SubstitutionRulesEditorProps {
  rules: SubstitutionRule[];
  onChange: (rules: SubstitutionRule[]) => void;
  isLocked?: boolean;
}
```

**Validaciones cliente:**
- `find` no vacío, ≤200 chars
- `replace` ≤500 chars
- Si `is_regex = true`, validar regex con `new RegExp()` y mostrar error inline

### `IdiolectProtectionsEditor.tsx` (nuevo, Sprint 4)

Lista editable de protecciones con campos: `scope` (selector con opciones predefinidas + custom), `description` (textarea), `examples` (lista de strings).

### `RegisterConstraintsSelector.tsx` (nuevo, Sprint 4)

Set de checkboxes con las 5-7 constraints predefinidas + tooltip explicativo en cada una.

### `ImpactEstimatePanel.tsx` (nuevo, Sprint 4)

Pequeño componente que renderiza la respuesta de `/simulate-impact`. Estados: idle, loading, ready, error.

### `MacroCorrectionView.tsx` (nuevo, Sprint 5)

Modificación de `CorrectionHistory.tsx` para agrupar correcciones por `correction_phase`. Badges:
- `substitution` (krypton/azul)
- `lt` (gris/plomo)
- `llm_micro` (verde claro)
- `llm_macro` (krypton fuerte)
- `audit` (amarillo)

---

## 7.7 Flujo de usuario nuevo (end-to-end)

```
1. Subir DOCX
   ↓
   Backend: status=uploaded, MinIO almacena, no lanza pipeline
   UI: "Documento subido. Selecciona un perfil base."

2. Elegir preset editorial
   ↓
   Backend: POST /documents/{id}/profile crea DocumentProfile
   UI: muestra cards de presets, click selecciona

3. (BACKGROUND) Análisis editorial automático
   ↓
   Backend: pipeline parcial corre etapas A → B → C (sin D ni E)
   genera DocumentGlobalContext
   UI: indicador "Analizando documento..." (polling 3-5s)

4. REVISAR FICHA EDITORIAL                                ← NUEVO
   ↓
   Backend: GET /documents/{id}/editorial-profile devuelve perfil + ADN
   UI: muestra EditorialProfilePanel
   El usuario puede:
     - Ver el ADN auto-detectado (lectura)
     - Agregar reglas de sustitución, normalizaciones, idiolectos
     - Activar/desactivar register_constraints
     - Elegir macro_correction_level
     - Pedir estimación de impacto

5. (OPCIONAL) Simular impacto
   ↓
   Backend: POST /documents/{id}/simulate-impact
   UI: panel con métricas (sustituciones, párrafos, costo, duración)

6. Confirmar y procesar
   ↓
   Backend: POST /documents/{id}/process
     status=correcting, lanza pipeline etapa D con perfil completo
     - Fase 0 (S2): aplica substitution_rules + entity_normalizations
     - Fase 1 (S1+S3): LT con protected_globals + LLM Pasada 1 con ADN
     - Fase 2 (S5, opt-in): LLM macro-corrección
     - Fase auditoría (S2): Pasada 2 con perfil completo
   UI: vista detalle con tabs habituales (Pipeline, Análisis, Correcciones, etc.)

7. Revisar correcciones (existente, sin cambios)
   ↓
   UI: tab Correcciones permite aceptar/rechazar/editar.
   Las correcciones ahora muestran badge de correction_phase.

8. Finalizar
   ↓
   Backend: POST /documents/{id}/finalize → DOCX/PDF final
```

**Puntos donde el usuario puede pausar:**
- Tras paso 4: cerrar la pestaña; al volver, retoma el panel.
- Tras paso 6: candidate_ready permite reabrir vía `/reopen` para ajustar perfil.
- Tras paso 7: revisión humana puede tomar tiempo arbitrario.

**Compatibilidad hacia atrás:** documentos creados antes del despliegue de S4 saltan al paso 6 directamente (sin paso 4). El backend detecta perfil sin `substitution_rules` y aplica comportamiento legacy (idéntico al actual).

---

## 7.8 Casos de prueba críticos

### Sprint 0 (BD + schemas)
- Migración corre dos veces sin error (idempotencia).
- Al crear un documento nuevo, `document_profiles.substitution_rules = []` por default.
- Schemas Pydantic aceptan ficha sin nuevos campos (retrocompat).

### Sprint 1 (wiring globales)
- **Documento de prueba:** fragmento que mencione "STYLIA" y "tokenización" varias veces.
- Tras análisis, `DocumentGlobalContext.protected_globals_json` contiene esos términos.
- Lanzar corrección → patches NO contienen "ITALIA" ni "colonización" como reemplazo de "STYLIA"/"tokenización".
- `lt_corrections_json` puede registrarlas inicialmente, pero `reverted_lt_changes_json` las revierte.
- **Verificación**: `pytest -k test_languagetool_respects_globals` (a crear).

### Sprint 2 (reglas usuario)
- POST regla `{"find": "los niños", "replace": "los y las niñas"}`.
- `simulate-impact` cuenta correctamente las ocurrencias.
- Lanzar pipeline → patches con `correction_phase="substitution"` para cada match.
- Pasada 2 NO revierte la sustitución (verificar `pass2_audit_json` no contiene reversión).
- Regla con regex inválido devuelve `400`.

### Sprint 3 (contexto enriquecido + ADN en P1)
- Documento con cambio brusco de registro entre párrafos → Pasada 1 puede mantener registro (ADN visible).
- Antes del cambio, registro era académico; tras introducir ADN al prompt, las correcciones tienden a homogeneizar registro.
- Logs de tokens muestran ~15% incremento por inyección del bloque global (esperable).

### Sprint 4 (frontend)
- Subir DOCX → al terminar análisis, aparece panel.
- Agregar 3 reglas de sustitución → guardar → recargar → reglas persisten.
- Click "recalcular impacto" → respuesta < 2s para documento de 50 páginas.
- "Confirmar y procesar" desactiva el panel (locked) y navega.
- Volver al panel con doc en `correcting` → muestra readonly + banner.

### Sprint 5 (macro-corrección)
- Perfil con `macro_correction_level="light"` → patches `correction_phase="llm_macro"` aparecen.
- Sin macro_level (default `none`) → ningún patch macro generado.
- Coste USD reportado en `llm_usage` con `phase="llm_macro"`.
- `recorrect-macro` sobre doc completed → solo agrega patches macro sin tocar los aprobados.

### Cobertura monolítico vs paralelo (obligatoria por sprint)

Cada sprint debe correr **dos suites e2e**:
- **Suite A — documento pequeño (~30 párrafos):** flag `parallel_correction_enabled=False` → modo monolítico.
- **Suite B — documento grande (~400 párrafos repartidos en 6+ secciones):** flag `parallel_correction_enabled=True` con `batch_size=80` → fuerza ≥4 lotes.

Ambas suites verifican:
1. **Cobertura 100%:** todos los párrafos del DOCX original tienen patches o registro de SKIP.
2. **Paridad de reglas:** las nuevas funcionalidades (substitution_rules, protected_globals, register_constraints, idiolect_protections, ADN en P1) producen patches equivalentes en ambas suites.
3. **No regresión de tests existentes** del MVP 2.

### Tests específicos de modo paralelo (S1-S5)

- **S1 paralelo:** documento con `STYLIA` en párrafo 1 (lote 0), 200 (lote 1), 350 (lote 2). Verificar que ningún lote produce reemplazo a "ITALIA".
- **S2 paralelo:** sustitución `los niños → los y las niñas` con coincidencias en lotes 0, 1 y 2. Verificar que cada lote aplica Fase 0 antes de LT y que el patch tiene `correction_phase="substitution"`.
- **S2 paralelo — boundary:** sustitución que cambia longitud del último párrafo del lote 0 (ej: alarga 30 chars). Verificar que el `boundary_check` re-corrige el primer párrafo del lote 1 con seed real y que la sustitución no se "duplica".
- **S3 paralelo:** ADN editorial llega al prompt P1 dentro de cada lote. Inspeccionar `llm_audit_log` y verificar que el bloque `CONTEXTO GLOBAL` aparece en ≥1 llamada por lote.
- **S5 paralelo:** documento con `macro_correction_level="light"` en modo paralelo. Verificar:
  - El chord encadena `correct_macro_pass` después de `assemble_correction_results`.
  - Patches macro tienen `correction_phase="llm_macro"`.
  - El macro pass **respeta** los patches de Fase 0 (no revierte sustituciones).
  - `Document.status` transita por `correcting_macro` antes de `candidate_rendering`.
- **S5 monolítico vs paralelo:** mismo documento, mismo perfil, ejecutado en ambos modos. Diff final del DOCX: ≥95% de patches idénticos. Diferencias permitidas solo en macro-correcciones (porque el contexto previo difiere por aproximación).

### End-to-end por sprint completado
- Comando: `docker-compose up --build` arranca limpio.
- Subir documento de referencia → completar flujo completo → descargar PDF.
- Diff entre original y corregido respeta sustituciones, no destruye términos protegidos.
- **Validar cobertura 100%:** `SELECT COUNT(*) FROM patches WHERE doc_id=X` ≥ párrafos no-vacíos del DOCX (algunos pueden no tener cambios pero deben pasar por el pipeline).

---

## 7.9 Riesgos y mitigaciones

| Riesgo | Sprint | Probabilidad | Impacto | Mitigación |
|--------|--------|--------------|---------|------------|
| Migración rompe documentos existentes | S0 | bajo | alto | Solo `ADD COLUMN` con defaults. Probar con `pgdump` previo. Snapshot de prueba en Docker. |
| Bloque de contexto global hincha tokens en cada llamada | S1, S3 | medio | medio | Truncar a ~600 tokens. System prompt cacheable de OpenAI mantiene la mayor parte. Métrica de tokens promedio a comparar antes/después. |
| Sustituciones con regex permite ataques (catastrophic backtracking) | S2 | medio | medio | Validar regex con timeout. En frontend: usar `new RegExp(pattern, "g")` con feature de cancelación. En backend: módulo `regex` con timeout. Si excede, devolver error y desactivar regla. |
| Pasada 2 revierte sustituciones aplicadas en Fase 0 | S2 | alto | alto | El `corrected_pass1` que llega a Pasada 2 ya contiene las sustituciones. AUDIT_SYSTEM_PROMPT explícito (ver 7.5). Test específico que falla si reversión ocurre. |
| Frontend deja al usuario "atascado" en panel sin terminar análisis | S4 | medio | medio | Polling con timeout de 90s. Botón "saltar revisión y procesar con perfil base" como escape. |
| Macro-corrección tarda demasiado y bloquea worker | S5 | alto | alto | Timeout específico por llamada macro (45s). Macro corre en cola separada `macro_queue`. Modelo `openai_macro_model` configurable (puede ser distinto y más caro). |
| Macro-corrección sobrescribe el trabajo cuidadoso de Pasada 1+2 | S5 | medio | alto | Macro respeta `max_macro_rewrite_ratio` (0.10 por default, conservador). Macro NO se aplica a párrafos donde Pasada 2 ya intervino fuerte (rewrite_ratio Pasada 2 > 0.20). |
| Idiolect protections no se respetan | S2 | medio | medio | Inyectar bloque dedicado en system prompt + en user prompt. Quality gate adicional: si rewrite_ratio del párrafo > 0.30 y contiene scope de idiolecto, marcar `manual_review`. |
| `register_constraints="lenguaje_inclusivo"` no se cumple consistentemente | S2 | alto | medio | Combinar instrucciones en prompt + post-proceso heurístico (regex que detecta formas masculinas-genéricas en contextos plurales como `los X` → marca `manual_review`). |
| Documentos que ya tienen perfil sin nuevos campos rompen al cargar | S0, S2 | bajo | alto | Schemas Pydantic con `default_factory=list` para todos los nuevos campos JSONB. Función `_migrate_profile_dict()` que normaliza dicts antiguos. |
| **Modo paralelo: contexto inter-lote queda desfasado tras S2/S3** | S2, S3 | medio | medio | Mitigado por `boundary_check` existente. Para S3, opcionalmente pasar `context_seed_window` (lista de N párrafos previos) en vez de un solo seed. Test obligatorio comparando salida monolítica vs paralela del mismo documento. |
| **Modo paralelo: macro-corrección dentro del lote pierde visión global** | S5 | alto | alto | Diseño explícito: macro NO corre por lote. Se ejecuta como pase post-merge (`correct_macro_pass`) sobre el documento ya corregido por P1+P2. Encadenado al chord como tarea Celery final. Garantiza ventana real de N párrafos previos. |
| **Modo paralelo: sustituciones cambian longitud y rompen boundary check** | S2 | medio | medio | Boundary check ya re-corrige con seed real. Test específico que aplica sustitución alargante en último párrafo del lote 0 y verifica integridad del primer párrafo del lote 1. |
| **Documentos muy grandes (>1000 párrafos) saturan la cola batch** | S2-S5 | bajo | medio | `parallel_correction_max_batches=8` ya limita. Si se rebasa, lotes son ≥125 párrafos. Para S5 macro-pass: timeout amplio (300s) y posibilidad de chunkar el macro pass también si rewrite_ratio_acumulado supera umbral. |
| **Cambio en firma de `correct_batch_llm` rompe tareas en cola al deployar** | S2-S5 | medio | medio | Si se modifica firma de la subtarea Celery, drenar cola antes de deploy O usar nombres versionados (`correct_batch_llm_v2`). Mantener compatibilidad llamando a `correct_batch_llm` con kwargs por defecto. |

---

## Archivos críticos a modificar (resumen consolidado)

### Backend
- [backend/app/main.py](backend/app/main.py) — migraciones (S0, S5)
- [backend/app/models/style_profile.py](backend/app/models/style_profile.py) — nuevos campos (S0)
- [backend/app/schemas/style_profile.py](backend/app/schemas/style_profile.py) — schemas (S0)
- [backend/app/data/profiles.py](backend/app/data/profiles.py) — actualizar 10 presets con defaults (S0)
- [backend/app/api/v1/documents.py](backend/app/api/v1/documents.py) — nuevos endpoints (S1-S5)
- [backend/app/services/correction.py](backend/app/services/correction.py) — pasar `term_registry` a engine_router, ampliar context, Fase 0, Fase 2 (S1-S5)
- [backend/app/services/engine_router.py](backend/app/services/engine_router.py) — wiring de protected_globals (S1)
- [backend/app/services/protected_regions.py](backend/app/services/protected_regions.py) — usar global_protected_terms (S1)
- [backend/app/services/prompt_builder.py](backend/app/services/prompt_builder.py) — bloques nuevos, build_macro_correction_prompt (S2-S5)
- [backend/app/services/audit_pass.py](backend/app/services/audit_pass.py) — recibir profile completo (S2)
- [backend/app/services/complexity_router.py](backend/app/services/complexity_router.py) — rutas macro/micro (S5)
- [backend/app/services/substitution_engine.py](backend/app/services/substitution_engine.py) — **NUEVO** Fase 0 (S2)
- [backend/app/services/macro_correction.py](backend/app/services/macro_correction.py) — **NUEVO** Fase 2 post-merge (S5)
- [backend/app/models/patch.py](backend/app/models/patch.py) — campos correction_phase, substitution_rule_id (S0)
- [backend/app/workers/tasks_pipeline.py](backend/app/workers/tasks_pipeline.py) — `correct_batch_llm`, `assemble_correction_results`, dispatch paralelo, integración macro post-merge (S1-S5)
- [backend/app/models/correction_batch.py](backend/app/models/correction_batch.py) — agregar `phase_completed` flags si S5 lo requiere

### Frontend
- [frontend/src/lib/api.ts](frontend/src/lib/api.ts) — tipos + funciones nuevas (S0, S4)
- [frontend/src/app/page.tsx](frontend/src/app/page.tsx) — flujo con nuevo paso 4 (S4)
- [frontend/src/components/AnalysisView.tsx](frontend/src/components/AnalysisView.tsx) — exponer ADN editorial (S4)
- [frontend/src/components/EditorialProfilePanel.tsx](frontend/src/components/EditorialProfilePanel.tsx) — **NUEVO** (S4)
- [frontend/src/components/SubstitutionRulesEditor.tsx](frontend/src/components/SubstitutionRulesEditor.tsx) — **NUEVO** (S4)
- [frontend/src/components/IdiolectProtectionsEditor.tsx](frontend/src/components/IdiolectProtectionsEditor.tsx) — **NUEVO** (S4)
- [frontend/src/components/RegisterConstraintsSelector.tsx](frontend/src/components/RegisterConstraintsSelector.tsx) — **NUEVO** (S4)
- [frontend/src/components/ImpactEstimatePanel.tsx](frontend/src/components/ImpactEstimatePanel.tsx) — **NUEVO** (S4)
- [frontend/src/components/MacroCorrectionView.tsx](frontend/src/components/MacroCorrectionView.tsx) — **NUEVO** (S5, modifica CorrectionHistory)

### Sin tocar (estables)
- `backend/app/services/ingestion.py`, `extraction.py`, `rendering.py` (excepto P7 opcional en S5)
- `backend/app/workers/celery_app.py`
- `backend/app/utils/*`, `database.py`, `config.py`

---

## 7.10 Compatibilidad con flujo paralelo (documentos grandes)

### Cómo Stylia procesa documentos hoy

Stylia tiene **dos rutas de Etapa D** según el tamaño y configuración:

| Característica | Modo monolítico (default) | Modo paralelo por lotes |
|----------------|---------------------------|--------------------------|
| Disparador | Default (`parallel_correction_enabled=False`) o cuando `len(batches)<=1` | Flag ON + boundaries de sección producen ≥2 lotes |
| Ubicación de la decisión | `tasks_pipeline.py:1175-1189` (`_dispatch_parallel_correction`) | Igual; si retorna `True`, no se ejecuta la rama secuencial |
| Tamaño de lote | n/a | `parallel_correction_batch_size = 150` párrafos, alineado a finales de sección |
| Máximo de lotes | n/a | `parallel_correction_max_batches = 8` |
| Tarea Celery | `process_document_pipeline` (cola `pipeline`) | `correct_batch_llm` por lote (cola `batch`) + chord callback `assemble_correction_results` |
| Función de corrección por párrafo | `_correct_single_paragraph` (`correction.py:220-511`) | **Misma función** — reutilizada desde `correct_batch_with_llm_sync` (`correction.py:946-1108`) |
| Pasada 1 LT | Pre-paralelizable con `ThreadPoolExecutor` | Pre-computada y serializada a MinIO antes del fork |
| Pasada 2 (auditoría) | Inline en bucle secuencial | Inline dentro de cada lote, secuencial por párrafo |
| Contexto entre párrafos | Real, lista acumulada `corrected_context` | **Aproximado entre lotes** vía `context_seed` (~200 chars del último párrafo post-LT del lote anterior); real DENTRO del lote |
| Boundary check | n/a | Re-corrige el primer párrafo de cada lote 2..N con seed real → reemplaza patch si difiere |
| Merge final | Implícito (todo en un `correct_docx_sync`) | `assemble_correction_results` ordena por `paragraph_index`, persiste, lanza Etapa E |

### Lo que YA es compatible (verificado en código)

1. **`profile_json` viaja completo a cada lote** (`tasks_pipeline.py:806`). Cualquier nuevo campo JSONB añadido al modelo `DocumentProfile` (substitution_rules, entity_normalizations, idiolect_protections, register_constraints, macro_correction_level, correction_phases) **llega automáticamente al lote** sin modificar firmas Celery. Solo hay que asegurarse de que esté incluido en el dict serializado en `tasks_pipeline.py` cuando se construye `profile_dict` (líneas 1008-1023).
2. **`global_context_dict` se serializa a MinIO** antes del dispatch y cada lote lo descarga (`tasks_pipeline.py:758-764` y `1387-1395`). Toda la información del ADN editorial llega al modo paralelo.
3. **`_correct_single_paragraph` es función única**. Sprints S1-S3 que modifiquen su comportamiento (inyectar ADN al prompt P1, pasar `term_registry`, etc.) heredan automáticamente al modo paralelo.
4. **Patches mergean por `paragraph_index`** sin riesgo de colisión. Los rangos `[start_para..end_para]` son disjuntos por construcción.

### Lo que requiere cuidado por sprint

**Sprint S0 — migraciones BD:**
- `correction_batches` ya existe; no requiere ALTER. Si S5 necesita un flag `macro_pass_completed`, se agrega `ALTER TABLE correction_batches ADD COLUMN IF NOT EXISTS macro_pass_completed BOOLEAN DEFAULT FALSE`.

**Sprint S1 — wiring de protecciones globales:**
- Pasar `term_registry` a `_correct_single_paragraph` propaga a ambos modos (es la misma función). Verificar que `protected_globals_json` se incluya en `global_context_dict` serializado a MinIO. **Riesgo bajo** — solo es wiring.
- El **boundary check** (`tasks_pipeline.py:1545-1588`) debe seguir funcionando: como re-llama `_correct_single_paragraph`, hereda las protecciones globales automáticamente.

**Sprint S2 — sustitution_rules / entity_normalizations:**
- **Decisión arquitectónica clave:** la Fase 0 se aplica **por párrafo dentro de `_correct_single_paragraph`**, antes de LT, NO como un pase global previo sobre el DOCX.
  - **Razón:** un pase global previo sobre el DOCX completo requeriría correr antes del fork de lotes y persistir el DOCX modificado, complicando el rendering. Aplicar por párrafo es idempotente, determinista, y se replica en boundary check sin riesgo.
- Los presets nuevos del perfil (substitution_rules, etc.) viajan vía `profile_json` y se procesan dentro del lote. **Compatible automáticamente.**
- Verificar que `correct_batch_with_llm_sync` reciba el `profile` completo y lo pase a `_correct_single_paragraph` (ya lo hace; verificar tras los cambios).
- **Riesgo medio:** si un párrafo cae en el límite de un lote y la sustitución cambia su longitud, el `context_seed` aproximado del lote siguiente puede divergir. Mitigación: el boundary check ya re-corrige con seed real.

**Sprint S3 — ampliación de ventana de contexto + ADN en P1:**
- En **monolítico**: `corrected_context[-3:]` puede crecer a `[-N:]` (configurable, ej: 5-8). Trivial.
- En **paralelo**: `corrected_context` arranca con `[context_seed]` y crece DENTRO del lote. Para los primeros párrafos de un lote 2..N, la ventana efectiva es 1-2 (el seed + lo que se va corrigiendo). **Limitación inherente del modo paralelo.**
  - Mitigación opcional: en `_dispatch_parallel_correction`, en lugar de pasar un solo `context_seed`, pasar una **lista de N párrafos previos al lote** (post-LT, ya pre-computados). Cambio mínimo en `correct_batch_llm` firma + en `correct_batch_with_llm_sync` para inicializar `corrected_context = list(context_seed_window)` en vez de `[context_seed]`.
  - Costo: ~200 chars × N párrafos = ~1-2 KB extra por lote en MinIO. Negligible.
- Inyectar el ADN al prompt P1 (`build_user_prompt`) → afecta a ambos modos sin cambios extras (la función la usa cualquier ruta).

**Sprint S4 — frontend:**
- `simulate-impact` debe estimar tokens y duración considerando que un documento grande corre en paralelo: `estimated_duration_seconds = max(...)` por lote en lugar de suma. El backend conoce `parallel_correction_enabled` y `parallel_correction_batch_size` desde `config.py`.
- El usuario no necesita ver la diferencia entre modos. La estimación de impacto es la misma; solo cambia la métrica de duración.

**Sprint S5 — macro-corrección como pase post-merge (CAMBIO ARQUITECTÓNICO):**
- **NO** se ejecuta dentro de cada lote. Se ejecuta DESPUÉS del merge en `assemble_correction_results` (o en una nueva tarea Celery `correct_macro_pass` encadenada al chord).
  - **Razón:** la macro-corrección requiere ventana de 5-8 párrafos previos REALES (ya corregidos por P1+P2) y visibilidad cross-sección. En modo paralelo, ningún lote tiene esa información hasta el merge.
- **Arquitectura:**
  ```
  chord(group(correct_batch_llm.s(...) for cada batch))
    .then(assemble_correction_results.s(...))     # merge patches P1+P2
    .then(correct_macro_pass.s(...))              # NUEVA — solo si macro_correction_level != "none"
    .then(final_render.s(...))                    # Etapa E
  ```
- `correct_macro_pass` carga el documento ya corregido (post P1+P2), itera secuencialmente con ventana real de N párrafos y aplica patches con `correction_phase="llm_macro"`. Es secuencial pero corre solo sobre párrafos que el router macro/micro marca como candidatos (default: skip mayoría).
- **En modo monolítico**, también se hace post-merge pero dentro de `correct_docx_sync` para mantener simetría: tras el bucle principal, un segundo bucle macro si el perfil lo requiere. Alternativamente, se puede unificar el código creando `correct_macro_pass_sync(patches, all_paragraphs, profile, global_context)` que ambos modos invocan al final.
- **Quality gates de macro-corrección** corren en este pase, comparando contra el resultado P1+P2 (no contra el original puro), para no destruir las correcciones previas.
- **Tracking:** en `CorrectionBatch` puede agregarse `macro_pass_completed BOOLEAN`. La nueva tarea Celery actualiza `Document.status` con un sub-estado intermedio (`correcting_macro`) si se quiere visibilidad en frontend.

### Decisiones cross-cutting

- **Compatibilidad con perfiles legacy.** Documentos creados antes del despliegue tienen `substitution_rules=NULL` (o `[]` por default si la migración corre). Tanto el modo monolítico como el paralelo deben aceptar `profile.get("substitution_rules", [])` defensivamente. Test específico: subir documento, dejarlo con perfil base sin reglas, verificar que pipeline corre idéntico al actual.
- **Métricas de coste por modo.** El nuevo campo `llm_usage.phase` (S5) permite separar costos de Fase 0 (gratis), Pasada 1, Pasada 2 y macro. El endpoint `/costs/summary` debe agrupar por phase para que el usuario vea cuánto cuesta cada fase, sin importar el modo.
- **Logs unificados.** Cada lote loggea su `batch_index`. Las nuevas reglas deben loggearse por párrafo con su `correction_phase` para trazabilidad cross-batch.

---

## Verificación end-to-end del plan completo

1. `docker-compose down -v && docker-compose up --build` → arranque limpio.
2. Subir DOCX de prueba con: términos técnicos repetidos, frases con "los niños", anglicismos, cambio de registro entre párrafos.
3. Tras análisis automático, abrir panel editorial → verificar que aparece el ADN auto-detectado con `protected_globals`.
4. Agregar regla `los niños → los y las niñas`, activar `sin_anglicismos`, agregar idiolect_protection sobre un personaje.
5. Click "Estimar impacto" → verificar conteo razonable (~5-50 sustituciones, X micro, 0 macro).
6. Confirmar y procesar.
7. En tab "Correcciones": filtrar por `correction_phase="substitution"` → ver las sustituciones aplicadas.
8. Filtrar por `correction_phase="llm_micro"` → ver correcciones que NO destruyeron los términos protegidos.
9. Descargar DOCX corregido → verificar manualmente: términos preservados, sustituciones aplicadas, registro homogeneizado.
10. (S5 opcional) Activar `macro_correction_level="light"` y `recorrect-macro` → verificar patches macro adicionales.

**Métricas de éxito globales:**
- 0 destrucciones de términos en `protected_globals_json` (vs ~3-5 hoy en docs grandes).
- Correcciones de tipo `substitution` con tasa de reversión por Pasada 2 < 1%.
- Tiempo total del pipeline: ≤ 1.3× del actual sin macro; ≤ 2.5× con macro_level="light".
- Costo USD por documento promedio: incremento ≤ 20% sin macro; ≤ 80% con macro_level="light".
- **Cobertura de patches al 100% del documento en ambos modos** (monolítico y paralelo). Cero párrafos sin pasar por la nueva lógica.
- **Paridad ≥95% entre modos** sobre el mismo documento+perfil (excluyendo diferencias esperadas en macro por aproximación de contexto inter-lote).
