# Plan v4 — Motor Cognitivo de Doble Pasada con Auditoría Total

## Context — Por qué este rediseño

La auditoría real del 2026-04-27 (`docx_prueba/REPORTE-DIAGNOSTICO-2026-04-27.md`) reveló que el pipeline actual de Plan v3 (single-pass: LT → router → LLM) tiene un techo de calidad estructural:

- **Tasa neta de corrección: 56%** (29/52 errores conocidos)
- **3 regresiones críticas** introducidas por LanguageTool sin que el LLM las pudiera revertir:
  - `STYLIA → ITALIA` (auto_accepted, sin gate que lo detecte)
  - `tokenización → colonización` (LLM aceptó la "corrección" de LT por falta de contexto técnico)
  - `STYLIA v1.0 → ITALIA vv.` (rewrite_ratio gate lo atrapó por casualidad)
- **17% de errores no corregidos** porque el LLM opera ciego al sentido global del documento (muletillas dobles, cambio de persona narrativa, ausencia de ¿)
- **El LLM solo ve 1 párrafo previo** (`prompt_builder.py:235-256`) — sin voz del autor, sin tema global, sin coherencia inter-sección

**Diagnóstico del usuario:** *"LanguageTool carece de contexto semántico. Si el usuario no protege explícitamente un término técnico, LanguageTool lo destruye. Necesitamos que la IA actúe como un auditor superior que entienda el sentido del texto, la voz del autor y el flujo global. La calidad es la prioridad absoluta; el costo de tokens pasa a segundo plano."*

**Objetivo del Plan v4:** rediseñar el motor cognitivo en 4 pilares para superar el techo del 56% y eliminar las regresiones por falta de contexto:

1. Prompts contextualmente ricos con ventana ampliada
2. Pipeline de doble pasada (corrección mecánica + auditoría contextual)
3. Trazabilidad RAW de cada llamada al LLM (request + response intactos)
4. Panel administrativo de auditoría comparativa

---

## Diagnóstico técnico del estado actual (auditado en código)

### 1. Generador de prompts — limitaciones encontradas

**Archivo:** `backend/app/services/prompt_builder.py`

- `build_user_prompt()` (líneas 98-265) construye 4 bloques: PERFIL, UBICACIÓN ESTRUCTURAL, CONTEXTO PREVIO (1 párrafo, truncado a 350 chars), TEXTO A CORREGIR, REGIONES PROTEGIDAS
- **Falta:** bloque de CONTEXTO GLOBAL DEL DOCUMENTO (resumen del libro, voz del autor, registro dominante, glosario activo)
- **Falta:** ventana de contexto previo amplia (actualmente N=1; ideal N=3-5 con texto completo, no truncado)
- `build_system_prompt()` (líneas 28-66) es estático cacheable — correcto, no tocar la estructura, pero ampliar las reglas para una "Pasada 2 de auditoría"

### 2. Tokens artificialmente limitados

**Archivos:** `backend/app/config.py:49-57`, `backend/app/utils/openai_client.py:33-37`

| Setting | Valor actual | Problema |
|---------|--------------|----------|
| `openai_cheap_max_tokens` | 500 | Insuficiente para prompts ricos + respuestas con explicación |
| `openai_editorial_max_tokens` | 1200 | Insuficiente para auditoría contextual |
| Input window | Sin límite explícito | OK — se aprovecha |

`gpt-5.4-mini` soporta ventanas largas; el tope de salida de 500/1200 es legacy MVP1. El input context se usa libremente.

### 3. Pipeline single-pass confirmado

**Archivo:** `backend/app/services/correction.py`

- `_correct_single_paragraph()` (líneas 219-498): orden fijo LT → revertir LT en regiones protegidas → router → LLM (CHEAP/EDITORIAL)
- `correct_docx_sync()` (líneas 501-682): un solo loop sobre párrafos, acumulando `corrected_context` (`line 638`) — solo 1 párrafo previo se inyecta al prompt
- **NO existe segunda pasada de auditoría.** El LLM tiene una sola oportunidad de revertir destrucciones de LT, sin contexto global.

### 4. Trazabilidad: audit trail estructurado pero NO hay JSON raw

**Archivos:** `backend/app/models/patch.py:125-139`, `backend/app/models/llm_usage.py`

