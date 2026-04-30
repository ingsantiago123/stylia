# Rediseño del pipeline de corrección de estilos de STYLIA con LLMs

El pipeline óptimo para STYLIA debe replicar el proceso multi-pasada que usan los correctores profesionales, no intentar hacer todo en una sola llamada al LLM. La investigación confirma que **separar las pasadas por tipo de corrección** (ortografía → léxico → estilo/coherencia) produce resultados más precisos, auditables y configurables, a un costo sorprendentemente bajo: entre **$0.02 y $0.16 por libro de 100 páginas** usando Batch API + prompt caching. La clave técnica es maximizar el system prompt estático cacheable, usar modelos baratos para pasadas simples y reservar modelos potentes para el análisis estilístico profundo, exponiendo perfiles configurables que parametricen vocabulario, complejidad sintáctica, tono y registro según el tipo de texto y público objetivo.

---

## Cómo trabaja un corrector de estilos profesional

La industria editorial en español divide el trabajo en **dos macro-fases**: antes de maquetación (corrección de contenido → corrección de estilo → corrección ortotipográfica) y después de maquetación (corrección de primeras y segundas pruebas). Esta secuencia no es arbitraria: cada fase tiene un alcance preciso y herramientas de referencia distintas.

La **corrección ortotipográfica** es superficial y normativa: corrige ortografía, puntuación y unifica criterios tipográficos (cursivas, comillas, versalitas) usando como referencia la *Ortografía de la lengua española* (RAE, 2010). Se considera **imprescindible** para cualquier publicación. La **corrección de estilo** opera a un nivel más profundo: aborda vocabulario impreciso, enriquecimiento léxico, muletillas, pleonasmos, coherencia, cohesión, ritmo, tono y registro, usando como referencia la *Nueva gramática* (RAE). Como resume Textovivo.es: "La ortotipográfica hace que el texto esté bien escrito; la de estilo hace que funcione mejor." La **corrección de pruebas** verifica que las correcciones anteriores se aplicaron correctamente sobre el texto ya maquetado.

En la tradición anglosajona, Flatpage y otros editores profesionales estructuran su trabajo en **pasadas secuenciales**: preparación del documento y hoja de estilo → edición profunda de mecánica y contenido → revisión del autor con control de cambios → corrección final de pruebas. Este modelo de pasadas secuenciales con verificación incremental es directamente trasladable a un pipeline técnico.

Un corrector de estilo profesional revisa en cada pasada aspectos específicos: errores de vocabulario e imprecisiones, riqueza léxica (sustitución de términos repetitivos por sinónimos adecuados), muletillas ("es decir", "esto es", "¿vale?"), concordancia gramatical, inconsistencias sintácticas, pleonasmos, coherencia y cohesión discursiva, claridad narrativa, tono y registro, ritmo y fluidez (variando longitud de oraciones, usando conectores), cacofonías y rimas internas no intencionales, y cumplimiento de la guía de estilo editorial. La corrección cambia sustancialmente según el tipo de texto: en **narrativa de ficción** se profundiza en técnica literaria, voz narrativa, verosimilitud y consistencia de personajes; en **literatura infantil** prima el ritmo, la cadencia y la simplicidad adaptada a la edad; en **texto académico** domina la claridad argumentativa, la consistencia terminológica y el formato de citas; en **texto comercial** se priorizan persuasión, concisión e impacto.

### Preservar la voz del autor no es opcional

"En la corrección de estilo se corrige todo menos el estilo del autor" (Revenga Ediciones). ACES (The Society for Editing) define tres pasos concretos: **leer antes de editar** para familiarizarse con el estilo, **evaluar cada cambio** preguntando si altera la voz característica, y **revisar después** para confirmar que la voz permanece intacta. El principio operativo es: "Si la única razón para revisar un texto es 'yo nunca lo escribiría así', dejo la frase como está" (Kerry Evans, Cell Press). En la práctica, esto se implementa mediante control de cambios donde el autor aprueba o rechaza cada corrección, y mediante la regla de consultar al autor ante la duda en lugar de hacer cambios unilaterales. Para el pipeline de STYLIA, esto implica que las correcciones deben ser **sugerencias categorizadas con explicación**, nunca aplicación automática irreversible.

---

## La arquitectura multi-pasada es superior a la pasada única

La investigación técnica confirma que cuando un solo modelo maneja planificación y ejecución simultáneamente, "debe resolver dos problemas cognitivos distintos en una pasada, y los LLMs no están optimizados para eso. Esto fuerza razonamiento redundante, relleno verboso y salidas más lentas y ruidosas." La separación en pasadas especializadas permite ajustar temperatura, especificidad del prompt y selección de modelo por tarea. En sistemas de producción con requisitos de alta precisión se han usado hasta **15 pasadas** donde se exige "100% de precisión y auditoría completa."

