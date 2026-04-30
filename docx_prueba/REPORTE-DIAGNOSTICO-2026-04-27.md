# REPORTE DIAGNÓSTICO — STYLIA Pipeline v3
**Documento de prueba:** `stylia_test_documento_con_errores.docx`  
**Perfil aplicado:** No ficción general (`no_ficcion_general` — intervención moderada)  
**Fecha de prueba:** 2026-04-27  
**ID procesamiento:** `b621f45b-1019-459a-8bea-199e3f7f9b80`

---

## RESUMEN EJECUTIVO

| Indicador | Valor |
|-----------|-------|
| Total errores conocidos | 52 |
| Corregidos correctamente | **29** (56%) |
| Corregidos parcialmente | **11** (21%) |
| No corregidos (missed) | **9** (17%) |
| Regresiones introducidas | **3 bugs** (6%) |
| Párrafos procesados | 79 analizados, 41 con cambios |
| Llamadas LLM (GPT) | 50 llamadas, 30 párrafos con cambios GPT |
| Costo LLM | $0.01153 USD (57,527 tokens) |
| Rutas: skip / cheap / editorial | 29 / 43 / 7 |
| Gates: OK / revisión / descartados | 34 / 5 / 0 |

### Incidente crítico detectado durante la prueba
**El LLM falló en la primera ejecución** por incompatibilidad del parámetro `max_tokens` con `gpt-5.4-mini` (requiere `max_completion_tokens`). El primer procesamiento fue LT-only. Se corrigió el bug y se reprocesó. El reporte refleja los resultados del **segundo procesamiento (con LLM activo)**.

---

## ANÁLISIS DETALLADO POR CATEGORÍA

### A. ORTOGRÁFICOS Y TIPOGRÁFICOS (10 errores)

| ID | Ubicación | Error | Corrección esperada | Resultado STYLIA | Estado |
|----|-----------|-------|---------------------|-----------------|--------|
| A-01 | Título H1 | "Artifial" | "Artificial" | **No corregido** — título clasificado como `titulo` → ruta `skip`, LLM excluido | ❌ MISSED |
| A-02 | Subtítulo H2 | "analisis" | "Análisis" + mayúscula | "Análisis comparativo..." | ✅ OK |
| A-03 | Resumen p.1 | "artifial" | "artificial" | "artificial" (LT+GPT) | ✅ OK |
| A-04 | Resumen p.1 | "editoriáles" | "editoriales" | "editoriales" (LT+GPT) | ✅ OK |
| A-05 | Resumen p.1 | "latinoamerica" (adj.) | "latinoamericanas" | "Latinoamérica" (nombre propio, no adj.) | ⚠️ PARCIAL |
| A-06 | Obj. 3 (lista) | "dia" sin tilde | "día" | "en la actualidad" (mejor que solo tilde) | ✅ MEJOR |
| A-07 | Formato mixto | "especificamente" | "específicamente" | "específicamente" (LT) | ✅ OK |
| A-08 | Hipervínculo | "publicasiones" | "publicaciones" | "publicaciones" (LT, ×2) | ✅ OK |
| A-09 | Pág. salto | "analisis" | "análisis" | "análisis" (LT+GPT) | ✅ OK |
| A-10 | Discusión/Marco T. | "artifial" | "artificial" | "artificial" (LT, ×2) | ✅ OK |

**Subtotal A: 8/10 corregidos, 1 parcial, 1 missed**

---

### B. GRAMATICALES (6 errores)

