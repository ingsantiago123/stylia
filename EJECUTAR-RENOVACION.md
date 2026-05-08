# Prompt de ejecución — Renovación arquitectónica STYLIA

> **Cómo usar este archivo:** abre Claude Code en el directorio del proyecto y copia el bloque "PROMPT PARA CLAUDE" de abajo como primer mensaje. Claude leerá el plan y comenzará Sprint 0. NO está en modo plan: está en modo ejecución, sprint por sprint, esperando tu confirmación entre cada uno.

---

## Estado actual

- **Plan completo y aprobado:** [C:/Users/USER/.claude/plans/prompt-maestro-compiled-seahorse.md](C:/Users/USER/.claude/plans/prompt-maestro-compiled-seahorse.md)
- **Diagnóstico verificado en código:** 7 problemas del prompt original confirmados + 4 problemas adicionales (P8-P11) detectados en exploración.
- **Sprints definidos:** S0 → S1 → S2 → S3 → S4 → S5.
- **Decisiones de alcance del usuario:**
  - Plan completo, sprints priorizados (no "todo en un PR").
  - Idiolect protections: solo input manual del usuario.
  - Macro-corrección: opt-in (default `none`), sprint final.
  - Compatibilidad obligatoria con flujo paralelo por lotes (documentos grandes).

---

## PROMPT PARA CLAUDE

Copia desde aquí 👇

````
Voy a ejecutar la renovación arquitectónica de STYLIA. El plan completo y validado
está en C:/Users/USER/.claude/plans/prompt-maestro-compiled-seahorse.md.

INSTRUCCIONES DE EJECUCIÓN:

1. Lee el plan COMPLETO antes de empezar. Identifica los 6 sprints (S0..S5).

2. Trabaja sprint por sprint. NO mezcles sprints. Tras terminar cada sprint:
   - Resume qué se modificó (archivos, líneas, migraciones).
   - Corre las suites de prueba A (monolítico) y B (paralelo) descritas en
     la sección 7.8 del plan.
   - Pide confirmación antes de pasar al siguiente sprint.

3. Reglas estrictas (no las violes nunca):
   - Migraciones: SOLO `ALTER TABLE IF NOT EXISTS ADD COLUMN`. Nunca DROP.
   - Schemas Pydantic: campos nuevos con `default_factory=list` para JSONB.
   - Endpoints existentes: NO cambiar firmas; solo agregar nuevos.
   - Paridad funcional: cada cambio en `_correct_single_paragraph` debe
     verificarse en monolítico Y paralelo (sección 7.10 del plan).
   - Documentos legacy (sin nuevos campos en perfil): el sistema debe correr
     idéntico al MVP 2 actual. Test específico de regresión.
   - Validar antes de cerrar sprint: `docker-compose up --build` levanta
     limpio y los tests existentes pasan.

4. Acuerdos del usuario que NO debes recontestar:
   - Idiolect protections solo manuales (no detección automática).
   - Macro-corrección como pase post-merge (no por lote) — sección 7.10 del plan.
   - macro_correction_level por defecto `none`.
   - Substitution_rules se aplican por párrafo dentro de
     `_correct_single_paragraph`, no como pase global previo al DOCX.