La arquitectura recomendada para STYLIA tiene esta estructura:

```
DOCX Input
  → [Parser] Extraer párrafos + metadatos
  → [Summarizer] Resumen del documento (GPT-4o-mini, una vez)
  → Para cada párrafo (ventana deslizante de 3 párrafos):
      → Pasada 1: LanguageTool (ortografía/gramática, determinista)
      → Pasada 2: Léxico (GPT-4o-mini, muletillas/repeticiones/redundancias)
      → Pasada 3: Estilo/Coherencia (GPT-4o o Claude Sonnet, tono/registro/flujo)
      → Merger de correcciones + actualización del registro de términos
  → [Verificación final] Pasada ligera sobre transiciones entre párrafos
  → [Output] DOCX con control de cambios + reporte JSON
```

La Pasada 1 con LanguageTool ya existe en STYLIA y es correcta: es determinista, gratuita y maneja bien el español. La **Pasada 2 con un modelo barato** (GPT-4o-mini a $0.15/MTok input) es suficiente para detectar patrones léxicos simples como muletillas, repeticiones y redundancias. La **Pasada 3 requiere un modelo potente** (GPT-4o a $2.50/MTok o Claude Sonnet 4.5 a $3.00/MTok) para el análisis complejo de coherencia, cohesión, tono, registro y fluidez. Claude Sonnet tiende a producir texto en español más natural y es mejor preservando la voz autoral, pero GPT-4o tiene mejor soporte para structured outputs con **100% de cumplimiento de schema** vía constrained decoding.

### El contexto acumulado se gestiona con tres mecanismos

Primero, un **resumen del documento completo** generado una sola vez al inicio (máximo 100 palabras: tema, tipo de texto, tono, público detectado, términos técnicos recurrentes). Segundo, una **ventana deslizante** que incluye el párrafo anterior, el actual y el siguiente. Tercero, un **registro de términos y decisiones estilísticas** que se actualiza con cada corrección (por ejemplo, si en el párrafo 2 se normalizó "internet" a "Internet", mantener esa decisión en el párrafo 15). Opcionalmente, después de procesar todos los párrafos, una pasada final ligera verifica las transiciones entre párrafos (última oración de cada párrafo contra primera del siguiente).

---

## Perfiles configurables que transforman las correcciones