| ID | Ubicación | Error | Corrección esperada | Resultado STYLIA | Estado |
|----|-----------|-------|---------------------|-----------------|--------|
| B-01 | Introducción p.1 | "Hubieron muchos cambios" | "Hubo muchos cambios" | "Hubo muchos cambios" (LT) | ✅ OK |
| B-02 | Introducción p.3 | "Pensamos de que" | "Pensamos que" (dequeísmo) | "Pensamos que" (LT+GPT) | ✅ OK |
| B-03 | Objetivos ítem 2 | "los resultado obtenido" | "los resultados obtenidos" | "el resultado obtenido" en objetivos; "los resultados obtenidos" en H-01 | ⚠️ PARCIAL |
| B-04 | Objetivos ítem 4 | "el herramienta más efectivo" | "la herramienta más efectiva" | "la herramienta más efectiva" (LT+GPT) | ✅ OK |
| B-05 | Tabla 2, LT fortalezas | "La dijeron que" (laísmo) | "Le dijeron que" | "Le dijeron que" (LT+GPT) | ✅ OK |
| B-06 | Tabla 2, LT limitaciones | "Se enteró que" (queísmo) | "Se enteró de que" | "Se enteró de que" (LT+GPT) | ✅ OK |

**Subtotal B: 5/6 corregidos, 1 parcial**

---

### C. ESTILO — REDUNDANCIAS Y MULETILLAS (7 errores)

| ID | Ubicación | Error | Corrección esperada | Resultado STYLIA | Estado |
|----|-----------|-------|---------------------|-----------------|--------|
| C-01 | Resumen p.1 | "es importante mencionar que es necesario tener en cuenta que" | Eliminar doble muletilla | **No corregido** — el LLM procesó el párrafo pero preservó la muletilla | ❌ MISSED |
| C-02 | Objetivos ítem 3 | "en el día de hoy" | "hoy" | "en la actualidad" (GPT, mejor opción) | ✅ MEJOR |
| C-03 | Objetivos ítem 5 | "llevar a cabo" | "realizar" | "llevar a cabo" → "introduciendo" (H-01 ctx) / no cambiado en Obj. | ⚠️ PARCIAL |
| C-04 | Objetivos ítem 5 | "dado al hecho de que" | "dado que" | "dado que" (LT+GPT) | ✅ OK |
| C-05 | Marco T. / H-01 | "En este sentido, cabe destacar el hecho de que...demuestran claramente que" | Eliminar muletillas | "el hecho de que" eliminado; "En este sentido" y "demuestran claramente que" permanecen | ⚠️ PARCIAL |
| C-06 | Marco T. / H-01 | "cosa" comodín ×3 | Sustituir por sustantivos precisos | "es una cosa" → eliminado; "en las cosa" → "en las cuestiones"; "estas cosas" parcial | ⚠️ PARCIAL |
| C-07 | Tabla 2, STYLIA | "a nivel de" ×3 | Eliminar/reemplazar | **No corregido** — la celda de la tabla con texto STYLIA no fue simplificada | ❌ MISSED |

**Subtotal C: 2/7 corregidos, 3 parciales, 2 missed**

---

### D. PUNTUACIÓN (7 errores)

| ID | Ubicación | Error | Corrección esperada | Resultado STYLIA | Estado |
|----|-----------|-------|---------------------|-----------------|--------|
| D-01 | Introducción p.2 | Coma entre sujeto y predicado "digital, ha sido" | Eliminar coma | Eliminada (LT) | ✅ OK |
| D-02 | Diálogo p.3 | "García Moreno «La edición»" | "García Moreno: «La edición»" | "García Moreno: «La edición»" (GPT editorial) | ✅ OK |
| D-03 | Discusión p.3 | "Qué impacto..." sin apertura ¿ | "¿Qué impacto..." | **No corregido** — el LLM tampoco añadió ¿ | ❌ MISSED |
| D-04 | Discusión p.3 | "...." (4 puntos) | "..." (3 puntos) | "sorprendentes..." (GPT) | ✅ OK |
| D-05 | Discusión p.3 | "tres factores; el primero" | "tres factores: el primero" | "tres factores: el primero" (GPT editorial) | ✅ OK |
| D-06 | Conclusiones p.1 | "Villanueva investigadora principal presentó" | "Villanueva, investigadora principal, presentó" | **No corregido** — comas de aposición no añadidas | ❌ MISSED |
| D-07 | Conclusiones p.2 | "resultados fueron: positivos" | "resultados fueron positivos" | "resultados fueron positivos" (GPT) | ✅ OK |