- `Patch` tiene 4 columnas JSONB del Sprint 3 (`lt_corrections_json`, `llm_change_log_json`, `reverted_lt_changes_json`, `protected_regions_snapshot`) — útiles pero **NO guardan el payload bruto enviado a OpenAI ni la respuesta cruda**
- `LlmUsage` solo guarda métricas (tokens, costo) — sin prompts ni responses
- Endpoint `/correction-flow` (`documents.py:1394-1490`) devuelve metadata reconstruida, **no los prompts/responses originales** (excepto en modo demo)

### 5. Frontend de auditoría inexistente

**Archivos:** `frontend/src/components/CorrectionFlowViewer.tsx`, `CorrectionHistory.tsx`

- `CorrectionFlowViewer` muestra prompts solo en modo demo simulado
- No hay vista que compare lado a lado: original → Pasada 1 → Pasada 2 con prompts crudos
- No hay filtros para "destrucciones de LT revertidas por la IA en Pasada 2"

### 6. Etapa C (análisis): genera resúmenes por sección, NO global

**Archivos:** `backend/app/services/analysis.py:527-591`, `backend/app/models/section_summary.py`

- Detecta secciones, glosario, clasifica párrafos
- **Genera `SectionSummary.summary_text`** (~50 palabras por sección) — bueno pero local
- **NO genera resumen global del documento** ni ficha de "voz del autor / registro dominante / estilo predominante" del libro completo

---

## PILAR 1 — Contexto Global y Prompts Expandidos

### 1.1 Nueva tabla `document_global_context`

Tabla de single-row por documento con el "ADN editorial" del libro:

| Campo | Tipo | Origen |
|-------|------|--------|
| `doc_id` | UUID PK FK | |
| `global_summary` | TEXT (~300 palabras) | LLM resume el documento entero a partir de muestreos diversos |
| `dominant_voice` | TEXT (~80 palabras) | "Académica formal con tendencia a la pasividad y al uso de tecnicismos del NLP. Tono neutro-explicativo." |
| `dominant_register` | VARCHAR(30) | "academico_formal" / "divulgativo" / "narrativo_literario" / etc. |
| `key_themes_json` | JSONB | `[{"theme": "machine learning editorial", "weight": 0.85}, ...]` |
| `protected_globals_json` | JSONB | Términos técnicos detectados por la IA que NO deben tocarse jamás (ej: "tokenización", "STYLIA", "NLP") |
| `style_fingerprint_json` | JSONB | `{"avg_sentence_length": 28, "passive_voice_ratio": 0.4, "uses_dashes": true, ...}` |
| `total_paragraphs` | INTEGER | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

**Cómo se llena:** durante Etapa C (análisis), una nueva sub-fase **C.6 Global Context** invoca el LLM con un muestreo estratificado de párrafos (primeros 3, mediano 3, últimos 3, + secciones representativas) y solicita un análisis global. Esto reemplaza/complementa la inferencia ligera actual de perfil.

**Costo estimado:** 1 llamada LLM extra por documento (~3000 tokens input, 800 tokens output). Despreciable frente a la mejora de calidad.

### 1.2 Bloque nuevo en el prompt: "CONTEXTO GLOBAL DEL DOCUMENTO"

Insertar en `prompt_builder.py:build_user_prompt()` antes de UBICACIÓN ESTRUCTURAL:

```
═══ CONTEXTO GLOBAL DEL DOCUMENTO ═══
TEMA PRINCIPAL: {global_summary}
VOZ DEL AUTOR: {dominant_voice}
REGISTRO BASE: {dominant_register} (no alterar a otro registro)
TÉRMINOS TÉCNICOS PROTEGIDOS: {protected_globals_json[*].term}
ESTILO DOMINANTE: oraciones de ~{avg_sentence_length} palabras, {passive_voice_ratio*100}% voz pasiva
```

### 1.3 Ventana de contexto previo ampliada

- Cambiar `corrected_context: list[str]` → mantener acumulador pero **inyectar N=5 párrafos previos completos** (no truncados a 350 chars)
- Para documentos largos: inyectar también los últimos 2 párrafos de la sección anterior si hay cambio de sección (cohesión inter-sección)

### 1.4 Eliminar límites artificiales de tokens de salida

| Setting | Antes | Después |
|---------|-------|---------|
| `openai_cheap_max_tokens` | 500 | 2000 |
| `openai_editorial_max_tokens` | 1200 | 4000 |
| `openai_audit_max_tokens` (NUEVO) | — | 6000 |

