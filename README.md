# STYLIA — Corrector de Estilo Editorial para Español

> Sistema de corrección editorial inteligente para documentos DOCX en español.  
> Combina LanguageTool (ortografía y gramática) con OpenAI GPT (estilo, claridad, coherencia) bajo perfiles editoriales parametrizados. Preserva formato y voz del autor.  
> Incluye extracción de estructura DOCX nativa, corrección grupal de listas y tablas, y prompts dinámicos por tipo de elemento.

**Versión**: 0.3.0 — Structural Awareness activo (B.5/D.5)

---

## Tabla de contenidos

1. [Qué es STYLIA y para qué sirve](#1-qué-es-stylia-y-para-qué-sirve)
2. [Inicio rápido](#2-inicio-rápido)
3. [Flujo completo de uso](#3-flujo-completo-de-uso)
4. [Pipeline de procesamiento (Etapas A–E + B.5/D.5)](#4-pipeline-de-procesamiento-etapas-ae--b5d5)
5. [Análisis estructural: listas, tablas y tipos de párrafo](#5-análisis-estructural-listas-tablas-y-tipos-de-párrafo)
6. [Motor de corrección: cómo funciona por dentro](#6-motor-de-corrección-cómo-funciona-por-dentro)
7. [Perfiles editoriales predefinidos (10 perfiles)](#7-perfiles-editoriales-predefinidos-10-perfiles)
8. [Perfiles personalizados y ficha ADN editorial](#8-perfiles-personalizados-y-ficha-adn-editorial)
9. [Reglas personalizadas: sustitución, entidades e idiolectos](#9-reglas-personalizadas-sustitución-entidades-e-idiolectos)
10. [Bloques del prompt: control granular](#10-bloques-del-prompt-control-granular)
11. [Las pestañas de la interfaz: qué hace cada una](#11-las-pestañas-de-la-interfaz-qué-hace-cada-una)
12. [Quality gates: validación automática de correcciones](#12-quality-gates-validación-automática-de-correcciones)
13. [Revisión humana (HITL)](#13-revisión-humana-hitl)
14. [Corrección macro por sección](#14-corrección-macro-por-sección)
15. [Costos y métricas LLM](#15-costos-y-métricas-llm)
16. [API REST completa](#16-api-rest-completa)
17. [Variables de entorno](#17-variables-de-entorno)
18. [Arquitectura y stack tecnológico](#18-arquitectura-y-stack-tecnológico)
19. [Estructura del repositorio](#19-estructura-del-repositorio)
20. [Comandos de desarrollo](#20-comandos-de-desarrollo)
21. [Limitaciones actuales y roadmap](#21-limitaciones-actuales-y-roadmap)

---

## 1. Qué es STYLIA y para qué sirve

STYLIA es un sistema de corrección editorial profesional diseñado específicamente para documentos en español. No es un corrector ortográfico genérico: es una herramienta editorial completa que entiende el contexto del texto, el género del documento, la audiencia, el registro lingüístico y la voz del autor.

### Qué hace

- **Corrige ortografía y gramática** con LanguageTool (motor especializado en español)
- **Mejora el estilo** usando OpenAI GPT con instrucciones parametrizadas por perfil editorial
- **Preserva el formato** del documento DOCX original (fuentes, estilos, tablas, encabezados)
- **Protege la voz del autor**: no reescribe arbitrariamente, respeta el nivel de intervención configurado
- **Analiza editorialmente** el documento antes de corregir: detecta secciones, construye glosario, clasifica tipos de párrafo
- **Valida automáticamente** cada corrección con quality gates antes de presentarla al revisor
- **Permite revisión humana** de cada corrección con aprobación, rechazo o edición manual
- **Rastrea costos** de cada llamada al LLM con desglose por párrafo, modelo y documento
- **Genera informes** descargables en DOCX y PDF corregidos

### Para quién es

- Editoriales que procesan manuscritos en lote
- Correctores y editores literarios que quieren asistencia automatizada sin perder control
- Departamentos de comunicación que producen documentos corporativos en español
- Agencias de traducción que necesitan revisión de estilo post-traducción
- Equipos académicos que publican artículos y libros en español

### Qué NO hace (aún)

- No procesa PDFs escaneados (OCR está en roadmap)
- No procesa PDFs nativos directamente (se convierte desde DOCX)
- No tiene autenticación de usuarios (MVP — multi-usuario en roadmap)
- No soporta inglés ni otros idiomas (solo español por ahora)

---

## 2. Inicio rápido

### Requisitos

- Docker Desktop (con al menos 8 GB de RAM asignados)
- Git
- API key de OpenAI (opcional: sin ella funciona en modo simulación)

### Arranque completo

```bash
git clone https://github.com/tu-org/stylia.git
cd stylia
cp .env.example .env
# Editar .env y poner tu OPENAI_API_KEY
docker compose up -d --build
```

El sistema tarda ~2 minutos en inicializarse completamente (LanguageTool necesita tiempo de calentamiento).

### URLs disponibles

| Servicio | URL |
|----------|-----|
| Aplicación web | http://localhost:3000 |
| API REST (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| MinIO (almacenamiento) | http://localhost:9001 (minioadmin / minioadmin) |
| pgAdmin (base de datos) | http://localhost:5050 (postgresql / admin) |

---

## 3. Flujo completo de uso

### En la interfaz web

```
1. Acceder a http://localhost:3000
2. Arrastrar un archivo .docx al área de carga
3. Seleccionar un perfil editorial (o crear uno personalizado)
4. Pulsar "Procesar documento"
5. Esperar el progreso en tiempo real (barra por etapas A→B→C→D→E)
6. Revisar resultados en las pestañas:
   - Resumen: estadísticas y estado del documento
   - Análisis: secciones detectadas, glosario, tipos de párrafo
   - Correcciones: lista completa con diff, categoría, confianza
   - ADN Editorial: ficha editorial + reglas personalizadas
   - Flujo API: auditoría de cada llamada al LLM
   - Comparar: vista side-by-side original vs. corregido
7. Aprobar / rechazar / editar correcciones individuales
8. Pulsar "Finalizar" para generar el documento definitivo
9. Descargar DOCX y PDF corregidos
```

### Via API (flujo mínimo)

```bash
# 1. Subir documento
DOC_ID=$(curl -s -X POST http://localhost:8000/api/v1/upload \
  -F "file=@mi_novela.docx" | jq -r '.id')

# 2. Asignar perfil editorial
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/profile \
  -H "Content-Type: application/json" \
  -d '{"preset_name": "novela_contemporanea"}'

# 3. Lanzar procesamiento
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/process

# 4. Consultar estado
curl http://localhost:8000/api/v1/documents/$DOC_ID | jq '.status'

# 5. Cuando status=candidate_ready, finalizar
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/finalize

# 6. Descargar
curl -L http://localhost:8000/api/v1/documents/$DOC_ID/download/docx -o corregido.docx
curl -L http://localhost:8000/api/v1/documents/$DOC_ID/download/pdf  -o corregido.pdf
```

---

## 4. Pipeline de procesamiento (Etapas A–E + B.5/D.5)

El procesamiento de cada documento sigue 7 etapas secuenciales ejecutadas como tarea Celery. Las sub-etapas B.5 y D.5 son no bloqueantes: si fallan, el pipeline continúa sin ellas.

```
DOCX original
  │
  ▼
[A] INGESTA
    • Valida formato y tamaño (máx 500 MB, 1000 páginas)
    • Sube el DOCX original a MinIO
    • Convierte DOCX → PDF con LibreOffice headless
    • Detecta número de páginas
  │
  ▼
[B] EXTRACCIÓN
    • PyMuPDF analiza el PDF página por página
    • Extrae layout estructurado (bloques, bounding boxes, fuentes)
    • Genera texto plano por página
    • Genera previews PNG (150 DPI) para visualización
    • Sube todo a MinIO: layout JSON, texto TXT, previews PNG
  │
  ▼
[B.5] EXTRACCIÓN ESTRUCTURAL DOCX ← NUEVO
    • Abre el DOCX original con python-docx (no el PDF)
    • Detecta listas nativas (atributo numPr del XML) y manuales (regex de prefijo)
    • Detecta tablas (filtrado de tablas decorativas)
    • Crea un registro ElementGroup por cada lista y tabla encontrada
    • Enriquece cada Block de la DB con: list_id, table_id, style_name, docx_location,
      list_position, list_format_type, table_cell_role, element_group_id
    • Crea blocks "sintéticos" para celdas DOCX no capturadas por PyMuPDF
    → Resultado: mapa completo de la estructura real del documento
  │
  ▼
[C] ANÁLISIS EDITORIAL
    • Detecta secciones del documento (títulos, capítulos, partes)
    • Construye glosario de términos frecuentes con frecuencia de aparición
    • Clasifica cada párrafo en 14 tipos usando metadata de B.5 como señal primaria:
      titulo, subtitulo, narrativo, explicacion_tecnica, dialogo, cita, lista,
      celda_tabla, celda_tabla_header, celda_tabla_total, pie_figura, nota_pie,
      encabezado, pie_pagina
    • Escribe paragraph_type en la tabla blocks de la DB (match por docx_location)
    • Infiere perfil editorial (género, audiencia, registro, tono)
    • Construye ADN global: voz dominante, términos globales protegidos, fingerprint
  │
  ▼
[D] CORRECCIÓN INDIVIDUAL
    • Omite párrafos que pertenecen a un ElementGroup (serán procesados en D.5)
    • Por cada párrafo no grupal:
        FASE 0: Sustituciones de usuario (antes de LT)
        FASE 1: LanguageTool corrige ortografía y gramática
        FASE 2: Router decide ruta (SKIP / CHEAP / EDITORIAL)
        FASE 3: LLM Pasada 1 — prompt dinámico filtrado por tipo de párrafo
        FASE 4: LLM Pasada 2 — auditoría contextual (detecta destrucciones)
        FASE 5: Quality gates (5 checks + gates estructurales por tipo)
    • Ventana de contexto: últimos 15 párrafos corregidos (triplicado)
  │
  ▼
[D.5] CORRECCIÓN GRUPAL ← NUEVO
    • Por cada ElementGroup (lista o tabla):
        — Recolecta todos los ítems del grupo ordenados por posición
        — Una sola llamada LLM con todos los ítems en el prompt
        — Para listas: evalúa paralelismo, puntuación uniforme, capitalización
        — Para tablas: evalúa uniformidad de celdas, roles (header/data/total)
        — Respuesta JSON indexada: cada ítem devuelto por su posición
        — Genera patches con group_id, group_call_index, structural_role
    • El LLM ve el grupo completo: puede detectar incoherencias entre ítems
  │
  ▼
[E] RENDERIZADO (group-aware)
    • Aplica primero los patches grupales (en orden de group_call_index)
    • Luego aplica los patches individuales (salteando los ya modificados por grupos)
    • Para listas manuales: preserva el prefijo exacto del usuario (no normaliza "2)" a "2.")
    • Para listas nativas: elimina el prefijo (el DOCX lo gestiona automáticamente)
    • Genera DOCX corregido candidato y convierte a PDF
  │
  ▼
candidate_ready → [Revisión humana] → completed
```

### Estados del documento

| Estado | Significado |
|--------|-------------|
| `uploaded` | Documento subido, esperando que el usuario elija perfil y lance proceso |
| `converting` | Etapa A: convirtiendo DOCX a PDF |
| `extracting` | Etapa B: extrayendo layout y texto del PDF |
| `analyzing` | Etapa C: analizando editorialmente el documento |
| `correcting` | Etapa D: corrigiendo párrafo por párrafo |
| `candidate_rendering` | Etapa E: generando DOCX/PDF corregido candidato |
| `candidate_ready` | Candidato listo para revisión humana |
| `finalizing` | Generando documento final tras aprobación humana |
| `completed` | Completado, listo para descarga |
| `failed` | Error durante el procesamiento |

---

## 5. Análisis estructural: listas, tablas y tipos de párrafo

Esta es la capacidad diferencial de STYLIA v0.3.0. El sistema no trata todos los párrafos igual: entiende la estructura del documento y aplica reglas distintas según el tipo de elemento.

### Por qué importa la estructura

Un corrector genérico puede:
- Añadir punto final a un título (incorrecto)
- Cambiar "2)" a "2." en una lista numerada (cambia el formato sin necesidad)
- Modificar el total de una tabla (destruye los datos)
- Corregir ítems de una lista de forma inconsistente entre sí

STYLIA v0.3.0 evita estos problemas porque antes de corregir sabe exactamente qué tipo de elemento es cada párrafo.

### Tipos de párrafo detectados (14 tipos)

| Tipo | Descripción | Señal de detección |
|------|-------------|-------------------|
| `titulo` | Título principal (Heading 1) | Estilo DOCX o heurística de texto corto sin punto |
| `subtitulo` | Título secundario (Heading 2+) | Estilo DOCX Heading nivel 2+ |
| `narrativo` | Párrafo narrativo o expositivo | Texto largo, sin marcadores especiales |
| `explicacion_tecnica` | Párrafo técnico con terminología | Densidad de términos del glosario |
| `dialogo` | Fragmento de diálogo | Empieza con —, «, " + mayúscula |
| `cita` | Cita textual | Estilo Quote en DOCX o marcadores tipográficos |
| `lista` | Ítem de lista | `list_id` del Block (B.5) o prefijo numérico/viñeta |
| `celda_tabla` | Celda de datos de tabla | `table_id` del Block + role=data |
| `celda_tabla_header` | Celda de encabezado de tabla | Primera fila de la tabla |
| `celda_tabla_total` | Celda de totales | Última fila + contenido numérico |
| `pie_figura` | Pie de figura o imagen | Empieza con "Figura", "Fig.", "Imagen", "Gráfico" |
| `nota_pie` | Nota al pie | Numeración + texto corto |
| `encabezado` | Encabezado de página | Ubicación header: en DOCX |
| `pie_pagina` | Pie de página | Ubicación footer: en DOCX |

### Detección de listas

**Listas nativas** (el DOCX gestiona la numeración):
- El XML del párrafo tiene atributo `numPr` con un `numId`
- Todos los párrafos con el mismo `numId` forman un grupo
- El DOCX añade la viñeta o número automáticamente → STYLIA no debe tocarlos

**Listas manuales** (el usuario escribió el prefijo a mano):
- El texto empieza con: `1.`, `2)`, `•`, `-`, `a)`, `i.`, etc.
- El cuerpo después del prefijo tiene al menos 4 caracteres
- Se excluyen títulos numerados ("1. Introducción" es un título, no un ítem)
- Los prefijos se preservan exactamente: si el usuario usó `2)`, STYLIA no lo cambia a `2.`

**Anti-falsos-positivos**:
- Párrafos con estilo Heading numerados no se detectan como lista
- Textos cortos (< 60 chars) sin puntuación final con prefijo = probablemente título
- Secuencias donde todos los "ítems" tienen estilo Heading → descartadas

### Detección de tablas

- Se analiza cada tabla del DOCX
- **Tablas decorativas descartadas**: 1×1, <2 celdas con texto real, tablas Nx1 con ≤3 filas
- Se asigna rol a cada celda: `header` (primera fila), `total` (última fila numérica), `data`
- Las celdas `total` nunca se modifican (protección de datos)

### Corrección en conjunto (ElementGroup)

Una vez detectados los grupos, STYLIA envía el grupo completo en una sola llamada al LLM:

**Para listas** — El LLM recibe todos los ítems y puede:
- Verificar paralelismo (todos empiezan con verbo infinitivo, o todos con sustantivo)
- Unificar puntuación al cierre (todos con punto, o todos sin él)
- Detectar consistencia de capitalización (todos con mayúscula inicial, o todos en minúscula)
- Corregir cada ítem individualmente mientras mantiene coherencia entre ellos

**Para tablas** — El LLM recibe todas las celdas con su rol y puede:
- Uniformizar capitalización por columna (todos los encabezados en mayúscula)
- Corregir contenido de celdas data sin tocar las de total
- Verificar que los textos de celdas hermanas sean gramaticalmente paralelos

### Árbol estructural (UI)

La pestaña "Análisis" muestra el árbol de estructura del documento:

```
Documento
├── Sección 1: Introducción
│   └── 📋 Lista manual — 4 ítems — ✓ completada
├── Sección 2: Marco teórico
│   ├── 📊 Tabla 4×3 — 10 celdas — ✓ completada
│   └── 📋 Lista nativa (decimal) — 6 ítems — ⚠ parcial
└── Sección 3: Conclusiones
    └── 📊 Tabla 2×5 — 8 celdas — ✓ completada
```

Cada nodo muestra: tipo, dimensiones, número de ítems, estado de corrección.

### En la lista de correcciones

Las correcciones grupales aparecen agrupadas con una `GroupCard` colapsable:

```
▼ [LISTA — 4 ítems — manual]
  ├── [1] "1. Informe final"  →  "1. Informe final."  [puntuacion: sugerencia]
  ├── [2] "2) Base de datos"  →  "2) Base de datos."  [puntuacion: sugerencia]
  ├── [3] "3. Acta de cierre" →  "3. Acta de cierre." [puntuacion: sugerencia]
  └── [4] "Cuatro. Resumen"   →  "4. Resumen final."  [estructura: importante]
```

---

## 6. Motor de corrección: cómo funciona por dentro

### Ruta activa: DOCX-first (Ruta 1)

La corrección opera directamente sobre el DOCX, no sobre el PDF extraído. Esto evita fragmentación de párrafos (los PDFs rompen párrafos que cruzan páginas) y preserva capitalización exacta.

### Fase 0 — Sustituciones de usuario

Antes de cualquier corrección automática, el sistema aplica las **reglas de sustitución personalizadas** del perfil:
- **Reglas de sustitución**: `"buscar" → "reemplazar"` (texto exacto o regex)
- **Normalizaciones de entidades**: unifican variantes de un nombre a su forma canónica (ej. `STYLIA`, `stylia`, `Stylia` → `STYLIA`)

Estas sustituciones se registran en el patch con `correction_phase="substitution"` y el LLM recibe una instrucción explícita de **no revertirlas**.

### Fase 1 — LanguageTool

- Envía el texto (post-sustituciones) al servidor LanguageTool en español
- Aplica correcciones de atrás hacia adelante para no desplazar posiciones
- Respeta las regiones protegidas (términos del perfil + términos globales del ADN)
- Las correcciones LT se registran con `correction_phase="lt"`

### Fase 2 — Router de complejidad

Cada párrafo es evaluado por el router para decidir qué nivel de procesamiento LLM necesita:

| Ruta | Cuándo se aplica | Modelo usado |
|------|-----------------|--------------|
| `SKIP` | Párrafo muy corto sin errores, título, pie de página, cita textual | Sin LLM |
| `CHEAP` | Párrafo simple, intervención mínima configurada, tabla, lista | `gpt-4o-mini` (barato) |
| `EDITORIAL` | Párrafo narrativo largo, diálogo, transición de sección, intervención agresiva | Modelo editorial configurable |

### Fase 3 — LLM Pasada 1 (corrección mecánica de estilo)

El prompt enviado al LLM tiene estructura en bloques:

```
[BLOQUE 0] CONTEXTO GLOBAL DEL DOCUMENTO
  • Tema principal del documento
  • Voz dominante del autor
  • Registro base
  • Términos técnicos protegidos globalmente (ej: STYLIA, tokenización)
  • Estilo dominante (longitud de oraciones, ratio voz pasiva)

[BLOQUE 1] PERFIL EDITORIAL
  • Registro: formal / informal / académico / literario...
  • Nivel de intervención: mínima / sutil / moderada / agresiva
  • Audiencia: tipo + edad + expertise
  • Tono del documento
  • Preservar voz del autor: sí/no
  • Máximo ratio de reescritura permitido

[BLOQUE 2] UBICACIÓN ESTRUCTURAL
  • Tipo de párrafo: narrativo, diálogo, técnico, lista, tabla, etc.
  • Sección actual y su resumen
  • Términos activos en la sección
  • Número de página / total de páginas
  • Advertencia si el párrafo cruza un salto de página

[BLOQUE 3] CONTEXTO PREVIO
  • Últimos N párrafos corregidos (ventana configurable, por defecto 15)
  • Con tipo de párrafo y etiqueta de categorías de cambio aplicados

[BLOQUE 4] REGLAS DEL USUARIO YA APLICADAS
  • Lista de sustituciones aplicadas en Fase 0 (NO revertir)

[BLOQUE 5] RESTRICCIONES DE REGISTRO
  • Lenguaje inclusivo / sin anglicismos / tuteo / voseo rioplatense / sin imperativo

[BLOQUE 6] IDIOLECTOS PROTEGIDOS
  • Rasgos de voz del autor que el LLM NO debe "corregir"

[BLOQUE 7] PÁRRAFO A CORREGIR

[BLOQUE 8] REGIONES PROTEGIDAS
  • Fragmentos exactos del párrafo que no se pueden modificar
```

El LLM responde en JSON estructurado con: `action`, `corrected_text`, `changes[]` (cada cambio con `original_fragment`, `corrected_fragment`, `category`, `severity`, `explanation`), `confidence`, `rewrite_ratio`.

### Fase 4 — LLM Pasada 2 (auditoría contextual)

Se activa cuando la Pasada 1 superó el umbral de reescritura. El auditor recibe:
- Texto original
- Corrección de Pasada 1
- Contexto global del documento

El auditor detecta **destrucciones** (términos técnicos alterados, nombres propios cambiados, sentido modificado) y las revierte. También aplica mejoras de estilo adicionales coherentes con la voz del autor.

Responde con: `final_text`, `reverted_destructions[]`, `style_improvements[]`, `confidence`, `pass1_quality`.

### Categorías de corrección

| Categoría | Qué corrige |
|-----------|-------------|
| `redundancia` | Palabras o frases redundantes |
| `claridad` | Oraciones confusas o ambiguas |
| `registro` | Ajuste del nivel de formalidad |
| `cohesion` | Conectores, transiciones, hilo argumental |
| `lexico` | Precisión en la elección de palabras |
| `estructura` | Reordenamiento sintáctico |
| `puntuacion` | Puntuación estilística |
| `ritmo` | Flujo y cadencia del texto |
| `muletilla` | Frases comodín y expresiones vacías |

### Severidades

| Severidad | Significado |
|-----------|-------------|
| `critico` | Error que afecta comprensión o cambia significado |
| `importante` | Mejora notable en calidad del texto |
| `sugerencia` | Mejora menor, opcional |

### Ventana de contexto acumulado

El sistema mantiene una ventana deslizante de los últimos **15 párrafos corregidos** (configurable con `CONTEXT_WINDOW_SIZE`). Esto garantiza coherencia terminológica y de estilo entre párrafos consecutivos. En modo paralelo por lotes, la ventana se inicializa con los últimos N párrafos del lote anterior.

---

## 7. Perfiles editoriales predefinidos (10 perfiles)

STYLIA incluye 10 perfiles editoriales cuidadosamente diseñados para los géneros más comunes en español. Cada perfil configura automáticamente el nivel de intervención, el registro, la audiencia y las prioridades de corrección.

### 1. `infantil_6_8` — Literatura infantil (6–8 años)

**Para**: Cuentos, álbumes ilustrados y primeros lectores.

- **Intervención**: Mínima — solo errores claros
- **Registro**: Informal, lenguaje sencillo
- **Audiencia**: Niños de 6 a 8 años, lectores principiantes
- **Tono**: Lúdico, accesible
- **Prioridades**: Claridad, ritmo, vocabulario asequible
- **Max reescritura**: 15%
- **Qué hace**: Corrige errores obvios sin alterar el ritmo de lectura ni el vocabulario intencional del autor. Preserva frases repetitivas típicas de la literatura infantil.

### 2. `infantil_9_12` — Literatura infantil (9–12 años)

**Para**: Novelas juveniles, aventuras, sagas para lectores intermedios.

- **Intervención**: Sutil
- **Registro**: Semi-formal, vocabulario en expansión
- **Audiencia**: Niños de 9 a 12 años
- **Tono**: Ágil, con algo de complejidad narrativa
- **Prioridades**: Claridad, cohesión, ritmo narrativo
- **Max reescritura**: 20%
- **Qué hace**: Mejora la cohesión entre párrafos y sugiere vocabulario más preciso cuando no afecta la accesibilidad del texto.

### 3. `ya_contemporanea` — Young Adult contemporánea

**Para**: Novela juvenil para adolescentes: romance, identidad, conflictos cotidianos.

- **Intervención**: Moderada
- **Registro**: Informal contemporáneo, coloquialismos
- **Audiencia**: Adolescentes (13–18 años)
- **Tono**: Cercano, emocional, directo
- **Prioridades**: Ritmo, autenticidad de voz, cohesión
- **Max reescritura**: 30%
- **Qué hace**: Preserva el registro coloquial y la voz del personaje. Corrige errores sin "formalizar" el texto. Los diálogos se tocan mínimamente.

### 4. `novela_contemporanea` — Novela literaria contemporánea

**Para**: Ficción literaria para adultos, narrativa de autor.

- **Intervención**: Sutil
- **Registro**: Literario, cuidado
- **Audiencia**: Adultos lectores habituales
- **Tono**: Variable según obra
- **Prioridades**: Voz del autor, ritmo, lexico preciso
- **Max reescritura**: 25%
- **Qué hace**: Interviene con mucho cuidado en el estilo. Prioriza preservar la voz única del autor. Solo corrige lo que es claramente un error, no lo que es una elección estilística.

### 5. `fantasia_ciencia_ficcion` — Fantasía y ciencia ficción

**Para**: Novelas de fantasía épica, ciencia ficción, distopía, space opera.

- **Intervención**: Moderada
- **Registro**: Literario con terminología especializada
- **Audiencia**: Adultos y jóvenes adultos fans del género
- **Tono**: Épico o especulativo
- **Prioridades**: Consistencia terminológica, cohesión, ritmo de acción
- **Max reescritura**: 35%
- **Qué hace**: Protege agresivamente la terminología inventada (nombres de lugares, razas, tecnologías, hechizos). Mejora la claridad en secuencias de acción. No cambia registros anacrónicos intencionales (inglés medieval, jerga futurista).

### 6. `ensayo_academico` — Ensayo académico y científico

**Para**: Artículos de investigación, ensayos universitarios, papers, tesis.

- **Intervención**: Moderada–Agresiva
- **Registro**: Académico formal
- **Audiencia**: Especialistas universitarios
- **Tono**: Objetivo, preciso, impersonal
- **Prioridades**: Precisión léxica, cohesión argumentativa, eliminación de muletillas
- **Max reescritura**: 40%
- **Qué hace**: Elimina redundancias, muletillas académicas, construcciones pasivas excesivas. Mejora la coherencia entre párrafos del argumento. Preserva terminología técnica de la disciplina. No informaliza el texto.

### 7. `comunicacion_corporativa` — Comunicación corporativa y empresarial

**Para**: Informes ejecutivos, presentaciones, comunicados, documentos de estrategia.

- **Intervención**: Agresiva
- **Registro**: Formal ejecutivo
- **Audiencia**: Directivos, stakeholders, profesionales del negocio
- **Tono**: Directo, orientado a resultados, sin ambigüedades
- **Prioridades**: Claridad, brevedad, eliminación de jerga innecesaria, estructura
- **Max reescritura**: 50%
- **Qué hace**: Reescribe párrafos verbosos en versiones más directas. Elimina redundancias corporativas. Mejora la estructura de listas y secciones. Asegura consistencia en el uso de términos del negocio.

### 8. `periodismo_divulgacion` — Periodismo y divulgación científica

**Para**: Artículos de prensa, reportajes, divulgación científica para público general.

- **Intervención**: Moderada
- **Registro**: Formal accesible
- **Audiencia**: Público general informado
- **Tono**: Claro, informativo, sin tecnicismos innecesarios
- **Prioridades**: Claridad, ritmo, cohesión, pirámide invertida
- **Max reescritura**: 30%
- **Qué hace**: Simplifica sin banalizar. Mejora las transiciones entre ideas. Adapta términos técnicos para audiencias no especializadas. Preserva nombres propios y cifras con precisión.

### 9. `libro_texto_universitario` — Libro de texto universitario

**Para**: Manuales universitarios, libros de texto, materiales de cursos.

- **Intervención**: Moderada
- **Registro**: Académico didáctico
- **Audiencia**: Estudiantes universitarios
- **Tono**: Claro, estructurado, pedagógico
- **Prioridades**: Claridad, estructura, precisión terminológica, ejemplos bien integrados
- **Max reescritura**: 35%
- **Qué hace**: Mejora la claridad de definiciones y explicaciones. Asegura coherencia terminológica a lo largo de capítulos. Mejora las transiciones entre conceptos. Preserva nomenclatura disciplinar.

### 10. `traduccion_literaria` — Traducción literaria

**Para**: Obras traducidas al español donde se busca naturalidad sin perder el original.

- **Intervención**: Sutil
- **Registro**: Literario naturalizado
- **Audiencia**: Lectores hispanohablantes adultos
- **Tono**: Variable según obra original
- **Prioridades**: Naturalidad en español, eliminación de calcos sintácticos, ritmo
- **Max reescritura**: 20%
- **Qué hace**: Detecta y corrige calcos del idioma original (estructuras sintácticas extrañas al español). Mejora la naturalidad sin perder el tono de la obra. No "hispaniza" en exceso textos que buscan mantener un sabor extranjero intencional.

---

## 8. Perfiles personalizados y ficha ADN editorial

### Crear un perfil personalizado

Además de los 10 presets, puedes crear perfiles totalmente personalizados:

```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/profile \
  -H "Content-Type: application/json" \
  -d '{
    "genre": "ensayo",
    "subgenre": "filosofia",
    "audience_type": "academica",
    "audience_age_range": "adultos",
    "audience_expertise": "experto",
    "register": "formal",
    "tone": "reflexivo",
    "intervention_level": "moderada",
    "preserve_author_voice": true,
    "max_rewrite_ratio": 0.30,
    "max_expansion_ratio": 1.10,
    "style_priorities": ["claridad", "cohesion", "lexico"],
    "protected_terms": ["dasein", "epoche", "lebenswelt"],
    "forbidden_changes": ["no sustituir 'ser' por 'estar'"]
  }'
```

### Ficha ADN editorial (pestaña "ADN Editorial")

Tras el análisis editorial (Etapa C), el sistema construye automáticamente el **ADN del documento**: una caracterización profunda del texto que va más allá del perfil manual.

El ADN incluye:

**Voz dominante**: Descripción de la voz narrativa detectada (ej. "primera persona introspectiva con oraciones largas y muchos incisos").

**Registro dominante**: Registro lingüístico predominante detectado en el corpus del documento.

**Resumen global**: Síntesis del contenido general del documento en 2–3 frases.

**Temas clave**: Los 8 temas más recurrentes con su peso relativo (%).

**Términos técnicos protegidos globalmente**: Lista de términos que el sistema detectó como técnicos, nombres propios o terminología especial. Estos términos se protegen en TODAS las llamadas al LLM para evitar que sean alterados. Por ejemplo: `STYLIA`, `tokenización`, `dasein`, nombres de personajes.

**Fingerprint de estilo**: Longitud media de oraciones (en palabras), ratio de voz pasiva, densidad léxica.

Puedes ver y editar la ficha ADN en la pestaña **"ADN Editorial"** de cualquier documento procesado.

### Campos avanzados del perfil

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `intervention_level` | `minima/sutil/moderada/agresiva` | Qué tanto puede cambiar el LLM |
| `preserve_author_voice` | boolean | Si es `true`, el LLM es más conservador |
| `max_rewrite_ratio` | 0.0–1.0 | Máximo porcentaje del texto que puede reescribirse |
| `max_expansion_ratio` | 1.0–1.5 | Máximo que puede crecer el texto corregido (1.10 = +10%) |
| `target_inflesz_min/max` | float | Rango de legibilidad INFLESZ objetivo |
| `style_priorities` | string[] | Qué categorías priorizar: `claridad`, `cohesion`, `lexico`... |
| `protected_terms` | string[] | Términos que nunca deben cambiarse |
| `forbidden_changes` | string[] | Instrucciones explícitas de qué no hacer |
| `lt_disabled_rules` | string[] | Reglas de LanguageTool a ignorar |

---

## 9. Reglas personalizadas: sustitución, entidades e idiolectos

La pestaña **"ADN Editorial"** permite configurar 4 tipos de reglas avanzadas que se aplican **antes** de LanguageTool (Fase 0) y se refuerzan en el prompt del LLM.

### Reglas de sustitución

Permiten definir búsquedas y reemplazos automáticos con texto exacto o regex:

```json
{
  "find": "inteligencia artificial",
  "replace": "IA",
  "case_sensitive": false,
  "is_regex": false,
  "scope": "all",
  "enabled": true
}
```

- **`find`**: Texto a buscar (o patrón regex si `is_regex=true`)
- **`replace`**: Texto de reemplazo (vacío = eliminar)
- **`case_sensitive`**: Si es `false`, busca `AI`, `ai`, `Ai`, etc.
- **`is_regex`**: Si es `true`, `find` se interpreta como expresión regular Python
- **`scope`**: `all` (todo el doc), `narrative` (solo narración), `dialogue` (solo diálogos)

**Ejemplos de uso**:
- Unificar el uso de siglas: `"inteligencia artificial"` → `"IA"`
- Corregir nombre de marca: `"Stylia"` → `"STYLIA"`
- Eliminar muletilla: `"en este sentido,"` → `""`
- Regex: `\bdon\b` → `Don` (capitalizar tratamiento)

Las sustituciones se registran con `correction_phase="substitution"` y el LLM recibe instrucción explícita de no revertirlas.

### Normalizaciones de entidades

Para nombres propios con múltiples variantes ortográficas:

```json
{
  "canonical": "STYLIA",
  "generic": "stylia",
  "aliases": ["Stylia", "STYLA", "S.T.Y.L.I.A."],
  "enabled": true
}
```

Todas las variantes listadas en `generic` y `aliases` se reemplazan por `canonical`. Ideal para:
- Nombres de marcas o productos con grafías variables
- Nombres de personajes con errores tipográficos
- Siglas que aparecen con o sin puntos

### Idiolectos protegidos

Protegen rasgos de voz del autor que el LLM podría "corregir" por considerarlos erróneos:

```json
{
  "description": "El narrador omite artículos en frases nominales para crear ritmo staccato",
  "scope": "narrative",
  "examples": ["Ciudad desierta", "Tarde gris", "Hombre sin nombre"],
  "enabled": true
}
```

El LLM recibe estas instrucciones y evita "normalizar" esos patrones aunque parezcan incorrectos gramaticalmente.

Útil para:
- Estilo telegráfico intencional
- Uso particular de tiempos verbales
- Construcciones sintácticas características del autor
- Variantes dialectales intencionales

### Restricciones de registro

Opciones preconfiguradas que el LLM debe respetar en todo el documento:

| Restricción | Qué hace |
|------------|---------|
| `lenguaje_inclusivo` | Prefiere formas no binarias cuando sea posible |
| `sin_anglicismos` | Sustituye préstamos del inglés por equivalentes en español |
| `tuteo_exclusivo` | Garantiza uso de "tú", nunca "usted" |
| `sin_imperativo` | Evita el modo imperativo en textos expositivos |
| `voseo_rioplatense` | Usa "vos/tenés/podés" en lugar de "tú/tienes/puedes" |

### Simular impacto antes de procesar

Antes de lanzar el pipeline, puedes estimar el impacto del perfil actual:

```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/simulate-impact
```

Devuelve:
- Número de sustituciones que se aplicarían
- Distribución de routing (cuántos párrafos serían SKIP / CHEAP / EDITORIAL)
- Estimación de tokens de entrada y salida
- **Costo estimado en USD**
- Duración estimada del procesamiento
- Advertencias de configuración

---

## 10. Bloques del prompt: control granular

El sistema de bloques del prompt (PromptBlocksConfig) permite habilitar o deshabilitar exactamente qué información se incluye en el prompt de cada llamada al LLM, con control por tipo de párrafo.

### Los 9 bloques configurables

| Bloque | ID | Contenido | Por defecto |
|--------|----|-----------|-------------|
| 0 | `global_context` | ADN del documento: voz, registro, términos globales protegidos, fingerprint de estilo | Activado |
| 1 | `editorial_profile` | Perfil editorial: nivel de intervención, registro, audiencia, tono, max ratio de reescritura | Activado |
| 2 | `structural_location` | Tipo de párrafo, sección actual, resumen de sección, términos activos, posición en documento | Activado |
| 3 | `previous_context` | Últimos N párrafos corregidos (ventana deslizante de 15 párrafos) | Activado |
| 4 | `user_substitutions` | Sustituciones aplicadas en Fase 0 que el LLM no debe revertir | Solo si hay sustituciones |
| 5 | `register_restrictions` | Restricciones de registro: sin anglicismos, voseo, lenguaje inclusivo, etc. | Solo si hay restricciones |
| 6 | `protected_idiolects` | Rasgos de voz del autor que el LLM no debe "corregir" | Solo si hay idiolectos |
| 7 | `paragraph_text` | El texto del párrafo a corregir | Siempre |
| 8 | `protected_regions` | Fragmentos del párrafo que no pueden modificarse | Solo si hay regiones protegidas |

### Filtrado por tipo de párrafo

La función `_blocks_for_paragraph_type()` determina qué bloques se incluyen según el tipo del párrafo actual:

| Tipo de párrafo | Bloques omitidos | Razón |
|----------------|-----------------|-------|
| `titulo` / `subtitulo` | 3 (contexto previo), 6 (idiolectos) | Los títulos no necesitan coherencia con el flujo narrativo |
| `pie_pagina` / `encabezado` | 3 (contexto previo), 6 (idiolectos) | Elementos de plantilla, sin contexto narrativo |
| `celda_tabla_total` | 1, 3, 4, 5, 6 | Celdas de totales: solo verificar integridad numérica |
| `nota_pie` | 6 (idiolectos) | Notas formales, sin voz del autor |
| `lista` (manual) | — | Todos los bloques, con reglas especiales de lista |
| `lista` (nativa) | 3 (contexto previo) | La lista nativa se corrige como grupo, no secuencialmente |

Esto reduce el número de tokens enviados por párrafo (y el costo) cuando el tipo de elemento no necesita toda la información de contexto.

### Configuración por perfil

En el perfil editorial puedes habilitar o deshabilitar bloques globalmente:

```json
{
  "prompt_blocks_config": {
    "global_context": true,
    "editorial_profile": true,
    "structural_location": true,
    "previous_context": true,
    "user_substitutions": true,
    "register_restrictions": false,
    "protected_idiolects": false,
    "protected_regions": true
  }
}
```

### Visualización en el panel PromptBlocks (UI)

La pestaña "Flujo API" incluye el panel PromptBlocksPanel que muestra, párrafo por párrafo:
- Qué bloques estaban habilitados en esa llamada
- El contenido exacto de cada bloque enviado
- Los tokens consumidos por bloque
- Por qué se omitió un bloque (tipo de párrafo, sin datos, perfil)

---

## 11. Las pestañas de la interfaz: qué hace cada una

### Pestaña "Resumen"

La primera pestaña tras abrir un documento. Muestra:

- **Estado actual** del documento con barra de progreso por etapas
- **Perfil editorial** asignado: nivel de intervención, registro, audiencia, tono
- **Estadísticas de corrección**: total de correcciones, distribución por categoría (con barras de color), distribución por severidad
- **Distribución de rutas**: cuántos párrafos fueron SKIP / CHEAP / EDITORIAL
- **Métricas de calidad**: correcciones aprobadas vs. pendientes vs. rechazadas
- **Información del documento**: páginas, estado de páginas, fechas de procesamiento
- **Botones de acción**: Finalizar, Reabrir, Descargar PDF/DOCX

### Pestaña "Análisis"

Resultado de la Etapa C (análisis editorial). Muestra:

**Perfil inferido automáticamente**:
- Género detectado
- Tipo de audiencia
- Registro lingüístico predominante
- Tono
- Variante del español (peninsular, rioplatense, mexicana, etc.)
- Términos clave detectados
- Nivel de intervención sugerido

**Secciones del documento**:
- Índice de secciones detectadas (capítulos, partes, secciones)
- Resumen de cada sección
- Tópico principal
- Términos activos en esa sección
- Tono local de la sección

**Glosario de términos**:
- Todos los términos frecuentes con su frecuencia
- Primera aparición (número de párrafo)
- Forma normalizada
- Si está protegido (no se puede cambiar)
- Decisión tomada (proteger / normalizar / ignorar)

**Distribución de tipos de párrafo**:
- Gráfico de barras con la distribución de los 11 tipos de párrafo detectados
- `narrativo`, `dialogo`, `explicacion_tecnica`, `lista`, `celda_tabla`, `pie_imagen`, `titulo`, `subtitulo`, `cita`, `encabezado`, `footer`

### Pestaña "Correcciones"

El panel central de revisión. Tiene dos modos de vista:

**Vista de revisión** (por defecto):
- Lista completa de todas las correcciones aplicadas
- **Diff word-level** para cada corrección: qué palabras se eliminaron (tachado en rojo) y qué se añadió (en verde)
- **Badge de categoría**: redundancia / claridad / registro / cohesion / lexico / estructura / puntuacion / ritmo / muletilla
- **Badge de severidad**: crítico (rojo) / importante (amarillo) / sugerencia (gris)
- **Badge de ruta**: SKIP / CHEAP / EDITORIAL (muestra qué modelo lo procesó)
- **Badge de fase**: substitution / lt / llm_micro / audit / llm_macro
- **Confianza del LLM** (%)
- **Ratio de reescritura** (%)
- **Resultado de quality gates**: qué gates pasaron y cuáles fallaron
- **Explicación** del LLM sobre por qué hizo cada cambio
- **Filtros**: por categoría, severidad, ruta, estado de revisión
- **Acciones HITL**: aprobar / rechazar / editar cada patch individualmente

**Vista por fase**:
- Resumen de cuántas correcciones vinieron de cada fase (sustitución / LT / LLM micro / auditoría / macro)
- Barras de distribución con porcentajes
- Filtro por fase para ver solo las correcciones de un tipo
- Si hay correcciones macro (S5), se indica con badge especial

### Pestaña "ADN Editorial"

Panel de configuración avanzada del perfil editorial. Accesible cuando el documento está en `candidate_ready` o superior.

**Sección ADN auto-detectado**:
- Voz dominante del autor (texto descriptivo)
- Registro base del documento
- Resumen global
- Temas clave con porcentajes de peso
- Términos técnicos protegidos globalmente (con su razón de protección)

**Editor de reglas de sustitución**:
- Lista de reglas activas con indicador de estado (activa / inactiva)
- Formulario para agregar nueva regla: buscar / reemplazar / regex / case-sensitive
- Botón de eliminar por regla
- Las reglas se aplican en Fase 0 antes de cualquier corrección automática

**Editor de normalizaciones de entidades**:
- Lista de normalizaciones con forma canónica y variantes
- Formulario: forma canónica / forma genérica / alias (separados por coma)
- Eliminar por ID

**Editor de idiolectos protegidos**:
- Lista de idiolectos con descripción y ejemplos
- Formulario: descripción / alcance (todo / narración / diálogos) / ejemplos
- Eliminar por ID

**Selector de restricciones de registro**:
- 5 opciones toggle: lenguaje inclusivo / sin anglicismos / tuteo / sin imperativo / voseo rioplatense
- Al activar una, se guarda inmediatamente en el perfil

**Estimador de impacto**:
- Botón "Simular impacto" que analiza el texto sin procesar
- Muestra: sustituciones estimadas, costo en USD, duración estimada, distribución de routing

**Pase macro** (si el documento está en `candidate_ready`):
- Botón "Lanzar pase macro" para iniciar la corrección holística por sección
- Solo disponible si el perfil tiene `macro_correction_level = "light"` o `"full"`

### Pestaña "Flujo API"

Visualización de debug del pipeline de corrección. Muestra:

- Timeline de cada llamada a LanguageTool y a OpenAI
- Configuración del prompt enviado al LLM (perfil codificado, parámetros)
- Para cada párrafo: texto original → post-LT → post-LLM Pasada 1 → post-auditoría
- Diferencias entre pasadas
- Tokens consumidos y latencia por llamada

Útil para entender qué hizo exactamente el sistema en cada párrafo y diagnosticar comportamientos inesperados.

### Pestaña "Comparar"

Vista side-by-side del documento original vs. el documento corregido:

- Preview visual de cada página (PNG generado en Etapa B)
- Anotaciones superpuestas indicando las correcciones en su posición exacta dentro de la página
- Navegación por páginas
- Modo "solo correcciones": resalta solo las páginas con cambios
- Cada anotación muestra: categoría, severidad, texto original y texto corregido

---

## 12. Quality gates: validación automática de correcciones

Antes de presentar cada corrección al revisor humano, el sistema ejecuta 5 validaciones automáticas:

### Gates críticos (descartan la corrección si fallan)

| Gate | Qué valida | Umbral |
|------|-----------|--------|
| `not_empty` | El texto corregido no está vacío | — |
| `expansion_ratio` | El texto corregido no supera el máximo de expansión | Configurable (por defecto 1.10) |
| `protected_terms` | Ningún término protegido fue alterado | 0 alteraciones |

Si un gate crítico falla, la corrección se marca como `gate_rejected` y se aplica el texto original. El revisor puede ver qué gate falló y por qué.

### Gates no críticos (marcan para revisión manual si fallan)

| Gate | Qué valida | Umbral |
|------|-----------|--------|
| `rewrite_ratio` | El ratio de reescritura no supera el máximo del perfil | Configurable |
| `language_preserved` | El idioma del texto corregido sigue siendo español | — |
| `readability_inflesz` | La legibilidad INFLESZ está dentro del rango objetivo | Configurable por perfil |

Si un gate no crítico falla, la corrección se marca como `manual_review`. El revisor humano puede aprobarla de todos modos.

### Gates estructurales (por tipo de párrafo)

Estos gates adicionales se ejecutan según el tipo de párrafo detectado en B.5:

| Gate | Tipo de párrafo | Qué valida |
|------|----------------|-----------|
| `title_no_final_period` | `titulo` / `subtitulo` | El título corregido no termina con punto final |
| `caption_starts_with_label` | `pie_figura` | La corrección preserva el prefijo "Figura X:" o "Gráfico X:" |
| `table_cell_uniform_capitalization` | `celda_tabla_header` | Los encabezados de columna mantienen capitalización uniforme |
| `list_format_consistent` | `lista` (manual) | El prefijo del ítem (1., 2), •) no fue alterado |
| `list_parallel_structure` | `lista` | Los ítems del grupo mantienen estructura gramatical paralela |

Los gates estructurales son **no críticos**: si fallan, marcan `manual_review` pero no descartan la corrección.

### Resultado en el patch

```json
{
  "gate_results": [
    {"gate_name": "not_empty", "passed": true, "critical": true},
    {"gate_name": "expansion_ratio", "passed": true, "value": 1.05, "threshold": 1.10, "critical": true},
    {"gate_name": "protected_terms", "passed": true, "critical": true},
    {"gate_name": "rewrite_ratio", "passed": false, "value": 0.42, "threshold": 0.30, "critical": false,
     "message": "Reescritura del 42% supera el umbral del 30%"},
    {"gate_name": "list_format_consistent", "passed": true, "critical": false,
     "message": "Prefijo '2)' preservado correctamente"}
  ],
  "review_status": "manual_review",
  "review_reason": "rewrite_ratio_exceeded"
}
```

---

## 13. Revisión humana (HITL)

Cuando el pipeline termina, el documento entra en `candidate_ready`. La interfaz muestra el candidato listo para revisión.

### Acciones disponibles por corrección

| Acción | Qué hace |
|--------|---------|
| **Aprobar** | La corrección se aplica en el documento final |
| **Rechazar** | Se usa el texto original en ese párrafo |
| **Editar** | El revisor escribe manualmente el texto definitivo |

### Recorrección individual

Si rechazas una corrección y editas el texto manualmente, puedes lanzar una recorrección solo de ese párrafo con feedback adicional:

```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/corrections/$PATCH_ID/recorrect \
  -H "Content-Type: application/json" \
  -d '{"feedback": "Mantener el término técnico pero mejorar la puntuación"}'
```

### Acciones bulk

Puedes aprobar o rechazar múltiples correcciones de una vez:

```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/corrections/bulk-action \
  -H "Content-Type: application/json" \
  -d '{"patch_ids": ["id1", "id2", "id3"], "action": "accepted"}'
```

### Finalización

Una vez que el revisor terminó:

```bash
# Modo rápido: aplica todas las correcciones aprobadas + auto-aceptadas
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/finalize \
  -d '{"mode": "quick"}'

# Modo estricto: solo aplica las explícitamente aprobadas por el revisor
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/finalize \
  -d '{"mode": "strict"}'
```

### Reabrir un documento

Si después de finalizar necesitas revisar de nuevo:

```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/reopen
```

Vuelve a `candidate_ready` para permitir edición adicional.

### Resumen de revisión

Antes de finalizar, puedes consultar el resumen de revisión:

```bash
curl http://localhost:8000/api/v1/documents/$DOC_ID/review-summary
```

Devuelve:
- Total de patches
- Cuántos están auto-aceptados, pendientes, aprobados, rechazados, en revisión manual, rechazados por gates
- Si se puede finalizar en modo quick/strict
- Distribución por severidad y por página

---

## 14. Corrección macro por sección

La corrección macro es una **tercera pasada opcional** que opera sobre el documento completo una vez terminadas todas las correcciones micro (por párrafo).

### Qué hace la corrección macro

Mientras la corrección micro mejora cada párrafo de forma independiente, la corrección macro **ve el documento como un todo** y detecta:

- **Problemas de coherencia**: un término aparece con significados distintos en diferentes secciones
- **Transiciones abruptas**: cambios de tema sin conectores adecuados entre secciones
- **Inconsistencias de registro**: un párrafo usa "usted" y el siguiente "tú" en el mismo capítulo
- **Terminología inconsistente**: el mismo concepto se llama de tres formas distintas a lo largo del texto

La corrección macro trabaja **por sección** (no por documento completo) para mantener los prompts manejables. Genera patches con `correction_phase="llm_macro"`.

### Cómo activarla

1. Configurar en el perfil editorial:
```bash
curl -X PATCH http://localhost:8000/api/v1/documents/$DOC_ID/editorial-profile \
  -H "Content-Type: application/json" \
  -d '{"macro_correction_level": "light"}'
```

2. Una vez que el documento está en `candidate_ready`, lanzar el pase macro:
```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/recorrect-macro
```

3. Las correcciones macro aparecen en la pestaña "Correcciones" con badge `LLM Macro` en color verde azulado.

### Niveles de corrección macro

| Nivel | Qué hace |
|-------|---------|
| `none` | Sin pase macro (comportamiento por defecto) |
| `light` | Solo transiciones abruptas y repeticiones semánticas obvias |
| `full` | Revisión estructural completa + coherencia terminológica + fluidez entre secciones |

---

## 15. Costos y métricas LLM

STYLIA rastrea el costo de cada llamada al LLM con precisión de párrafo.

### Vista de costos (`/costs`)

La página de costos muestra:

- **Total acumulado**: costo total en USD de todos los documentos procesados
- **Desglose por modelo**: cuánto costó `gpt-4o-mini` vs. el modelo editorial vs. el modelo de auditoría
- **Desglose por documento**: ranking de documentos más costosos
- **Métricas de eficiencia**: costo promedio por documento, costo por llamada, tokens promedio

### API de costos

```bash
# Resumen global
curl http://localhost:8000/api/v1/costs/summary

# Por documento (ranking)
curl http://localhost:8000/api/v1/costs/documents

# Desglose párrafo por párrafo de un documento específico
curl http://localhost:8000/api/v1/documents/$DOC_ID/costs
```

### Cómo se calculan los costos

El sistema usa los precios oficiales de OpenAI (configurable en `.env`):
- `OPENAI_PRICING_INPUT`: precio por millón de tokens de entrada (por defecto $0.75/M para gpt-4o-mini)
- `OPENAI_PRICING_OUTPUT`: precio por millón de tokens de salida (por defecto $4.50/M)

Cada llamada registra en `llm_usage`: modelo usado, tokens de entrada/salida, costo calculado, tipo de llamada (micro / auditoría / macro), índice de párrafo.

### Estimación antes de procesar

Usa el endpoint `/simulate-impact` para estimar el costo antes de procesar el documento. La estimación es una heurística basada en el número de párrafos y su longitud media, con el perfil configurado.

---

## 16. API REST completa

Base URL: `http://localhost:8000/api/v1`

### Flujo principal

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/upload` | Sube documento DOCX |
| POST | `/documents/{id}/process` | Lanza el pipeline completo |
| GET | `/health` | Health check del sistema |

### Perfiles editoriales (CRUD básico)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/presets` | Lista los 10 perfiles predefinidos |
| POST | `/documents/{id}/profile` | Crea perfil editorial (desde preset o custom) |
| GET | `/documents/{id}/profile` | Lee el perfil editorial del documento |
| PUT | `/documents/{id}/profile` | Actualiza el perfil editorial completo |

### Ficha ADN editorial (Renovación S2)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents/{id}/editorial-profile` | Perfil completo + ADN auto-detectado + `is_locked` |
| PATCH | `/documents/{id}/editorial-profile` | Actualización parcial del perfil (bloqueado si está en corrección) |
| POST | `/documents/{id}/editorial-profile/rules` | Agrega regla de sustitución, normalización o idiolecto |
| DELETE | `/documents/{id}/editorial-profile/rules/{rule_id}` | Elimina una regla por ID (idempotente) |
| POST | `/documents/{id}/simulate-impact` | Estima impacto del perfil sin procesar el documento |

### Documentos y resultados

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents` | Lista documentos (con paginación) |
| GET | `/documents/{id}` | Detalle del documento (estado, progreso, estadísticas) |
| GET | `/documents/{id}/pages` | Lista de páginas con número de correcciones y URIs de preview |
| GET | `/documents/{id}/corrections` | Todas las correcciones del documento |
| DELETE | `/documents/{id}` | Elimina el documento |

### Análisis y métricas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents/{id}/analysis` | Resultado del análisis editorial (secciones, glosario, clasificación) |
| GET | `/documents/{id}/structure` | Árbol estructural del documento: listas y tablas detectadas en B.5 con sus ítems |
| GET | `/documents/{id}/correction-flow` | Flujo de correcciones con contexto jerárquico |
| GET | `/documents/{id}/correction-batches` | Estado de lotes de corrección paralela |
| GET | `/documents/{id}/global-context` | ADN global del documento |
| GET | `/documents/{id}/llm-audit` | Registro de auditoría de llamadas LLM |
| GET | `/documents/{id}/llm-audit/{paragraph_index}` | Detalle de llamadas LLM para un párrafo |
| GET | `/documents/{id}/structural-map` | Mapa estructural de párrafos por página |

### Previews y descargas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents/{id}/pages/{no}/preview` | PNG preview de la página original |
| GET | `/documents/{id}/pages/{no}/preview-corrected` | PNG preview con anotaciones de correcciones |
| GET | `/documents/{id}/pages/{no}/annotations` | Posiciones de correcciones en la página (JSON) |
| GET | `/documents/{id}/download/pdf` | Stream del PDF corregido |
| GET | `/documents/{id}/download/docx` | Stream del DOCX corregido |

### Revisión humana (HITL)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/documents/{id}/review-summary` | Resumen de correcciones pendientes de revisión |
| PATCH | `/documents/{id}/corrections/{patch_id}` | Aprobar o rechazar un patch |
| PATCH | `/documents/{id}/corrections/{patch_id}/edit` | Editar manualmente el texto de un patch |
| POST | `/documents/{id}/corrections/bulk-action` | Aprobar o rechazar múltiples patches |
| POST | `/documents/{id}/corrections/{patch_id}/recorrect` | Relanzar corrección de un párrafo con feedback |
| POST | `/documents/{id}/finalize` | Finalizar documento tras revisión |
| POST | `/documents/{id}/reopen` | Reabrir documento completado para nueva revisión |
| POST | `/documents/{id}/rerender-preview` | Regenerar preview candidato |

### Corrección macro (S5)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/documents/{id}/recorrect-macro` | Lanza el pase de corrección holística por sección |

### Costos LLM

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/costs/summary` | Resumen global de costos |
| GET | `/costs/documents` | Costos agregados por documento |
| GET | `/documents/{id}/costs` | Desglose de costos por párrafo |

### Salud del sistema

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check general |
| GET | `/health/llm` | Estado del LLM (latencia, modelo activo) |
| GET | `/health/languagetool` | Estado de LanguageTool (latencia, versión) |

---

## 17. Variables de entorno

Archivo base: `.env.example`. Copiar a `.env` y completar.

### Base de datos

```env
DATABASE_URL=postgresql+asyncpg://stylecorrector:changeme@postgres:5432/stylecorrector
DATABASE_URL_SYNC=postgresql+psycopg2://stylecorrector:changeme@postgres:5432/stylecorrector
```

### Redis y Celery

```env
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
CELERY_TASK_TIME_LIMIT=7200
CELERY_TASK_SOFT_TIME_LIMIT=6900
```

### MinIO (almacenamiento de archivos)

```env
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=stylecorrector
MINIO_SECURE=false
```

### LanguageTool

```env
LANGUAGETOOL_URL=http://languagetool:8010
LANGUAGETOOL_LANGUAGE=es
```

### OpenAI

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini              # Modelo principal (micro corrección)
OPENAI_CHEAP_MODEL=gpt-4o-mini        # Modelo para párrafos simples (ruta CHEAP)
OPENAI_EDITORIAL_MODEL=gpt-4o-mini    # Modelo para párrafos complejos (ruta EDITORIAL)
OPENAI_TEMPERATURE=0.3                # Conservador para edición
OPENAI_MAX_TOKENS=2000
OPENAI_AUDIT_MAX_TOKENS=6000         # Para la Pasada 2 de auditoría
OPENAI_EDITORIAL_MAX_TOKENS=4000     # Para párrafos editoriales complejos
```

### Precios OpenAI (para cálculo de costos)

```env
OPENAI_PRICING_INPUT=0.75    # USD por millón de tokens de entrada
OPENAI_PRICING_OUTPUT=4.50   # USD por millón de tokens de salida
```

### Parámetros del pipeline

```env
MAX_UPLOAD_SIZE_MB=500
MAX_DOCUMENT_PAGES=1000
CONTEXT_WINDOW_SIZE=15          # Párrafos previos como contexto del LLM (defecto: 15, triplicado)
PASS2_ENABLED=true              # Activar Pasada 2 (auditoría contextual)
PASS2_REWRITE_THRESHOLD=0.15    # Umbral mínimo de reescritura para activar Pasada 2
GLOBAL_CONTEXT_SAMPLE_SIZE=9    # Párrafos muestreados para construir ADN global
```

### Corrección paralela por lotes (documentos grandes)

```env
PARALLEL_CORRECTION_ENABLED=false     # OFF por defecto, ON para docs grandes
PARALLEL_CORRECTION_BATCH_SIZE=150    # Párrafos por lote
PARALLEL_CORRECTION_MAX_BATCHES=8     # Máximo de lotes simultáneos
PARALLEL_CORRECTION_LT_WORKERS=8     # Threads para LanguageTool paralelo
PARALLEL_CORRECTION_BOUNDARY_CHECK=true  # Re-verificar primer párrafo de cada lote
```

---

## 18. Arquitectura y stack tecnológico

### Diagrama de servicios

```
Usuario (Browser)
    │
    ▼
[Frontend Next.js 14] ─── puerto 3000
    │ (rewrites /api/v1/* → backend)
    ▼
[Backend FastAPI] ─────── puerto 8000
    │
    ├─► [PostgreSQL 16] ── puerto 5432 (estado, patches, análisis, costos)
    ├─► [Redis 7] ──────── puerto 6379 (broker Celery + cache DOCX)
    ├─► [MinIO] ─────────── puerto 9000 (archivos: DOCX, PDF, JSON, PNG)
    ├─► [LanguageTool] ──── puerto 8010 (nginx balanceando 2 instancias Java)
    └─► [OpenAI API] ──────── internet (LLM gpt-4o-mini)

[Celery Workers]
    ├─► worker-pipeline (1 instancia, cola: pipeline)
    └─► worker-batch    (1 instancia, cola: batch)

[LibreOffice headless] — ejecutado inline para conversión DOCX↔PDF
```

### Stack tecnológico

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Backend API | FastAPI | 0.115.6 |
| Python runtime | Python | 3.11 |
| ORM | SQLAlchemy async | 2.0.36 |
| Base de datos | PostgreSQL | 16-alpine |
| Cache / Broker | Redis | 7-alpine |
| Cola de tareas | Celery | 5.4.0 |
| Almacenamiento | MinIO (S3-compatible) | latest |
| Corrector gramatical | LanguageTool | latest (Java, Docker) |
| LLM | OpenAI SDK | 1.51.0 |
| Procesamiento DOCX | python-docx | 1.1.2 |
| Extracción PDF | PyMuPDF (fitz) | 1.25.1 |
| Conversión documentos | LibreOffice headless | sistema |
| Frontend framework | Next.js | 14.2.21 |
| UI library | React | 18.3.1 |
| Lenguaje frontend | TypeScript | 5.7.2 |
| Estilos | Tailwind CSS | 3.4.17 |
| Contenedores | Docker Compose | 3.8 |

### Base de datos: tablas principales

| Tabla | Propósito |
|-------|-----------|
| `documents` | Documento maestro: estado, rutas MinIO, métricas de costo |
| `document_profiles` | Perfil editorial del documento (10 presets + campos personalizados + reglas S0–S5) |
| `pages` | Páginas individuales del documento con URIs de preview |
| `blocks` | Bloques de texto por página con clasificación y tipo |
| `patches` | Correcciones: original, corregido, categoría, severidad, ruta, gates, fase |
| `jobs` | Tracking de tareas Celery por documento |
| `llm_usage` | Uso de LLM por llamada: tokens, costo, modelo, fase |
| `section_summaries` | Secciones detectadas con resumen y términos activos |
| `term_registry` | Glosario de términos con frecuencia y estado de protección |
| `correction_batches` | Lotes de corrección paralela para documentos grandes |
| `document_global_context` | ADN global: voz, registro, temas, términos protegidos, fingerprint |
| `llm_audit_log` | Log completo de cada llamada LLM: request/response raw, latencia |
| `element_groups` | Grupos estructurales detectados en B.5: listas y tablas con todos sus ítems |

---

## 19. Estructura del repositorio

```
corrector de estilos/
├── backend/
│   ├── app/
│   │   ├── main.py               # Entry point FastAPI + migraciones DB en startup
│   │   ├── config.py             # Todas las variables de configuración (Pydantic Settings)
│   │   ├── database.py           # SQLAlchemy async engine + session
│   │   ├── api/v1/
│   │   │   └── documents.py      # Todos los endpoints REST (~50 endpoints)
│   │   ├── models/               # ORM: 12 tablas
│   │   ├── schemas/              # Pydantic: request/response + validación
│   │   ├── data/
│   │   │   └── profiles.py       # 10 perfiles editoriales predefinidos
│   │   ├── services/
│   │   │   ├── ingestion.py      # Etapa A: upload + DOCX→PDF
│   │   │   ├── extraction.py     # Etapa B: layout extraction (PyMuPDF)
│   │   │   ├── extraction_docx.py # Etapa B.5: extracción estructural DOCX (listas y tablas)
│   │   │   ├── group_collector.py # Recolección de ítems de ElementGroup para D.5
│   │   │   ├── analysis.py       # Etapa C: análisis editorial
│   │   │   ├── correction.py     # Etapa D: LT + LLM + gates (núcleo del sistema)
│   │   │   ├── prompt_builder.py # Construcción de prompts parametrizados
│   │   │   ├── complexity_router.py  # Router SKIP/CHEAP/EDITORIAL
│   │   │   ├── quality_gates.py  # 5 gates de validación post-corrección
│   │   │   ├── substitution_engine.py  # Fase 0: reglas de sustitución del usuario
│   │   │   ├── protected_regions.py    # Detección de regiones protegidas en texto
│   │   │   ├── engine_router.py        # Orquestador LT + regiones protegidas
│   │   │   ├── macro_correction.py     # S5: corrección holística por sección
│   │   │   ├── rendering.py      # Etapa E: aplicar patches al DOCX
│   │   │   └── context_accumulator.py # Gestión del contexto acumulado del LLM
│   │   ├── workers/
│   │   │   ├── celery_app.py     # Configuración Celery (2 colas)
│   │   │   └── tasks_pipeline.py # Pipeline completo + tareas paralelas + macro
│   │   └── utils/
│   │       ├── openai_client.py  # Cliente OpenAI con retry, semáforo y auditoría
│   │       ├── minio_client.py   # Operaciones MinIO/S3
│   │       └── pdf_utils.py      # LibreOffice + PyMuPDF
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx        # Layout global (header STYLIA, footer)
│   │   │   ├── page.tsx          # Dashboard: upload + lista + selector perfil
│   │   │   ├── costs/page.tsx    # Vista de costos y métricas LLM
│   │   │   └── documents/[id]/
│   │   │       └── page.tsx      # Detalle: 6 tabs (resumen, análisis, correcciones,
│   │   │                         #          adn editorial, flujo api, comparar)
│   │   ├── components/
│   │   │   ├── DocumentUploader.tsx      # Drag-drop .docx
│   │   │   ├── DocumentList.tsx          # Grid de documentos con estado
│   │   │   ├── PipelineFlow.tsx          # Visualización pipeline en tiempo real
│   │   │   ├── CorrectionHistory.tsx     # Correcciones con diff word-level
│   │   │   ├── CorrectionActionPanel.tsx # Acciones HITL
│   │   │   ├── DiffCompareView.tsx       # Comparación side-by-side
│   │   │   ├── CorrectionFlowViewer.tsx  # Flujo de llamadas LLM
│   │   │   ├── AnalysisView.tsx          # Análisis editorial: secciones, glosario
│   │   │   ├── EditorialProfilePanel.tsx # ADN editorial + editor de reglas
│   │   │   ├── MacroCorrectionView.tsx   # Vista por fase de corrección
│   │   │   ├── ProfileEditor.tsx         # Editor de perfil editorial
│   │   │   ├── ProfileSelector.tsx       # Selector de presets
│   │   │   ├── LLMAuditPanel.tsx         # Panel de auditoría LLM
│   │   │   ├── StructuralTree.tsx        # Árbol visual de estructura DOCX (listas y tablas)
│   │   │   └── PromptBlocksPanel.tsx     # Visualización de bloques del prompt por párrafo
│   │   └── lib/
│   │       └── api.ts            # Cliente API: tipos TypeScript + funciones fetch
│
├── landing/                      # Sitio landing (Next.js, puerto 3001)
├── docker-compose.yml            # 11 servicios
├── .env.example                  # Template de variables de entorno
└── fonts/                        # Liberation + Noto (para LibreOffice)
```

---

## 20. Comandos de desarrollo

### Stack completo con Docker

```bash
# Levantar todo
docker compose up -d --build

# Ver logs de un servicio
docker compose logs -f backend
docker compose logs -f worker-pipeline

# Parar todo
docker compose down

# Parar y borrar volúmenes (base de datos y almacenamiento)
docker compose down -v
```

### Backend local (sin Docker)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Workers Celery local

```bash
cd backend
# Worker del pipeline principal
celery -A app.workers.celery_app worker --loglevel=info --queues=pipeline --concurrency=2

# Worker de lotes paralelos
celery -A app.workers.celery_app worker --loglevel=info --queues=batch --concurrency=4
```

### Frontend local

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### Landing local

```bash
cd landing
npm install
npm run dev   # http://localhost:3001
```

---

## 21. Limitaciones actuales y roadmap

### Limitaciones actuales

| Limitación | Detalle |
|-----------|---------|
| Formato de entrada | Solo DOCX. PDF, ODT, RTF en roadmap. |
| PDF escaneados | Sin OCR aún (Ruta 3 en roadmap) |
| PDF digitales | Solo vía conversión desde DOCX (Ruta 2 en roadmap) |
| Idioma | Solo español |
| Autenticación | Sin login de usuarios (MVP — productivo en roadmap) |
| Limpieza MinIO | Eliminar documento no borra los archivos en MinIO |
| Tests automáticos | Sin suite de pruebas formal aún |
| LLM local | llama.cpp no integrado en flujo activo (reservado Fase 3+) |

### Roadmap

| Fase | Contenido |
|------|-----------|
| **MVP 1** ✅ | Pipeline DOCX completo, LT + OpenAI, frontend básico |
| **MVP 2** ✅ | Perfiles editoriales, prompts parametrizados, análisis editorial, router, quality gates, HITL |
| **Renovación** ✅ | ADN editorial, reglas de sustitución, contexto enriquecido, corrección macro |
| **Structural Awareness** ✅ | B.5 extracción estructural DOCX, D.5 corrección grupal, gates estructurales, árbol de estructura |
| **Fase 3** | PDF born-digital (extracción + corrección + overlay), soporte ODT/RTF |
| **Fase 4** | OCR para PDFs escaneados (Tesseract / Azure OCR) |
| **Fase 5** | Autenticación multi-usuario, métricas por organización, Kubernetes, escalado productivo |
| **Fase 6** | LLM local (llama.cpp), modo offline, modelos fine-tuned para español |

---

## Licencia

MIT

---

*Última actualización: Mayo 2026 — Renovación S0–S5 completada.*