**Subtotal D: 5/7 corregidos, 2 missed**

---

### E. ERRORES EN CELDAS DE TABLA (5 errores)

| ID | Ubicación | Error | Corrección esperada | Resultado STYLIA | Estado |
|----|-----------|-------|---------------------|-----------------|--------|
| E-01 | Tabla 1, col.1 | "Region" sin tilde | "Región" | "Región" (LT) | ✅ OK |
| E-02 | Tabla 1, México col.5 | "más o menos 60%" (coloquial) | "~60%" o "60% aprox." | "Más o menos 60%" — solo capitalizó, no simplificó | ❌ PARCIAL |
| E-03 | Tabla 1, Colombia col.3 | "resultados positivo" | "resultados positivos" | "Resultados positivos" (LT) | ✅ OK |
| E-04 | Tabla 1, Chile col.2 | Texto ~80 palabras verboso | "N/A" | Texto acortado ~30% pero no reducido a "N/A" | ⚠️ PARCIAL |
| E-05 | Tabla 2, LT fortalezas | "La dijeron que" (laísmo) | "Le dijeron que" | "Le dijeron que" (ver B-05) | ✅ OK |

**Subtotal E: 3/5 corregidos, 2 parciales**

---

### F. ERRORES EN CAPTIONS (4 errores)

| ID | Ubicación | Error | Corrección esperada | Resultado STYLIA | Estado |
|----|-----------|-------|---------------------|-----------------|--------|
| F-01 | Caption Fig.1 | "evolución" sin mayúscula | "Evolución" | "Evolución" (LT+GPT) | ✅ OK |
| F-02 | Caption Fig.1 | "latinoamerica" (adj.) | "latinoamericanas" | "de Latinoamérica" (nombre propio, no adj.) | ⚠️ PARCIAL |
| F-03 | Caption Fig.2 | "fig 2 Mapa..." | "Fig. 2. Mapa..." | "Fig. 2. Mapa..." (GPT editorial) | ✅ OK |
| F-04 | Caption Fig.2 | Sin mayúscula inicial | Mayúscula en primera letra | Corregida como parte de F-03 | ✅ OK |

**Subtotal F: 3/4 corregidos, 1 parcial**

---

### G. REGISTRO Y TONO (5 errores)

| ID | Ubicación | Error | Corrección esperada | Resultado STYLIA | Estado |
|----|-----------|-------|---------------------|-----------------|--------|
| G-01 | Metodología cierre | "O sea, básicamente...un montón" | Reformular en registro académico | "La IA está cambiando todo de forma considerable..." (mejor, no perfecto; "¿no?" persiste) — `manual_review` | ⚠️ PARCIAL |
| G-02 | Metodología / Marco T. | "la cosa" comodín | Sustantivo preciso | Parcialmente corregido en H-01 y Marco T. | ⚠️ PARCIAL |
| G-03 | Discusión p.2 | "Los investigadores...Analizamos" (cambio de persona) | Unificar tercera persona | **No corregido** — inconsistencia de persona preservada | ❌ MISSED |
| G-04 | Discusión p.2 | "Si quieres revisar" (tuteo) | "Si desea revisar" (formal) | "Si desea revisar" (GPT) | ✅ OK |
| G-05 | Objetivos ítem 3 | "en el día de hoy" | (ver C-02) | (ver C-02) | ✅ OK |

**Subtotal G: 2/5 corregidos, 2 parciales, 1 missed**

---

### H. PÁRRAFO ESTRESOR CON 7 ERRORES SIMULTÁNEOS (H-01 — Discusión p.1)

Este párrafo concentra errores de categorías A, B, C y G acumulados. Se procesó con `cheap` y resultó en `manual_review`.