**Archivos a modificar:**
- `backend/app/services/prompt_builder.py` — añadir `build_global_context_block()`, ampliar ventana de contexto previo, nueva firma `build_audit_user_prompt()` para Pasada 2
- `backend/app/models/document_global_context.py` — NUEVO modelo
- `backend/app/services/analysis.py` — añadir `analyze_global_context_sync(doc, sample_paragraphs, llm_client)`
- `backend/app/config.py` — actualizar settings de tokens

---

## PILAR 2 — Pipeline de Doble Pasada (Mecánica + Auditoría Contextual)

### 2.1 Arquitectura de las dos pasadas

```
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA C — ANÁLISIS                                              │
│   C.1-C.5 actual + C.6 NUEVO → genera document_global_context   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA D — CORRECCIÓN (DOBLE PASADA)                             │
│                                                                  │
│   ┌──────────────────────────────────────────┐                  │
│   │ PASADA 1 — Corrección Mecánica           │                  │
│   │   • LanguageTool con disabled rules      │                  │
│   │   • LLM con prompt MÍNIMO (sin global)   │                  │
│   │   • Objetivo: ortografía + gramática     │                  │
│   │   • Output: corrected_pass1 + audit log  │                  │
│   └──────────────────────────────────────────┘                  │
│                       ↓                                          │
│   ┌──────────────────────────────────────────┐                  │
│   │ PASADA 2 — Auditoría Contextual          │                  │
│   │   • LLM con CONTEXTO GLOBAL completo     │                  │
│   │   • Recibe: original + pass1 + diff      │                  │
│   │   • Tarea: revertir destrucciones,       │                  │
│   │     mejorar estilo, coherencia, registro │                  │
│   │   • Output: corrected_pass2 + audit log  │                  │
│   └──────────────────────────────────────────┘                  │
│                       ↓                                          │
│   Quality Gates sobre corrected_pass2                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Implementación

**Refactorización en `backend/app/services/correction.py`:**

- `_correct_single_paragraph()` se divide en:
  - `_run_pass1_mechanical(para_text, profile, ...)` → retorna `corrected_pass1, lt_log, llm1_log, raw_request_1, raw_response_1`
  - `_run_pass2_contextual(para_text, corrected_pass1, global_context, full_history, ...)` → retorna `corrected_pass2, llm2_log, raw_request_2, raw_response_2, reverted_destructions[]`

**Nuevo módulo `backend/app/services/audit_pass.py`:**

- Función `audit_paragraph_with_context()` construye prompt de Pasada 2 con instrucciones explícitas:
  - "Compara `original` con `corrected_pass1`. Identifica si la Pasada 1 introdujo errores semánticos (términos técnicos modificados incorrectamente, nombres propios alterados, sentido cambiado)."
  - "Revierte cualquier destrucción detectada usando el CONTEXTO GLOBAL como referencia."
  - "Aplica mejoras de estilo, registro y coherencia con respecto al CONTEXTO PREVIO y la VOZ DEL AUTOR."
  - "Devuelve JSON con: `final_text`, `reverted_destructions[]`, `style_improvements[]`, `confidence`."

**Reglas de routing del Pilar 2:**

- Pasada 1 obligatoria para todos los párrafos (excepto `route=skip`)
- Pasada 2 obligatoria para párrafos donde Pasada 1 hizo cambios significativos (>10% rewrite_ratio) O ruta=editorial
- Pasada 2 opcional pero recomendada para todos los párrafos del cuerpo si el perfil tiene `intervention_level >= moderada`
- Para títulos cortos donde Pasada 1 detectó errores tipográficos: forzar Pasada 1 + Pasada 2 ligera (validación), eliminar route=skip ciego

### 2.3 Quality gates sobre Pasada 2

Los gates existentes (`quality_gates.py`) se ejecutan **sobre la salida de Pasada 2**, no de Pasada 1. La Pasada 1 puede fallar gates: la Pasada 2 tiene la oportunidad de arreglarlo.

**Archivos a modificar:**
- `backend/app/services/correction.py` — refactorizar a doble pasada
- `backend/app/services/audit_pass.py` — NUEVO
- `backend/app/services/prompt_builder.py` — añadir `build_audit_user_prompt()`
- `backend/app/services/complexity_router.py` — añadir lógica para decidir si Pasada 2 se ejecuta
- `backend/app/models/patch.py` — añadir campos `corrected_pass1_text`, `pass1_changes_json`, `pass2_audit_json` (paralelo al audit trail dual-engine actual)

---

## PILAR 3 — Trazabilidad Total: tabla `llm_audit_log`

### 3.1 Nueva tabla independiente para JSON crudo

| Campo | Tipo | Propósito |
|-------|------|-----------|
| `id` | UUID PK | |
| `doc_id` | UUID FK | |
| `paragraph_index` | INTEGER | |
| `location` | VARCHAR(100) | `body:N`, `table:T:R:C:P` |
| `pass_number` | SMALLINT (1 o 2) | Pasada 1 (mecánica) o Pasada 2 (auditoría) |
| `call_purpose` | VARCHAR(40) | `mechanical_correction` / `contextual_audit` / `global_summary` |
| `model_used` | VARCHAR(50) | gpt-5.4-mini, etc. |
| `request_payload` | JSONB | Solicitud RAW completa enviada a OpenAI (system prompt, user prompt, params) |
| `response_payload` | JSONB | Respuesta RAW completa de OpenAI (choices, usage, finish_reason) |
| `prompt_tokens` | INTEGER | |
| `completion_tokens` | INTEGER | |
| `total_tokens` | INTEGER | |
| `latency_ms` | INTEGER | |
| `error_text` | TEXT NULL | Si la llamada falló |
| `created_at` | TIMESTAMPTZ | |

**Indices:** `(doc_id, paragraph_index, pass_number)`, `(doc_id, created_at)`.

### 3.2 Captura no-intrusiva en el cliente OpenAI

Modificar `backend/app/utils/openai_client.py` para:

- Capturar siempre el request payload completo antes del POST
- Capturar la response RAW antes de parsear
- Pasar ambos a una función callback `on_call_complete(request, response, metadata)` que persiste en `llm_audit_log`
- **Nunca alterar/sanitizar** el payload — guardar exactamente como se envió/recibió

### 3.3 Endpoints nuevos

| Método | Endpoint | Propósito |
|--------|----------|-----------|
| GET | `/documents/{id}/llm-audit` | Lista de todas las llamadas LLM del documento (paginado, con filtros: pass_number, call_purpose, has_error) |
| GET | `/documents/{id}/llm-audit/{paragraph_index}` | Detalle de las 1-2 llamadas para un párrafo específico — request + response RAW |
| GET | `/documents/{id}/llm-audit/diff/{paragraph_index}` | Comparativa estructurada: original / corrected_pass1 / corrected_pass2 / prompts ambas pasadas |

**Archivos a modificar:**
- `backend/app/models/llm_audit_log.py` — NUEVO modelo
- `backend/app/utils/openai_client.py` — añadir hook de captura RAW
- `backend/app/api/v1/documents.py` — 3 endpoints nuevos
- `backend/app/main.py` — migración ALTER/CREATE TABLE para `llm_audit_log` y `document_global_context`

---

## PILAR 4 — Panel de Auditoría Humana (Frontend)

### 4.1 Nueva pestaña "Auditoría LLM" en detalle de documento

**Archivo nuevo:** `frontend/src/components/LLMAuditPanel.tsx`

**Estructura del panel:**

```
┌──────────────────────────────────────────────────────────────┐
│ AUDITORÍA LLM — Documento {filename}                         │
├──────────────────────────────────────────────────────────────┤
│ Stats: 50 llamadas LLM · 30 párrafos auditados · 12 reversiones detectadas │
│                                                              │
│ Filtros: [Solo con cambios P1↔P2] [Reversiones] [Errores]    │
├──────────────────────────────────────────────────────────────┤
│ Tabla de párrafos:                                           │
│   #5 [body:5] [editorial] ✓ 2 pasadas — 1 reversión          │
│   #6 [body:6] [cheap]      ✓ 2 pasadas — 0 reversiones       │
│   #7 [titulo] [skip]       — sin LLM                         │
│   ...                                                        │
└──────────────────────────────────────────────────────────────┘
```

Al expandir un párrafo:

```
┌────────────────────────────────────────────────────────────┐
│ Párrafo #5 — body:5                                        │
├────────────────────────────────────────────────────────────┤
│ ORIGINAL:                                                  │
│   "La tokenización semántica es una cosa importante..."    │
├────────────────────────────────────────────────────────────┤
│ PASADA 1 (Corrección Mecánica)                             │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ Prompt enviado: [▼ ver completo]                    │    │
│ │ Respuesta cruda OpenAI: [▼ ver JSON]                │    │
│ └─────────────────────────────────────────────────────┘    │
│ Resultado P1:                                              │
│   "La colonización semántica resulta importante..."        │
│   ⚠ Posible destrucción: tokenización → colonización       │
├────────────────────────────────────────────────────────────┤
│ PASADA 2 (Auditoría Contextual)                            │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ Prompt enviado: [▼ ver completo]                    │    │
│ │ Respuesta cruda OpenAI: [▼ ver JSON]                │    │
│ └─────────────────────────────────────────────────────┘    │
│ Resultado P2:                                              │
│   "La tokenización semántica resulta indispensable..."     │
│   ✓ Reversión: "colonización" → "tokenización" (técnico)   │
│   ✓ Mejora: "es una cosa importante" → "resulta indisp..." │
└────────────────────────────────────────────────────────────┘
```

### 4.2 Funcionalidades del panel

- **Diff destacado** (rojo/verde) entre Original / Pasada 1 / Pasada 2
- **Banner visible** cuando Pasada 2 revirtió cambios de Pasada 1 ("Reversión por contexto")
- **Visor de prompt RAW** colapsable con resaltado JSON
- **Métricas por párrafo:** tokens consumidos en cada pasada, latencia, costo
- **Filtros:** solo párrafos con reversiones, solo errores LLM, por sección, por ruta

### 4.3 Vista global de costos por pasada

Extender pestaña "Costos" (`frontend/src/app/costs/page.tsx`) para diferenciar:

- Tokens y costo de Pasada 1 vs Pasada 2
- Costo del análisis global (Etapa C.6)
- Comparativa de inversión por documento

**Archivos a modificar:**
- `frontend/src/components/LLMAuditPanel.tsx` — NUEVO
- `frontend/src/app/documents/[id]/page.tsx` — añadir nueva pestaña "Auditoría LLM"
- `frontend/src/lib/api.ts` — tipos y funciones para los 3 nuevos endpoints
- `frontend/src/components/CorrectionHistory.tsx` — badge de "Reversión P2" en patches afectados
- `frontend/src/app/costs/page.tsx` — desglose por pasada

---

## Orden de implementación (sprints)

### Sprint A — Contexto Global (Pilar 1)
1. Modelo `document_global_context` + migración Alembic-like en `main.py`
2. Etapa C.6 `analyze_global_context_sync()` con muestreo estratificado
3. Bloque CONTEXTO GLOBAL en `prompt_builder.py`
4. Ampliar tokens de salida (`config.py`) y ventana de contexto previo

### Sprint B — Trazabilidad RAW (Pilar 3)
1. Modelo `llm_audit_log` + migración
2. Hook de captura en `openai_client.py` (request/response RAW)
3. Endpoints `/llm-audit`, `/llm-audit/{idx}`, `/llm-audit/diff/{idx}`

### Sprint C — Doble Pasada (Pilar 2)
1. Refactor `_correct_single_paragraph` → `_run_pass1_mechanical` + `_run_pass2_contextual`
2. Nuevo módulo `audit_pass.py` con prompts de auditoría contextual
3. Nuevos campos en `Patch`: `corrected_pass1_text`, `pass1_changes_json`, `pass2_audit_json`
4. Quality gates aplicados sobre salida de Pasada 2
5. Routing: decidir Pasada 2 obligatoria/opcional según rewrite_ratio P1 y nivel de intervención

### Sprint D — Panel Frontend (Pilar 4)
1. `LLMAuditPanel.tsx` con tabla expandible y diff
2. Visor de prompts/responses RAW colapsable
3. Filtros (reversiones, errores, sección)
4. Integración en pestañas de detalle de documento
5. Desglose de costos por pasada

### Sprint E — Validación end-to-end
1. Reprocesar `stylia_test_documento_con_errores.docx` con doble pasada
2. Verificar: tasa de corrección sube de 56% a ≥75%
3. Verificar: las 3 regresiones críticas (STYLIA→ITALIA, tokenización→colonización) se revierten en Pasada 2
4. Validar panel de auditoría muestra los prompts/responses RAW intactos
5. Comparar costo total contra baseline (esperado: 2-3× el costo actual, aceptable según el usuario)

---

## Archivos a crear y modificar (resumen)

### NUEVOS archivos
| Archivo | Propósito |
|---------|-----------|
| `backend/app/models/document_global_context.py` | "ADN editorial" del documento |
| `backend/app/models/llm_audit_log.py` | Tabla paralela RAW de cada llamada LLM |
| `backend/app/services/audit_pass.py` | Lógica de Pasada 2 (auditoría contextual) |
| `frontend/src/components/LLMAuditPanel.tsx` | Panel de auditoría humana con prompts/responses RAW |

### MODIFICADOS
| Archivo | Cambios |
|---------|---------|
| `backend/app/services/correction.py` | Refactor a doble pasada; integrar contexto global |
| `backend/app/services/prompt_builder.py` | Bloque CONTEXTO GLOBAL; ventana ampliada; `build_audit_user_prompt()` |
| `backend/app/services/analysis.py` | Etapa C.6 análisis global |
| `backend/app/utils/openai_client.py` | Hook de captura RAW request/response |
| `backend/app/services/complexity_router.py` | Decisión de Pasada 2 obligatoria/opcional |
| `backend/app/models/patch.py` | +`corrected_pass1_text`, `pass1_changes_json`, `pass2_audit_json` |
| `backend/app/api/v1/documents.py` | 3 endpoints `/llm-audit/*` |
| `backend/app/main.py` | Migraciones para tablas nuevas |
| `backend/app/config.py` | Tokens 2000/4000/6000; settings de doble pasada |
| `frontend/src/app/documents/[id]/page.tsx` | Pestaña "Auditoría LLM" |
| `frontend/src/lib/api.ts` | Tipos y funciones nuevos endpoints |
| `frontend/src/components/CorrectionHistory.tsx` | Badge "Reversión P2" |
| `frontend/src/app/costs/page.tsx` | Desglose por pasada |

---

## Verificación end-to-end

1. **Pre-flight:** `GET /api/v1/health/llm` retorna `status:ok`, modelo correcto
2. **Subir documento de prueba** (`stylia_test_documento_con_errores.docx`) con perfil "no_ficcion_general"
3. **Verificar Etapa C.6:** existe registro en `document_global_context` con `global_summary`, `dominant_voice`, `protected_globals_json` incluyendo "STYLIA" y "tokenización"
4. **Verificar Pasada 1 + Pasada 2 en BD:**
   - Tabla `llm_audit_log` tiene 2 entries por párrafo procesado (excepto skip)
   - `request_payload` incluye el bloque CONTEXTO GLOBAL en Pasada 2
   - `Patch.corrected_pass1_text` ≠ `Patch.corrected_text` cuando hubo reversión
5. **Verificar reversiones críticas:**
   - "STYLIA" en el documento NO se convierte a "ITALIA" en `corrected_text` final (Pasada 2 revirtió la destrucción de Pasada 1)
   - "tokenización semántica" preservado en el resultado final
6. **Verificar panel frontend:**
   - Pestaña "Auditoría LLM" muestra los párrafos con badge de reversiones
   - Al expandir un párrafo afectado, se ven los prompts RAW de ambas pasadas
   - El JSON crudo de la respuesta OpenAI es legible y completo
7. **Métricas finales esperadas:**
   - Tasa de corrección ≥ 75% (subida desde 56%)
   - 0 regresiones críticas (STYLIA, tokenización preservados)
   - Costo por documento aproximadamente 2-3× el baseline (aceptable)
   - Latencia total ≤ 2× baseline

---

## Riesgos asumidos

- **Costo de tokens 2-3× mayor** por Pasada 2 + análisis global. El usuario explícitamente acepta este trade-off ("la calidad es la prioridad absoluta").
- **`llm_audit_log` puede crecer rápido** (2 entradas por párrafo × N documentos). Mitigación: TTL configurable o particionado por mes para operación productiva.
- **Pasada 2 puede introducir nuevas alucinaciones** si el contexto global está mal calibrado. Mitigación: gates ejecutados sobre P2; si P2 falla un gate crítico, fallback a P1.
- **Latencia aumenta** (doble llamada por párrafo). Mitigación: paralelización en lotes (la infra de `correction_batches` ya existe y soporta paralelismo).
- **Sin Alembic todavía:** las migraciones se hacen vía `ALTER TABLE IF NOT EXISTS` en `main.py` (mismo patrón que Plan v3 ya implementado). Deuda técnica conocida.
