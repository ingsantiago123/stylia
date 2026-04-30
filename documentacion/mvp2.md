# STYLIA — Rediseño del Pipeline de Corrección de Estilos

## Síntesis ejecutiva

El pipeline actual de STYLIA (LanguageTool → GPT con prompt genérico y ventana fija de 3 párrafos) funciona como MVP, pero opera a nivel local sin entender el documento como obra. El rediseño propone pasar de un **corrector automático de párrafos** a un **motor editorial con inteligencia contextual**, replicando las fases que sigue un corrector de estilos profesional humano.

La arquitectura se resume en una frase: **primero entender el texto, luego decidir cómo corregirlo, y solo después corregirlo.**

---

## 1. Cómo trabaja un corrector profesional (y por qué importa)

### La cadena editorial estándar en español

La industria editorial trabaja en fases secuenciales, cada una con alcance y herramientas distintas:

1. **Corrección de contenido** — Estructura, argumentación, organización
2. **Corrección de estilo** — Claridad, fluidez, cohesión, tono, léxico, voz del autor
3. **Corrección ortotipográfica** — Ortografía, puntuación, tipografía según RAE
4. **Corrección de pruebas** — Verificación sobre maqueta final

La corrección de estilo se enfoca en el *cómo se dice*: mejora redacción, tono y sintaxis. La ortotipográfica se enfoca en el *qué está escrito*: corrige según norma. Son complementarias, no intercambiables.

### Lo que un corrector resuelve ANTES de tocar una coma

Un profesional no entra corrigiendo. Primero responde:

| Pregunta | Impacto en la corrección |
|----------|-------------------------|
| ¿Qué clase de texto es? | Define qué reglas aplican y cuáles no |
| ¿Para quién está escrito? | Calibra vocabulario, complejidad, registro |
| ¿Qué función cumple? | Narrar ≠ enseñar ≠ persuadir ≠ vender |
| ¿Qué voz debe preservar? | Limita la intervención del corrector |
| ¿Qué tanto puede intervenir? | Sutil vs. profundo |
| ¿Qué NO debe tocar? | Términos técnicos, modismos, ritmo intencional |

### Los tres niveles de lectura

**Macro** (documento como obra): coherencia global, tono sostenido, registro uniforme, consistencia terminológica, progresión de ideas, densidad.

**Meso** (capítulo/sección/párrafo): transiciones, arranque y cierre de párrafos, conectores, orden lógico, redundancias, saltos de registro.

**Micro** (frase y palabra): sintaxis, precisión léxica, cacofonías, muletillas, ambigüedad, puntuación estilística, ritmo, concordancia, repeticiones.

**Diferencia fundamental con un corrector automático**: el profesional no corrige "errores"; corrige según una **intención editorial**. Muchas veces decide "esto no se toca".

### Cómo cambia según el contexto

**Texto infantil (6-8 años)**:
- Simplifica sintaxis, baja densidad conceptual
- Vocabulario concreto, ritmo oral
- Conserva repeticiones útiles (memorización, musicalidad)
- Error típico de IA: "mejorar" tanto que deja de ser infantil

**Libro de psicología**:
- Precisión terminológica > variedad léxica
- Definiciones estables, no ornamentación
- Distinguir afirmación vs hipótesis vs correlación
- Error típico de IA: reemplazar términos técnicos por sinónimos "más bonitos"

**Mismo tema, diferente público**:
- Psicología para especialistas → mínima intervención léxica
- Psicología para estudiantes → aclarar sin banalizar
- Psicología para público general → simplificar sin perder rigor
- Psicología para autoayuda → calidez, segunda persona, ejemplos concretos

### Preservar la voz del autor

Regla de la industria: "En la corrección de estilo se corrige todo menos el estilo del autor." ACES (The Society for Editing) define tres pasos: leer antes de editar para familiarizarse, evaluar cada cambio preguntando si altera la voz, y revisar después para confirmar que la voz permanece intacta.