| Error en H-01 | Resultado |
|---------------|-----------|
| "En este sentido es importante mencionar el hecho de que" | ⚠️ PARCIAL — "el hecho de que" eliminado, "En este sentido...es importante mencionar que" permanece |
| "los resultado obtenido" | ✅ CORRECTED — "los resultados obtenidos" |
| "a nivel de las editoriales latinoamerica" | ✅ CORRECTED — "en las editoriales de Latinoamérica" |
| "demuestran claramente que" | ❌ MISSED — muletilla de énfasis preservada |
| "la inteligencia artifial," | ✅ CORRECTED — "la inteligencia artificial" |
| "en las cosa relacionadas" | ✅ CORRECTED — "en las cuestiones relacionadas" |
| "llevando a cabo" | ✅ CORRECTED — "introduciendo" |
| "lo cual es una cosa que nadie puede negar en el dia de hoy" | ✅ CORRECTED — "algo que hoy nadie puede negar" |

**H-01 resultado: 6/8 sub-errores corregidos. Marcado para revisión humana.**

---

## BUGS Y REGRESIONES CRÍTICAS

### BUG-01: STYLIA → ITALIA (CRÍTICO — INACEPTABLE)

LanguageTool interpreta "STYLIA" como typo de "ITALIA" y lo corrige automáticamente.

| Patch | Original | Corrección aplicada | Review status |
|-------|----------|---------------------|---------------|
| v65 | `STYLIA — Corrector Editorial` | `ITALIA — Corrector Editorial` | `auto_accepted` ← **peligroso** |
| v58 | `STYLIA v1.0` | `ITALIA vv.` | `manual_review` (gate rewrite_ratio lo atrapó) |

**Causa raíz:** El perfil `no_ficcion_general` no incluye "STYLIA" en `protected_terms`. La lógica de `engine_router.py` protege términos del perfil, pero si el perfil no los lista, LT los modifica y el LLM no los revierte.

**Fix requerido:**
1. Agregar "STYLIA" a los `protected_terms` del perfil `no_ficcion_general` (o como término global de la aplicación), O
2. El gate `gate_protected_terms` debería bloquearlo, pero como "STYLIA" no está en el perfil, no lo detecta.
3. La corrección v65 fue `auto_accepted` — el gate de rewrite_ratio no lo atrapó porque solo cambió 1 palabra.

---

### BUG-02: tokenización → colonización (CRÍTICO)

En el Marco Teórico, el LLM cambió "tokenización semántica" por "colonización semántica".

| Patch | Original | Corrección aplicada |
|-------|----------|---------------------|
| v24 | `La tokenización semántica es otra cosa importante` | `La colonización semántica es otra cosa importante` |

**Causa raíz:** "tokenización" es un término técnico específico de NLP que no está en el glosario español estándar. El LLM, intentando "corregir" o simplificar, lo sustituyó por una palabra más común. Este es exactamente el tipo de error que el Plan v3 intentaba prevenir con `term_registry` y regiones protegidas — pero el término no fue añadido al glosario del documento ni al perfil.

**Fix requerido:** La Etapa C (análisis editorial) debería detectar términos técnicos como "tokenización", "NLP", "machine learning editorial" y añadirlos automáticamente al `term_registry` con `is_protected=True`.

---

### BUG-03: max_tokens → max_completion_tokens (BLOQUEANTE — YA CORREGIDO)

El modelo `gpt-5.4-mini` requiere `max_completion_tokens` en lugar del parámetro legacy `max_tokens`. Esto causó que **todo el primer procesamiento fallara silenciosamente** con `0 llamadas GPT` — solo LanguageTool se aplicó.

**Fix aplicado:** `openai_client.py` líneas 129 y 186: `max_tokens` → `max_completion_tokens`.

---

## ANÁLISIS DE RUTAS Y COMPORTAMIENTO DEL ROUTER