5. Sprints en orden:

   S0 — Migración BD (document_profiles + patches) + schemas Pydantic +
        actualizar 10 presets en data/profiles.py + tipos TS en api.ts.
        Riesgo: bajo. Complejidad: pequeño. Sin lógica nueva.

   S1 — Wiring de DocumentGlobalContext.protected_globals_json:
        - correction.py:273-278: pasar `term_registry` a engine_router.decide_engines
        - protected_regions.detect_protected_regions: aceptar global_protected_terms
        - prompt_builder.build_user_prompt: inyectar build_global_context_block en
          Pasada 1 (no solo en Pasada 2).
        Test crítico: doc con "STYLIA" y "tokenización" en lotes distintos
        no producen "ITALIA"/"colonización". Riesgo: bajo. Alta relación valor/esfuerzo.

   S2 — Reglas personalizadas:
        - Crear backend/app/services/substitution_engine.py
        - Fase 0 dentro de _correct_single_paragraph antes de LT
        - prompt_builder: bloques REGLAS DEL USUARIO YA APLICADAS,
          RESTRICCIONES DE REGISTRO, IDIOLECTOS PROTEGIDOS
        - audit_pass.audit_paragraph_with_context: aceptar profile completo
        - AUDIT_SYSTEM_PROMPT: agregar reglas 7-9 (prompt_builder)
        - Endpoints: GET/PATCH /editorial-profile, POST/DELETE rules,
          POST simulate-impact
        - Quality gate post-corrección para register_constraints (heurística).
        Riesgo: medio. Complejidad: grande.

   S3 — Contexto enriquecido + ADN en P1:
        - Ampliar ventana corrected_context de 1 a N (configurable, default 5)
        - corrected_meta como list[dict] tipada (texto, tipo, registro local)
        - En modo paralelo: pasar context_seed_window (lista N) en vez de
          context_seed (string) en correct_batch_llm
        - prompt_builder: build_user_prompt acepta varios párrafos previos.
        Riesgo: medio. Complejidad: mediano.

   S4 — Frontend (Editorial Profile Panel):
        - lib/api.ts: tipos EditorialProfile, SubstitutionRule, etc. + funciones
        - app/page.tsx: paso 4 "Revisar Ficha Editorial" antes de procesar
        - components/EditorialProfilePanel.tsx (nuevo)
        - components/SubstitutionRulesEditor.tsx (nuevo)
        - components/IdiolectProtectionsEditor.tsx (nuevo)
        - components/RegisterConstraintsSelector.tsx (nuevo)
        - components/ImpactEstimatePanel.tsx (nuevo)
        - components/AnalysisView.tsx: exponer ADN editorial completo.
        Paleta carbon/krypton/bruma/plomo, dark-only, SVG inline.
        Riesgo: medio. Complejidad: grande.

   S5 — Macro-corrección post-merge (opt-in):
        - Crear backend/app/services/macro_correction.py
        - Crear tarea Celery correct_macro_pass encadenada al chord
        - prompt_builder.build_macro_correction_prompt
        - complexity_router: rutas SKIP/MICRO/MICRO+MACRO/MACRO_ONLY
        - components/MacroCorrectionView.tsx: badges por correction_phase
        - Endpoint: POST /documents/{id}/recorrect-macro
        - Opcional: mejora de _apply_text_with_page_break (P7).
        Riesgo: alto. Complejidad: grande. Solo arrancar tras S0-S4 en producción.

6. Tras cada sprint:
   - Crea un commit con prefijo `feat(renov-Sx): <descripción>`.
   - Actualiza CLAUDE.md si hay cambios estructurales.
   - Actualiza REGISTRO-MVP2.md (o crea REGISTRO-RENOV.md) con qué quedó hecho.
   - Pregúntame: "Sprint Sx terminado y verificado. ¿Continúo con S(x+1)?"

7. Si encuentras una decisión ambigua, pregúntame con AskUserQuestion antes
   de improvisar. Las decisiones tomadas en el plan no se reabren.

EMPIEZA POR LEER EL PLAN COMPLETO. Luego dame un resumen de 10 líneas de
qué entendiste y arranca Sprint S0.
````

Hasta aquí 👆

---

## Material de referencia (NO copies este bloque al prompt)

- Plan validado: `C:/Users/USER/.claude/plans/prompt-maestro-compiled-seahorse.md`
- CLAUDE.md del proyecto: `c:/Users/USER/Desktop/corrector de estilos/CLAUDE.md`
- Documentación MVP2: `mvp2.md`, `IMPLEMENTACION-MVP2.md`, `REGISTRO-MVP2.md`, `CLAUDE-LOGIC.md`

## Comandos útiles para validar manualmente entre sprints

```bash
# Levantar stack y verificar que arranca limpio
docker-compose up --build

# Ver logs de migración
docker logs corrector-de-estilos-backend-1 --tail 100

# Validar que la BD migró
docker exec -it corrector-de-estilos-postgres-1 psql -U stylecorrector \
  -d stylecorrector -c "\d document_profiles"

# Forzar modo paralelo en .env (test de Suite B)
# parallel_correction_enabled=True
# parallel_correction_batch_size=80

# Test e2e: subir, procesar, descargar
# Frontend: http://localhost:3000
```

## Checklist de inicio de cada sprint

- [ ] He leído la sección 7.X del plan correspondiente al sprint.
- [ ] Tengo claros los archivos a modificar (sección "Archivos críticos").
- [ ] Tengo claros los tests obligatorios (Suite A monolítico + Suite B paralelo).
- [ ] No voy a tocar archivos fuera del scope del sprint salvo wiring necesario.
- [ ] Los acuerdos del usuario están internalizados (no se reabren).

## Checklist de cierre de cada sprint

- [ ] Migraciones (si las hay) corren idempotentemente (lanzar dos veces).
- [ ] Suite A pasa (monolítico).
- [ ] Suite B pasa (paralelo).
- [ ] Test de retrocompatibilidad: documento legacy sin nuevos campos corre idéntico.
- [ ] CLAUDE.md actualizado con cambios estructurales.
- [ ] Commit creado.
- [ ] Resumen entregado al usuario y confirmación pedida antes de avanzar.