Principio operativo: "Si la única razón para cambiar algo es 'yo nunca lo escribiría así', se deja como está."

Para STYLIA esto significa: las correcciones deben ser **sugerencias categorizadas con explicación**, nunca aplicación automática irreversible.

---

## 2. Arquitectura del pipeline rediseñado

### Pipeline actual (MVP)

```
Etapa A: Ingesta (DOCX → PDF, conteo páginas)
Etapa B: Extracción (layout PyMuPDF, previews)
[Etapa C: no existe]
Etapa D: Corrección (LanguageTool → GPT genérico, ventana 3 párrafos)
Etapa E: Renderizado (aplicar patches, generar outputs)
```

### Pipeline rediseñado

```
Etapa A: Ingesta
  └─ Sin cambios

Etapa B: Extracción estructural
  └─ Sin cambios + clasificación de párrafos por tipo

Etapa C: Análisis editorial (NUEVA)
  ├─ C.1: Detección de género/audiencia/registro
  ├─ C.2: Generación del brief editorial (style profile)
  ├─ C.3: Resumen por secciones
  ├─ C.4: Extracción de glosario y términos protegidos
  └─ C.5: Clasificación de párrafos y asignación de políticas

Etapa D: Corrección local guiada
  ├─ D.0: Normalización ligera (espacios, tipología, idioma)
  ├─ D.1: LanguageTool (ortografía/gramática, determinista)
  ├─ D.2: LLM Pasada Léxica (modelo barato: muletillas, redundancias, repeticiones)
  ├─ D.3: LLM Pasada Estilística (modelo potente: coherencia, tono, registro, flujo)
  └─ D.4: Quality gates (similitud semántica, ratio reescritura, términos protegidos)

Etapa E: Armonización global (NUEVA sub-etapa)
  ├─ Consistencia terminológica cross-documento
  ├─ Consistencia de tono y registro
  ├─ Consistencia de persona gramatical y tiempos verbales
  └─ Detección de sobrecorrección y tics del modelo

Etapa F: Renderizado
  └─ Generar DOCX con track changes + PDF corregido

Etapa G: Revisión humana (futuro)
  └─ Aceptar/rechazar/editar → dataset para mejora continua
```

---

## 3. Etapa C — Análisis Editorial (el cambio más importante)

Esta etapa llena el hueco natural que ya existe en el pipeline. Se ejecuta una sola vez por documento antes de cualquier corrección.

### C.1: Detección automática

Analizar muestras del documento (portada, índice, primeros N párrafos, primeros párrafos de cada capítulo) con una llamada barata (GPT-4o-mini) para inferir:

- Género y subgénero
- Audiencia probable
- Registro dominante
- Nivel lector estimado
- Variante del español

### C.2: Brief editorial (style profile)

Combinar tres fuentes:

1. **Configuración explícita del usuario** (selecciona perfil + ajustes)
2. **Perfiles predeterminados** (templates por género/audiencia)
3. **Inferencia automática** (lo detectado en C.1)

El usuario elige un perfil base y ajusta. El sistema completa lo que el usuario no configure con inferencia automática.

#### Salida: `document_style_profile`

```json
{
  "language": "es",
  "locale": "es-CO",
  "genre": "psicologia_divulgativa",
  "audience": {
    "type": "adultos_no_especialistas",
    "age_range": "25+",
    "expertise_level": "bajo"
  },
  "register": "formal_claro",
  "tone": "reflexivo",
  "intervention_level": "sutil",
  "preserve_author_voice": true,
  "preserve_rhetorical_repetition": false,
  "prefer_terminological_consistency": true,
  "allow_sentence_split": true,
  "allow_paragraph_split": false,
  "allow_paragraph_reordering": false,
  "max_rewrite_ratio": 0.35,
  "max_expansion_ratio": 1.10,
  "target_readability_inflesz": [55, 65],
  "target_sentence_length": "media",
  "style_priorities": [
    "claridad",
    "fluidez",
    "cohesion",
    "precision_lexica"
  ],
  "protected_terms": ["apego", "sesgo cognitivo", "disonancia cognitiva"],
  "forbidden_changes": [
    "simplificar_terminos_tecnicos",
    "cambiar_definiciones"
  ],
  "lt_disabled_rules": [],
  "human_review_mode": "suggestions"
}
```