| Ruta | Párrafos | Comportamiento observado |
|------|----------|--------------------------|
| `skip` | 29 | Títulos, captions cortas, párrafos de 1-2 palabras. Algunos títulos con errores (A-01) no fueron corregidos. |
| `cheap` | 43 | La mayoría de párrafos de cuerpo, objetivos, tabla. LLM con prompt simple. |
| `editorial` | 7 | Párrafos largos con contexto complejo: Resumen, Marco Teórico, Discusión p.3, Caption Fig.2. |

**Observación:** El router `skip` excluye LLM para títulos. El H1 "La Inteligencia Artifial..." con error A-01 fue skipeado. Para párrafos cortos con solo ortografía, el skip es correcto; pero para títulos con errores tipográficos, debería aplicarse al menos LT.

**Observación:** 5 patches marcados `manual_review`. Todos son por `rewrite_ratio` elevado o `language_preserved` sospechoso. Esto es correcto y esperado — el revisor humano puede evaluarlos.

---

## RESUMEN DE GATES DE CALIDAD

| Gate | OK | Fallo | Comportamiento |
|------|----|-------|----------------|
| `not_empty` | 41 | 0 | Sin problemas |
| `expansion_ratio` | 41 | 0 | Sin expansiones excesivas |
| `rewrite_ratio` | 36 | 5 | 5 párrafos con reescritura >30% → manual_review (correcto) |
| `protected_terms` | 41 | 0 | **No detectó STYLIA→ITALIA** porque STYLIA no estaba en el perfil |
| `language_preserved` | 38 | 3 | 3 falsos positivos menores (párrafos muy cortos como "Región") |

**Nota crítica:** El gate `protected_terms` pasó el cambio STYLIA→ITALIA porque el perfil no declaraba "STYLIA" como término protegido. El diseño del gate es correcto, pero necesita un mecanismo de términos globales a nivel de aplicación.

---

## ERRORES QUE EL LLM NO CORRIGIÓ (ANÁLISIS)

Los errores sistemáticamente perdidos corresponden a:

1. **Falta ¿ en preguntas (D-03):** LT no detecta apertura de interrogación faltante en español, y el LLM en ruta `editorial` tampoco la añadió. La regla debería ser explícita en el system prompt.

2. **Comas en aposición (D-06):** "La doctora Villanueva investigadora principal del proyecto" — el LLM con ruta `cheap` no añadió las comas. El prompt de ruta `cheap` es más conservador, lo que explica la omisión.

3. **Cambio de persona narrativa (G-03):** "Los investigadores analizaron...Analizamos los datos" — cambiar la persona requiere análisis de cohesión inter-oración. El LLM procesó el párrafo pero prefirió no tocar la inconsistencia (probablemente por conservadurismo).

4. **Títulos H1/H2 con errores (A-01):** La clasificación `titulo` lleva a ruta `skip` en el router de complejidad. Esto es excesivamente conservador para títulos con errores tipográficos evidentes.

5. **Doble muletilla en Resumen (C-01):** El LLM procesó el párrafo en ruta `editorial` pero no eliminó la muletilla. Posiblemente porque es una corrección de alto impacto (eliminaría dos frases completas) y el perfil `moderado` la frenó.

---

## PROBLEMAS ESTRUCTURALES DETECTADOS

### 1. Párrafos duplicados (versiones múltiples)
Se observan hasta 6 versiones del mismo párrafo (v18-v23 para Metodología coloquial, v37-v42 para Discusión H-01). Esto genera 65 patches totales para 41 párrafos únicos. Las versiones múltiples surgen de múltiples pases del pipeline. Deben consolidarse en el frontend para no confundir al revisor.

### 2. Correcciones de tabla capitalizan incorrectamente
v55: "resultados positivo" → "Resultados positivos" — al ser contenido de celda de tabla, la capitalización automática es incorrecta (depende del contexto). El router debería diferenciar `celda_encabezado` de `celda_dato`.

