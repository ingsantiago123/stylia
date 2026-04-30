# Validación Fase 1 — Human-in-the-Loop (HITL)

## Estado: EN PROGRESO (90% completado)

## Lo que ya se validó exitosamente

1. **Columnas BD**: `reviewed_at`, `reviewer_note`, `decision_source` agregadas a tabla `patches` via ALTER TABLE
2. **Pipeline completo**: Documento subió → convirtió → extrajo → analizó → corrigió → **se detuvo en `pending_review`** ✅
3. **Review summary**: `GET /documents/{id}/review-summary` funciona (retorna conteo por status)
4. **Listar correcciones**: `GET /documents/{id}/corrections` retorna patches con gate_results
5. **Aceptar patch individual**: `PATCH /documents/{id}/corrections/{patch_id}` con `{"action":"accepted"}` funciona ✅
6. **Tarea Celery registrada**: `render_approved_patches` aparece en lista de tasks del worker

## Documento de prueba

- **Doc ID**: `7e790192-f664-49c3-b53a-17dc7097b840`
- **Archivo**: `test_review.docx` (3 párrafos con errores ortográficos)
- **Estado actual**: `pending_review`
- **Patches**: 3 (todos `gate_rejected` por bug en `protected_terms` gate — trata palabras mal escritas como términos protegidos)
- **Patch ya aceptado**: `e15bdf3b-9b6c-4e9c-9061-6d8f24aa0ee8` → status cambiado a `accepted`
- **Patches pendientes de aceptar**: 
  - `b92b05f9-881e-4c7b-bb31-9d0707f62ec6`
  - `39c80326-69c8-4de5-9e20-b921c4044473`

## Lo que falta probar (SIN costo de API/LLM)

Todas estas pruebas son solo llamadas locales al backend, no gastan tokens OpenAI:

### 1. Bulk accept (los 2 patches restantes)
```bash
DOC_ID="7e790192-f664-49c3-b53a-17dc7097b840"
curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/corrections/bulk-action" \
  -H "Content-Type: application/json" \
  -d "{\"patch_ids\": [\"b92b05f9-881e-4c7b-bb31-9d0707f62ec6\", \"39c80326-69c8-4de5-9e20-b921c4044473\"], \"action\": \"accepted\"}"
```

### 2. Verificar review-summary actualizado
```bash
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/review-summary"
# Esperado: accepted=3, can_finalize=true
```

### 3. Finalize (lanza rendering con patches aceptados)
```bash
curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/finalize" \
  -H "Content-Type: application/json" \
  -d "{\"apply_mode\": \"accepted_only\"}"
# Esperado: task_id del Celery task render_approved_patches
```

### 4. Verificar que el documento llegó a `completed`
```bash
# Esperar ~10s y consultar
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID" | python -c "import sys,json; d=json.load(sys.stdin); print(d['status'])"
# Esperado: completed
```

### 5. Descargar documento corregido
```bash
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID/download/docx" -o corrected.docx
# Verificar que solo tiene los patches aceptados aplicados
```

### 6. Probar frontend
- Abrir http://localhost:3000
- Navegar al documento en `pending_review`
- Verificar que se muestra el toolbar de revisión
- Verificar que aparece la etapa "Revisión" en el PipelineFlow

## Bug encontrado (para próxima fase)

**Gate `protected_terms` tiene falso positivo**: Cuando un término original tiene error ortográfico (ej: "herrores"), el gate lo detecta como "término protegido eliminado" porque la corrección cambia "herrores" → "errores". Esto causa que todas las correcciones ortográficas sean `gate_rejected`. **Fix**: El gate debería comparar solo contra la lista explícita de `protected_terms` del perfil, no contra todas las palabras del texto original.

## Archivos modificados en Fase 1

| Archivo | Cambio |
|---------|--------|
| `backend/app/models/document.py` | Status comment actualizado con `pending_review` |
| `backend/app/models/patch.py` | +3 columnas: reviewed_at, reviewer_note, decision_source |
| `backend/app/schemas/patch.py` | +4 schemas: PatchReviewAction, BulkPatchReviewAction, FinalizeRequest, ReviewSummary |
| `backend/app/api/v1/documents.py` | +4 endpoints: review-summary, PATCH correction, bulk-action, finalize |
| `backend/app/services/rendering.py` | +apply_mode param con filtro por review_status |
| `backend/app/workers/tasks_pipeline.py` | Split _run_stage_e → _persist_patches + _run_stage_e; nuevo task render_approved_patches |
| `backend/app/workers/celery_app.py` | Ruta para render_approved_patches |
| `frontend/src/lib/api.ts` | +4 funciones: getReviewSummary, reviewCorrection, bulkReviewCorrections, finalizeDocument |
| `frontend/src/components/CorrectionHistory.tsx` | ReviewToolbar, checkboxes, accept/reject buttons |
| `frontend/src/components/PipelineFlow.tsx` | Etapa pending_review agregada |
| `frontend/src/components/DocumentList.tsx` | Status pending_review en config |
| `frontend/src/app/documents/[id]/page.tsx` | reviewSummary state + props a CorrectionHistory |
| `frontend/src/app/page.tsx` | Excluir pending_review de "en proceso" |
