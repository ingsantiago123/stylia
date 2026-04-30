# INFORME DE MEJORA (MVP2)

Fecha: 2026-03-26
Alcance auditado: backend, frontend, documentacion funcional MVP2
Criterio: solo hallazgos comprobados en codigo/documentacion actual, sin inferencias.

## 1) Hallazgos criticos

### 1.1 Mapeo incorrecto de parches a bloques (trazabilidad rota)
- Severidad: Critico
- Evidencia:
  - backend/app/workers/tasks_pipeline.py:363
  - backend/app/workers/tasks_pipeline.py:367
- Hecho comprobado:
  - En persistencia de patches DOCX se usa explicitamente "el primero de la primera pagina" para asociar parches, en lugar de mapear cada parche a su bloque real.
- Impacto:
  - Correcciones pueden quedar asociadas al bloque equivocado.
  - Conteo por pagina/bloque y trazabilidad de cambios quedan distorsionados.
  - Riesgo de UX inconsistente en vistas de correcciones y analitica.
- Recomendacion:
  - Reemplazar la asociacion fija por mapeo determinista (por paragraph_index + texto normalizado + fallback estable).

### 1.2 API de analisis no expone clasificacion de parrafos producida por Etapa C
- Severidad: Critico
- Evidencia:
  - backend/app/services/analysis.py:622
  - backend/app/api/v1/documents.py:837
- Hecho comprobado:
  - El servicio de analisis construye paragraph_classifications.
  - El endpoint /documents/{doc_id}/analysis devuelve paragraph_classifications vacio de forma fija.
- Impacto:
  - Frontend/consumidores no reciben salida completa de Etapa C.
  - Se rompe la validacion de MVP2 sobre clasificacion editorial.
- Recomendacion:
  - Persistir y/o reconstruir paragraph_classifications en la respuesta del endpoint para devolver datos reales.

## 2) Hallazgos altos

### 2.1 Inconsistencia de etapas de pipeline entre componentes UI
- Severidad: Alto
- Evidencia:
  - frontend/src/components/DocumentList.tsx:12
- Hecho comprobado:
  - PIPELINE_STAGES en DocumentList omite la etapa analyzing.
- Impacto:
  - Barra mini de progreso no representa el flujo real MVP2 cuando documento esta en analyzing.
- Recomendacion:
  - Incluir analyzing en la secuencia de etapas para alinear la UI con estados backend.

### 2.2 Dashboard de costos clasifica llamadas con etiqueta legacy (MVP1/MVP2) incompatible con router actual
- Severidad: Alto
- Evidencia:
  - frontend/src/app/costs/page.tsx:682
  - backend/app/services/correction.py:338
- Hecho comprobado:
  - Frontend interpreta tipo por igualdad exacta a correction_mvp2.
  - Backend genera call_type dinamico correction_{route_taken} (ej. correction_editorial, correction_cheap, correction_skip).
- Impacto:
  - Etiquetado visual y colorizacion de costos puede ser incorrecto.
  - Lectura de metricas por tipo de llamada queda sesgada.
- Recomendacion:
  - Normalizar etiqueta por prefijo/sufijo o tabla de mapeo de rutas (skip/cheap/editorial).

## 3) Hallazgos medios

### 3.1 Desacople historico entre tipos de correccion y componente de comparacion
- Severidad: Medio
- Evidencia:
  - frontend/src/components/DiffCompareView.tsx:116
  - frontend/src/lib/api.ts:231
  - frontend/src/lib/api.ts:232
- Hecho comprobado:
  - El comparador usa original_snippet/corrected_snippet para vincular anotaciones.
  - Las propiedades existen en el contrato de anotaciones del cliente API.
- Impacto:
  - No se detecta fallo de compilacion directo en este punto, pero es una zona de acoplamiento sensible entre correcciones y anotaciones.
- Recomendacion:
  - Mantener contrato explicito y pruebas de integracion API-UI para evitar regresiones en matching de tooltips.

## 4) Hallazgo de desalineacion arquitectura/documentacion

### 4.1 Diferencia entre objetivo de LLM local y estado de implementacion actual
- Severidad: Medio
- Evidencia:
  - agents.md:133
  - agents.md:134
  - backend/app/utils/openai_client.py:10
- Hecho comprobado:
  - Documentacion maestra describe LLM local (llama.cpp + Qwen).
  - Implementacion activa usa cliente OpenAI.
- Impacto:
  - Divergencia entre expectativa de arquitectura y operacion real del sistema.
- Recomendacion:
  - Definir oficialmente estado transitorio (OpenAI) o plan de migracion a local LLM y actualizar docs de estado.

## 5) Matriz de cumplimiento MVP2 (estado actual observado)

- Etapa C (analisis editorial): Parcial
  - Motivo: produce clasificaciones, pero API publica no las entrega.
- Etapa D (router de complejidad): Parcial
  - Motivo: backend genera call_type por ruta, pero frontend de costos no interpreta correctamente ese esquema.
- Trazabilidad de correcciones por bloque/pagina: Parcial/Deficiente
  - Motivo: asociacion de parches a bloque no corresponde de forma confiable en Ruta 1.
- Representacion de pipeline en UI: Parcial
  - Motivo: mini pipeline sin etapa analyzing.

## 6) Prioridad recomendada de correccion

1. Corregir asociacion patch -> block en pipeline (Critico).
2. Exponer paragraph_classifications reales en endpoint de analisis (Critico).
3. Alinear costos frontend con call_type por ruta (Alto).
4. Alinear mini pipeline UI con etapa analyzing (Alto).
5. Resolver/explicitar gap doc-arquitectura LLM local vs OpenAI (Medio).

## 7) Nota metodologica

Este informe incluye unicamente observaciones verificadas contra archivos actuales del workspace y referencias concretas de ubicacion.