### 3. El perfil `no_ficcion_general` no es adecuado para documentos técnicos
El documento usa terminología de NLP ("tokenización", "machine learning editorial"). El perfil aplicado no conoce estos términos. Para pruebas futuras usar perfil "Ensayo" o "Manual técnico" que incluyen mayor respeto por terminología técnica.

---

## MÉTRICAS FINALES

```
ERRORES CONOCIDOS:     52 (distribuidos en 8 categorías)
─────────────────────────────────────────────────────
CORREGIDOS (total):    29  (55.8%)
  • Correctamente:     25  (48.1%)
  • Mejorado/superior:  4  (7.7%) — respuesta más elegante que la esperada
PARCIALES:             11  (21.2%)
PERDIDOS (missed):      9  (17.3%)
REGRESIONES:            3  bugs nuevos introducidos (5.8%)
─────────────────────────────────────────────────────
TASA DE ÉXITO NETA:   ~50% (corregidos sin introducir bugs)
```

---

## PLAN DE ACCIÓN PRIORITARIO

### PRIORIDAD CRÍTICA (bloquean calidad)

| # | Acción | Impacto | Archivos |
|---|--------|---------|---------|
| P1 | Añadir términos globales protegidos a nivel de aplicación (STYLIA, nombres de producto) que no dependan del perfil | STYLIA→ITALIA | `engine_router.py`, `app/data/profiles.py` |
| P2 | La Etapa C (análisis) debe detectar y proteger automáticamente términos técnicos del dominio presentes en el documento | tokenización→colonización | `analysis.py` |
| P3 | El router no debe aplicar `skip` a títulos con errores tipográficos detectados por LT — si LT encontró cambios, debe procesarse aunque sea solo LT | A-01 (H1) | `complexity_router.py` |

### PRIORIDAD ALTA (mejoran cobertura)

| # | Acción | Impacto |
|---|--------|---------|
| P4 | Añadir instrucción explícita al system prompt para detectar y añadir ¿ faltante en oraciones interrogativas | D-03 |
| P5 | El router `cheap` debería incluir instrucciones de puntuación (comas en aposición) | D-06 |
| P6 | Consolidar versiones múltiples del mismo párrafo en la vista de correcciones del frontend | UX |
| P7 | Diferenciar `celda_encabezado` de `celda_dato` en el router — las celdas de dato no deben capitalizar automáticamente | E-03 |

### PRIORIDAD MEDIA (refinamiento)

| # | Acción | Impacto |
|---|--------|---------|
| P8 | Añadir regla específica para detectar inconsistencias de persona narrativa (G-03) | G-03 |
| P9 | "latinoamerica" como adjetivo debería corregirse a "latinoamericana/o" no a "Latinoamérica" nombre propio | A-05, F-02 |
| P10 | Mejorar instrucción del perfil `moderado` para permitir eliminar muletillas dobles (C-01) | C-01 |

---

## COMPARACIÓN: PRIMER PROCESAMIENTO (solo LT) vs SEGUNDO (LT + LLM)

| Categoría | Solo LT | LT + LLM | Diferencia |
|-----------|---------|----------|------------|
| Ortografía (A) | 7/10 | 8/10 | +1 (A-06 elegante) |
| Gramática (B) | 4/6 | 5/6 | +1 (B-04 género completo) |
| Estilo C | 0/7 | 2/7 | +2 (C-02, C-04) |
| Puntuación D | 3/7 | 5/7 | +2 (D-02, D-05) |
| Tablas E | 3/5 | 3/5 | = |
| Captions F | 2/4 | 3/4 | +1 (F-03) |
| Registro G | 0/5 | 2/5 | +2 (G-01 parcial, G-04) |
| **TOTAL** | **19/52 (37%)** | **29/52 (56%)** | **+10 errores** |

El LLM añade valor real, especialmente en estilo, puntuación compleja y registro. Sin LLM, el sistema funciona solo como corrector ortográfico básico.

---

*Generado automáticamente por análisis post-procesamiento — STYLIA v0.2.0*