### C.3: Resúmenes por sección

Por cada capítulo/sección, generar un mini-resumen (~50 palabras):
- Tema de la sección
- Propósito del bloque
- Terminología activa
- Tono local
- Transición con sección anterior

### C.4: Glosario y términos protegidos

Extraer automáticamente:
- Términos técnicos recurrentes → proteger de sinónimos
- Nombres propios → no tocar
- Decisiones terminológicas → normalizar (ej: "internet" vs "Internet")

### C.5: Clasificación de párrafos

Cada párrafo recibe un `paragraph_type` y una política asociada:

| Tipo | Política de corrección |
|------|----------------------|
| `titulo` | Intervención mínima |
| `subtitulo` | Intervención mínima |
| `narrativo` | Corrección completa según perfil |
| `explicacion_tecnica` | Precisión > brillo, proteger términos |
| `dialogo` | Preservar oralidad, mínima intervención |
| `cita` | No tocar contenido, solo formato |
| `pie_imagen` | Concisión, corrección ortográfica solo |
| `celda_tabla` | Máxima precisión, cero expansión |
| `encabezado` | No tocar |
| `footer` | No tocar |
| `lista` | Paralelismo sintáctico, concisión |

Ya tienes las ubicaciones `body`, `table`, `header`, `footer`. Solo falta agregar la clasificación semántica del contenido.

---

## 4. Perfiles predeterminados

### Perfiles base disponibles

| Perfil | Registro | Intervención | Repetición | Long. frase | INFLESZ objetivo |
|--------|----------|-------------|-----------|-------------|-------------------|
| `infantil_6_8` | informal_claro | moderada | tolerar | 8-12 palabras | >80 |
| `infantil_9_12` | neutro_claro | moderada | reducir | 12-16 palabras | 70-80 |
| `juvenil` | neutro | moderada | reducir | 14-20 palabras | 65-75 |
| `novela_literaria` | variable | sutil | según autor | variable | 55-70 |
| `ensayo` | formal | sutil | reducir | 18-25 palabras | 50-65 |
| `psicologia_academica` | formal_tecnico | mínima | mantener técnica | 20-30 palabras | 40-55 |
| `psicologia_divulgativa` | formal_claro | sutil | reducir no-técnica | 15-22 palabras | 55-65 |
| `manual_tecnico` | tecnico | mínima | mantener | 15-25 palabras | 45-60 |
| `texto_marketing` | persuasivo | agresiva | eliminar | 10-18 palabras | 65-80 |
| `no_ficcion_general` | neutro | moderada | reducir | 15-22 palabras | 55-70 |

### Ejemplo de cómo cambia la corrección con perfiles

**Texto original** (oración académica):
> "La implementación de las metodologías pedagógicas innovadoras que han sido propuestas por los investigadores del ámbito educativo podría contribuir significativamente a la mejora sustancial del rendimiento académico de los estudiantes que presentan dificultades de aprendizaje."

**Con perfil `infantil_6_8`**:
> "Los maestros pueden usar nuevas formas de enseñar. Así, los niños que tienen problemas para aprender pueden mejorar mucho en la escuela."

**Con perfil `psicologia_academica`**:
> Corrección mínima: convertir cláusula relativa en aposición, eliminar "que han sido", quitar redundancia "sustancial" (ya hay "significativamente").

**Con perfil `texto_marketing`**:
> "¿Tu hijo tiene dificultades en la escuela? Los nuevos métodos de enseñanza pueden cambiar su futuro."

---

## 5. Corrección local guiada (Etapa D rediseñada)

### Arquitectura multi-pasada con ruteo