Un sistema profesional de corrección debe exponer parámetros en siete dimensiones: **nivel de vocabulario** (básico, intermedio, avanzado, especializado), **longitud de oraciones** (8-12 palabras para niños de 6-8 años hasta 20-35 para textos académicos), **complejidad sintáctica** (profundidad máxima de subordinación, tolerancia a voz pasiva, ratio coordinación/subordinación), **registro de formalidad** (informal, neutro, formal, académico), **tolerancia a repeticiones** (alta en literatura infantil donde es pedagógica, muy baja en marketing), **tono** (neutro, cálido, autoritario, lúdico, persuasivo, didáctico) y **convenciones de género** (show-don't-tell, realismo en diálogos, lenguaje de cobertura).

El mismo texto corregido con diferentes perfiles produce resultados radicalmente distintos. Considérese esta oración académica: "La implementación de las metodologías pedagógicas innovadoras que han sido propuestas por los investigadores del ámbito educativo podría contribuir significativamente a la mejora sustancial del rendimiento académico de los estudiantes que presentan dificultades de aprendizaje." Para **literatura infantil (6-8 años)**: "Los maestros pueden usar nuevas formas de enseñar. Así, los niños que tienen problemas para aprender pueden mejorar mucho en la escuela." Para **texto académico**: la corrección es mínima — convertir la cláusula relativa en aposición, eliminar "que han sido" y quitar la redundancia "sustancial" (ya está "significativa"). Para **marketing**: "¿Tu hijo tiene dificultades en la escuela? Los nuevos métodos de enseñanza pueden cambiar su futuro. Descubre cómo."

### Las métricas de legibilidad en español anclan los perfiles a valores objetivos

El **índice de Szigriszt-Pazos** (1993) es la fórmula de referencia para español, y la **escala INFLESZ** (Barrio-Cantalejo, 2008) proporciona la interpretación calibrada más precisa: <40 = Muy Difícil (revistas científicas), 40-55 = Algo Difícil (publicaciones especializadas), 55-65 = Normal (revistas generales, periódicos), 65-80 = Bastante Fácil (libros de texto escolares, promedio 67.39), >80 = Muy Fácil (material infantil). Cada perfil de corrección debe incluir un rango objetivo INFLESZ y verificar post-corrección que el resultado esté dentro del rango, re-prompting si no lo cumple. La librería Python `legibilidad` (GitHub: alejandromunozes/legibilidad) computa todos los índices principales para español.

ProWritingAid, la herramienta más granular del mercado con **25+ reportes especializados**, calibra sus estadísticas (palabras sobreusadas, longitud de oraciones objetivo) contra **corpora de referencia publicados por género**. Este enfoque de calibración contra corpora es el estándar a emular. Grammarly estructura sus correcciones en cuatro categorías con código de color (Correctness en rojo, Clarity en azul, Engagement en verde, Delivery en púrpura) y permite configurar metas por documento en cuatro dimensiones: audiencia, formalidad, dominio e intención. Ambos modelos son directamente trasladables a los perfiles de STYLIA.

---

## Prompt engineering y structured output para corrección en español

Las lecciones más valiosas provienen de experimentos reales con corrección de texto periodístico en español (Noches de Media con La Silla Vacía). **Temperatura 0 es esencial** para correcciones reproducibles. Los modelos GPT a veces "indican haber corregido una frase, pero al revisar la frase 'corregida' es exactamente igual a la original" — la validación post-proceso es crítica. Las citas directas deben protegerse explícitamente en el prompt. Los modelos a veces aplican **reglas de puntuación del inglés al español** (por ejemplo, colocando puntuación dentro de comillas en lugar de después, según norma RAE). El prompt debe declarar explícitamente: "Sigue las normas de puntuación del español según la RAE."

La estructura óptima del prompt separa el system prompt estático (cacheable) del user prompt dinámico. El system prompt contiene: definición de rol y persona, reglas completas de estilo, reglas gramaticales específicas del español, instrucciones de formato de salida, ejemplos few-shot de correcciones correctas e incorrectas, y restricciones y casos límite. El user prompt contiene solo: tipo de texto, público objetivo, tono deseado, variante del español, contexto anterior/posterior, y el párrafo a corregir. Esta separación maximiza los cache hits porque el system prompt permanece idéntico en las **250+ llamadas** que requiere un libro típico.

Para obtener correcciones parseables, el schema JSON recomendado incluye: `original_text` (fragmento exacto), `corrected_text` (propuesta), `category` (coherencia, cohesión, léxico, registro, claridad, redundancia, estructura, puntuación), `severity` (crítico, importante, sugerencia), y `explanation` (justificación en español). OpenAI Structured Outputs garantiza **100% de cumplimiento de schema** mediante constrained decoding usando Pydantic models directamente. La librería **Instructor** (python.useinstructor.com) permite usar el mismo schema Pydantic con OpenAI y Anthropic indistintamente, facilitando el cambio entre proveedores.

Un patrón especialmente efectivo para prevenir sobre-correcciones usa **ejemplos negativos** en el prompt: mostrar qué NO cambiar es tan importante como mostrar qué cambiar. Por ejemplo: "Original: 'A pesar de todo, el proyecto salió adelante.' — Corrección incorrecta: 'No obstante, el proyecto salió adelante.' — Corrección correcta: No se requiere corrección. La frase es válida. No sustituir expresiones válidas por sinónimos si no hay error."

---

## La combinación de caching y batch reduce costos hasta un 95%

Los dos mecanismos de reducción de costos más potentes son el prompt caching y el Batch API, y **se acumulan multiplicativamente**. Anthropic ofrece cache reads al **10% del precio base** (90% de descuento) con un TTL de 5 minutos que se refresca con cada cache hit; el costo de escritura inicial es 1.25× el precio base. OpenAI ofrece caching automático al **50% del precio base** para GPT-4o/4o-mini sin cambios de código, requiriendo un prefijo mínimo de 1,024 tokens. Ambos proveedores ofrecen Batch API con **50% de descuento** adicional (entrega en ≤24 horas). En Anthropic, los descuentos se acumulan: Sonnet 4.5 pasa de $3.00/MTok a $1.50/MTok (batch) a **$0.15/MTok** (batch + cache read), un ahorro del 95%.

| Modelo | Input estándar | Con cache | Con batch | Batch + cache |
|--------|---------------|-----------|-----------|---------------|
| GPT-4o-mini | $0.15/MTok | $0.075 | $0.075 | $0.0375 |
| GPT-4o | $2.50/MTok | $1.25 | $1.25 | $0.625 |
| Claude Haiku 4.5 | $1.00/MTok | $0.10 | $0.50 | $0.05 |
| Claude Sonnet 4.5 | $3.00/MTok | $0.30 | $1.50 | $0.15 |

Para un libro de 100 páginas (~250 párrafos, ~25,000 palabras), el costo total estimado con batch + caching es: **$0.02 con GPT-4o-mini**, $0.36 con GPT-4o, $0.045 con Claude Haiku 4.5, y **$0.08 con Claude Sonnet 4.5**. Para la arquitectura híbrida recomendada (GPT-4o-mini en Pasada 2 + Claude Sonnet en Pasada 3), el costo por libro es aproximadamente **$0.03-$0.10**. Para maximizar cache hits, se debe procesar todos los párrafos de un documento en una sola sesión rápida (dentro de la ventana TTL de 5 minutos) y mantener el system prompt 100% estático — sin timestamps, contadores ni metadatos dinámicos al inicio.

---

## Arquitectura de producción y evaluación de calidad

### Procesamiento, errores y alucinaciones

La arquitectura de producción debe usar procesamiento basado en colas (Redis/RabbitMQ) con reintentos exponenciales con jitter. Los errores 429 (rate limit) requieren respetar el header `Retry-After`; los 500/502/503 se reintentan automáticamente; los 400/401/422 no se reintentan. La librería Python `tenacity` es el estándar para implementar esta lógica. Para throughput, el procesamiento paralelo de párrafos es posible (las APIs permiten 50-500+ requests concurrentes según tier), pero debe respetarse el orden del documento al reagregar resultados.

Las **alucinaciones en contexto de edición** son particularmente insidiosas: el LLM puede alterar el significado, insertar información no presente en el original, eliminar contenido importante, sobre-corregir texto correcto, o destruir la voz del autor. Las estrategias de mitigación incluyen: umbrales de similitud semántica (requerir BERTScore F1 > 0.85 entre original y corrección), verificación NLI para detectar contradicciones, análisis de ratio de distancia de edición (flag si las correcciones cambian >X% del contenido), temperatura baja (0.0-0.3), y presentar siempre correcciones como sugerencias con control de cambios, nunca como ediciones auto-aplicadas.

### Generación de track changes en DOCX

Un hallazgo crítico: **python-docx NO soporta nativamente track changes** (issue #340 abierto desde 2016). La mejor solución open-source es **Python-Redlines** (github.com/JSv4/Python-Redlines), que envuelve el WmlComparer de Open-XML-PowerTools: compara dos archivos .docx y genera un documento con marcado de tracked changes real de Open XML. Alternativamente, **diff-match-patch** de Google (originalmente construido para Google Docs) genera diffs a nivel de carácter con agrupación semántica, ideal para visualizar correcciones.

### Evaluación automatizada de calidad

**SARI es la única métrica diseñada específicamente para edición de texto** — considera texto fuente, referencia y salida, y mide operaciones de edición (mantener, añadir, eliminar). BERTScore captura equivalencia semántica más allá de la coincidencia superficial. Los métricas n-gram clásicas (BLEU, ROUGE) "no capturan si el texto mejoró — solo miden similitud con una referencia." La combinación recomendada es: SARI/GLEU para calidad de edición referenciada, BERTScore para similitud semántica, y LLM-as-judge para evaluación de seguimiento de instrucciones. El paper CoEdIT de Grammarly (EMNLP 2023) demostró que un modelo fine-tuned de **770M parámetros** superó a GPT-3-Edit (175B) en benchmarks de edición, con evaluadores humanos prefiriéndolo **64% vs 10%** — evidencia de que modelos especializados pequeños pueden ser superiores a modelos generales grandes para tareas de edición.

---

## Conclusión: el pipeline profesional es multi-pasada, configurable y económico

El rediseño de STYLIA debe abandonar la tentación de la pasada única omnisciente. La corrección profesional humana es inherentemente secuencial y categorizada — y el pipeline técnico debe reflejar eso. La arquitectura de tres pasadas (LanguageTool → modelo barato para léxico → modelo potente para estilo) replica el proceso editorial profesional, permite auditoría por categoría, habilita configuración granular por perfil de texto, y cuesta menos de $0.10 por libro de 100 páginas.

Los perfiles configurables con las siete dimensiones identificadas (vocabulario, longitud de oraciones, complejidad sintáctica, registro, tolerancia a repeticiones, tono, convenciones de género), anclados a métricas INFLESZ verificables, transforman STYLIA de una herramienta genérica a un sistema profesional adaptable. El JSON schema de correcciones categorizadas con severidad y explicación permite construir una UX de revisión granular comparable a Grammarly o ProWritingAid. Y la estrategia de prompt estático cacheable + batch processing reduce los costos a niveles donde procesar miles de documentos diarios es económicamente viable.

Las referencias editoriales en español que deben informar los prompts del sistema son: la *Ortografía* de la RAE (2010) para normas ortotipográficas, la *Nueva gramática* (RAE) para corrección de estilo, el *Manual de estilo de la lengua española* de Martínez de Sousa para estilo editorial, y Fundéu para consultas de uso actual. Estas son las mismas fuentes que usan los correctores profesionales humanos, y codificar sus criterios en los system prompts es lo que separa una corrección amateur de una profesional.