La decisión técnica clave: **no todos los párrafos necesitan todas las pasadas, ni el mismo modelo**.

```
Párrafo
  → D.0: Normalización (espacios, encoding, detección idioma)
  → D.1: LanguageTool (siempre, determinista, gratis)
  → Router de complejidad:
      ├─ Ruta rápida (skip LLM):
      │   Si está limpio en LT + sintaxis simple + no es transición
      │   + no tiene riesgo tonal → no enviar al LLM
      │
      ├─ Ruta barata (GPT-4o-mini / Claude Haiku):
      │   Para: títulos, tablas, listas, párrafos limpios,
      │   textos rutinarios, correcciones léxicas simples
      │
      └─ Ruta editorial (GPT-4o / Claude Sonnet):
          Para: transiciones, párrafos densos, definiciones,
          narración delicada, diálogos, párrafos con riesgo de tono
  → D.4: Quality gates (siempre)
```

### El prompt ya no es genérico

El LLM no recibe "corrige estilo y mejora claridad". Recibe:

1. **System prompt estático** (cacheable, ~800-1200 tokens):
   - Rol: corrector de estilo profesional en español
   - Reglas completas de estilo (normas RAE de puntuación, no inglés)
   - Instrucciones de formato de salida (JSON schema)
   - Ejemplos few-shot de correcciones correctas e incorrectas
   - Ejemplos negativos ("esto NO se corrige")
   - Restricciones y casos límite

2. **User prompt dinámico** (variable, ~200-500 tokens):
   - Brief editorial comprimido (perfil codificado, no texto largo)
   - Resumen de sección actual (~50 palabras)
   - Política del tipo de bloque
   - Nivel de intervención permitido
   - 1 párrafo previo corregido
   - Párrafo actual
   - Opcionalmente 1 párrafo siguiente original

### Contexto jerárquico reemplaza ventana fija

En lugar de 3 párrafos anteriores crudos:

| Componente | Tokens aprox. | Función |
|-----------|--------------|---------|
| Brief editorial codificado | ~50 | Calibrar toda la corrección |
| Resumen de sección | ~50 | Contexto temático |
| 1 párrafo previo corregido | ~100-200 | Continuidad inmediata |
| Párrafo actual | ~100-200 | Texto a corregir |
| 1 párrafo siguiente (opcional) | ~100-200 | Resolver ambigüedad |
| Registro de términos normalizados | ~30-50 | Consistencia |
| **Total contexto dinámico** | **~330-750** | — |

Comparado con 3 párrafos crudos (~300-600 tokens) más el prompt genérico repetido (~200 tokens), el contexto jerárquico da **más información relevante en igual o menos tokens**.

### Prompt codificado (no texto largo)

En vez de repetir instrucciones en texto:

```
"Mantén el tono reflexivo, mejora la claridad, evita sonar a IA,
no cambies el significado, ten en cuenta que el público son adultos
no especialistas..."
```

Se envía internamente:

```json
{
  "profile": "PSI_DIVULG_SUTIL",
  "block_policy": "BODY_EXPLANATORY",
  "intervention": "LIGHT",
  "preserve": ["VOICE", "TERMS", "MEANING"],
  "constraints": ["MAX_REWRITE_35", "MAX_LEN_110"],
  "section_topic": "Teoría del apego en relaciones adultas",
  "active_terms": ["apego seguro", "figura de apego", "modelo operante interno"]
}
```

El servidor traduce esos códigos a instrucciones cortas y específicas para el prompt.

### Schema de salida estructurado

```json
{
  "action": "correct",  // "correct" | "flag" | "skip"
  "corrected_text": "Texto corregido aquí",
  "changes": [
    {
      "original_fragment": "fragmento exacto",
      "corrected_fragment": "propuesta",
      "category": "redundancia",  // coherencia|cohesion|lexico|registro|claridad|redundancia|estructura|puntuacion|ritmo|muletilla
      "severity": "sugerencia",   // critico|importante|sugerencia
      "explanation": "Se eliminó la redundancia 'mejora sustancial' porque ya se usó 'significativamente'."
    }
  ],
  "warnings": [],  // alertas sobre intervenciones dudosas
  "confidence": 0.85,
  "rewrite_ratio": 0.12
}
```

El campo `action` es clave: permite que el modelo decida **no tocar** un párrafo (action: "skip") o **advertir sin reescribir** (action: "flag").

### Quality gates (D.4)

Antes de aceptar cualquier corrección del LLM:

| Gate | Criterio | Si falla |
|------|---------|---------|
| Similitud semántica | BERTScore F1 > 0.85 entre original y corrección | Descartar corrección |
| Ratio de reescritura | Distancia de edición < `max_rewrite_ratio` del perfil | Descartar o flag |
| Expansión | `len(corregido) / len(original)` < `max_expansion_ratio` | Descartar |
| Términos protegidos | Todos los `protected_terms` presentes en output | Descartar si falta alguno |
| Tono fuera de perfil | Análisis rápido de registro (puede ser heurístico) | Flag para revisión humana |
| Preservación de significado | NLI check: no contradicción entre original y corregido | Descartar |

---

## 6. Optimización de tokens y costos

### Prompt caching (el ahorro más importante)

El system prompt estático (~800-1200 tokens) permanece idéntico en las 250+ llamadas de un libro típico. Esto activa el prompt caching automáticamente:

| Proveedor | Descuento cache read | Requisito |
|-----------|---------------------|-----------|
| OpenAI | 50% en input | Prefijo ≥1,024 tokens idéntico |
| Anthropic | 90% en input | TTL 5 min (se refresca con cada hit) |

**Regla crítica**: el system prompt NO debe contener timestamps, contadores, IDs de párrafo ni ningún dato dinámico. Todo lo variable va en el user prompt.

### Batch API para procesamiento no-urgente

| Proveedor | Descuento | Entrega |
|-----------|-----------|---------|
| OpenAI | 50% | ≤24 horas |
| Anthropic | 50% | ≤24 horas |

Los descuentos se acumulan: batch + cache = hasta 95% de ahorro en Anthropic.

### Costos estimados por libro de 100 páginas (~250 párrafos)

**Escenario: Arquitectura híbrida con batch + caching**

| Pasada | Modelo | Costo estimado |
|--------|--------|---------------|
| Pasada Léxica (D.2) | GPT-4o-mini (batch+cache) | ~$0.01 |
| Pasada Estilística (D.3) | Claude Sonnet 4.5 (batch+cache) | ~$0.05-0.08 |
| Análisis editorial (C) | GPT-4o-mini (una llamada) | ~$0.001 |
| Armonización (E) | GPT-4o-mini (una llamada) | ~$0.002 |
| **Total por libro** | — | **$0.06-0.10** |

### Detector de "necesita LLM o no"

Si un párrafo cumple TODAS estas condiciones:
- Limpio en LanguageTool (0 matches)
- Sintaxis simple (no subordinadas anidadas)
- No contiene muletillas conocidas
- No es párrafo de transición
- No tiene riesgo tonal (no es primer/último párrafo de sección)

→ Skip LLM o revisión mínima. Esto puede eliminar 20-40% de llamadas al API.

### Cache por hash normalizado

Muchos documentos repiten encabezados, disclaimers, fórmulas, pies. Si `hash(normalize(text) + profile_id)` ya existe con el mismo perfil editorial, reutilizar resultado.

---

## 7. Selección de modelos por pasada

### Recomendación

| Pasada | Modelo recomendado | Justificación |
|--------|--------------------|--------------|
| C: Análisis editorial | GPT-4o-mini | Una sola llamada, tarea de clasificación, barato |
| D.2: Léxica | GPT-4o-mini | Patrones simples (muletillas, repeticiones), alto volumen |
| D.3: Estilística | Claude Sonnet 4.5 | Mejor español natural, preserva voz del autor mejor |
| E: Armonización | GPT-4o-mini | Una sola llamada, verificación de consistencia |

**Trade-off Claude vs GPT para D.3**: Claude Sonnet tiende a producir español más natural y es mejor preservando la voz autoral. GPT-4o tiene structured outputs con 100% de cumplimiento de schema vía constrained decoding. La librería **Instructor** permite usar el mismo schema Pydantic con ambos proveedores, facilitando A/B testing y cambio entre ellos.

**Alternativa si se prioriza costo**: GPT-4o-mini para todo. Pierde calidad en estilística profunda pero el costo baja a ~$0.02/libro.

**Alternativa si se prioriza calidad**: GPT-4o o Claude Sonnet para D.3. Sube a ~$0.10-0.15/libro pero la corrección estilística es notablemente superior.

---

## 8. Métricas de legibilidad para español

### Índice de Szigriszt-Pazos + Escala INFLESZ

La escala INFLESZ es la referencia calibrada para español:

| Puntuación | Nivel | Ejemplo |
|-----------|-------|---------|
| <40 | Muy Difícil | Revistas científicas |
| 40-55 | Algo Difícil | Publicaciones especializadas |
| 55-65 | Normal | Periódicos, revistas generales |
| 65-80 | Bastante Fácil | Libros de texto escolares |
| >80 | Muy Fácil | Material infantil |

Cada perfil de corrección incluye un rango INFLESZ objetivo. Post-corrección, verificar que el resultado esté dentro del rango. Si no cumple → re-prompting o flag.

**Implementación**: librería Python `legibilidad` (pip install legibilidad) computa todos los índices principales para español.

---

## 9. Cambios en el modelo de datos

### Nuevas tablas/campos

**Tabla `document_profiles`** (nueva):
```
id, doc_id (FK), genre, subgenre, audience_type, audience_age,
audience_expertise, register, tone, intervention_level,
preserve_author_voice, max_rewrite_ratio, max_expansion_ratio,
target_inflesz_min, target_inflesz_max, style_priorities (JSONB),
protected_terms (JSONB), forbidden_changes (JSONB),
source (user|inferred|preset), preset_name
```

**Tabla `section_summaries`** (nueva):
```
id, doc_id (FK), section_index, section_title, summary_text,
topic, local_tone, active_terms (JSONB), transition_from_previous
```

**Tabla `term_registry`** (nueva):
```
id, doc_id (FK), term, normalized_form, first_occurrence_paragraph,
is_protected, decision (use_as_is|normalize_to)
```

**Campos nuevos en `blocks`**:
```
paragraph_type (titulo|narrativo|explicacion|dialogo|cita|tabla|lista|etc)
risk_score (float, 0-1)
requires_llm (boolean)
section_id (FK a section_summaries)
```

**Campos nuevos en `patches`**:
```
category (coherencia|lexico|registro|claridad|redundancia|etc)
severity (critico|importante|sugerencia)
explanation (text)
confidence (float)
rewrite_ratio (float)
semantic_similarity (float)
editorial_policy_used (text)
model_used (text)
pass_number (1=LT, 2=lexica, 3=estilistica)
```

### Extensión de `config_json` en `documents`

El `config_json` existente se extiende para ser el centro del comportamiento editorial. Ver la estructura completa en la sección 3 (C.2).

---

## 10. Lo que NO hay que hacer

### El gran error: prompt largo omnisciente

No meter todo en un prompt tipo: "Corrige estilo, mejora claridad, mantén tono, no cambies significado, ten en cuenta público, etc." Eso produce respuestas variables y caras.

En cambio: reglas persistentes estructuradas + perfiles + ruteo por tipo de texto + gates automáticos + prompt corto y específico.

### No empezar por fine-tuning

Primero hacer bien estas cuatro cosas:
1. Perfiles editoriales
2. Etapa de análisis
3. Ruteo y gates
4. Captura de feedback humano

Cuando haya cientos/miles de pares (original → corrección propuesta → corrección aceptada/rechazada/editada → perfil → tipo de bloque → audiencia), entonces sí considerar fine-tuning. Para corrección de estilo, un **sistema de preferencia y control** da más valor que un fine-tuning temprano.

### No destruir la rareza útil del autor

La IA tiende a: alisar, homogeneizar, explicar de más, normalizar el ritmo, volver todo "correcto" pero menos humano.

Medir y limitar:
- Ratio de reescritura
- Sustitución léxica excesiva
- Pérdida de idiosincrasia
- Uniformidad artificial

En infantil, cierta repetición es virtud. En psicología, la repetición terminológica es obligación. En literatura, una sintaxis marcada puede ser voz.

---

## 11. Track changes en DOCX

Hallazgo crítico: **python-docx NO soporta nativamente track changes** (issue #340 abierto desde 2016).

**Solución recomendada**: **Python-Redlines** (github.com/JSv4/Python-Redlines) — compara dos archivos .docx y genera un documento con tracked changes real de Open XML. Alternativa: manipulación directa de XML con el workflow unpack → edit → repack que tu skill de DOCX ya soporta.

---

## 12. Plan de implementación por fases

### Fase 2A (inmediata, sin cambiar pipeline existente)
1. Extender `config_json` con estructura de perfil editorial completo
2. Crear 10 perfiles predeterminados con valores por defecto
3. UI para selección de perfil + ajustes
4. Reemplazar prompt genérico por prompts parametrizados según perfil
5. Agregar campos `category`, `severity`, `explanation` a patches

### Fase 2B (Etapa C + mejoras Etapa D)
1. Implementar Etapa C de análisis editorial
2. Clasificación de párrafos por tipo
3. Contexto jerárquico (resumen sección + 1 párrafo) en lugar de 3 fijos
4. Router de complejidad (skip LLM / ruta barata / ruta editorial)
5. Quality gates básicos (ratio reescritura, expansión, términos protegidos)

### Fase 2C (multi-modelo + optimización)
1. Separar Pasada Léxica (modelo barato) de Pasada Estilística (modelo potente)
2. Implementar prompt caching (system prompt estático)
3. Implementar Batch API para procesamiento no-urgente
4. Cache por hash normalizado
5. Métricas INFLESZ post-corrección

### Fase 2D (armonización + revisión humana)
1. Etapa E de armonización global
2. Revisión humana (aceptar/rechazar/editar)
3. Track changes real en DOCX con Python-Redlines
4. Captura de feedback como dataset

### Fase 3+ (inteligencia)
1. BERTScore y NLI como quality gates avanzados
2. LLM-as-judge para evaluación automática
3. Fine-tuning con datos de revisión humana
4. Modelo de ranking/preferencia para elegir mejor corrección

---

## 13. Resumen de decisiones técnicas

| Decisión | Elegida | Razón |
|----------|---------|-------|
| Multi-pasada vs pasada única | Multi-pasada (3 niveles) | Replica proceso profesional, auditable por categoría, permite ruteo |
| Modelos diferentes por pasada | Sí | GPT-4o-mini para léxico (barato), Claude Sonnet para estilo (calidad) |
| Contexto jerárquico vs ventana fija | Jerárquico | Más información relevante en igual o menos tokens |
| Perfiles configurables | Sí, 7 dimensiones + 10 presets | Transforma corrección genérica en corrección editorial real |
| Quality gates | Sí, 6 gates mínimos | Previene sobrecorrección, preserva voz, detecta alucinaciones |
| Prompt caching | Sí, system prompt estático | Ahorro 50-90% en input tokens |
| Batch API | Sí, para procesamiento no-urgente | 50% adicional |
| Track changes | Python-Redlines o XML directo | python-docx no soporta tracked changes |
| Fine-tuning | No ahora, sí después de capturar datos | Primero perfiles + gates + feedback humano |
| Métrica de legibilidad | INFLESZ (español) | Escala calibrada con corpus, librería Python disponible |