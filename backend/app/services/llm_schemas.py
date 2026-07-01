"""
Schemas JSON estrictos para Structured Outputs (Fase 5 del plan,
DIAGNOSTICO_STYLIA.md §2.6.1).

Antes el contrato de salida era texto en el system prompt + json_object:
cualquier desviación del modelo producía un JSON inválido que se
interpretaba silenciosamente como "no corregir". Con json_schema strict
la API GARANTIZA la forma de la respuesta.

Reglas de strict mode (OpenAI):
  - additionalProperties: false en todos los objetos
  - todos los campos en required (los opcionales se modelan como nullables
    con "type": [X, "null"])
"""

_CHANGE_SCHEMA = {
    "type": "object",
    "properties": {
        "original_fragment": {"type": "string"},
        "corrected_fragment": {"type": "string"},
        "category": {
            "type": "string",
            "enum": [
                "redundancia", "claridad", "registro", "cohesion",
                "lexico", "estructura", "puntuacion", "ritmo",
                "muletilla", "sustitución", "ortografia",
            ],
        },
        "severity": {"type": "string", "enum": ["critico", "importante", "sugerencia"]},
        "explanation": {"type": "string"},
    },
    "required": [
        "original_fragment", "corrected_fragment", "category",
        "severity", "explanation",
    ],
    "additionalProperties": False,
}

# ── Corrección individual de párrafo ──
INDIVIDUAL_CORRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["correct", "flag", "skip"]},
        "corrected_text": {"type": "string"},
        "changes": {"type": "array", "items": _CHANGE_SCHEMA},
        "confidence": {"type": ["number", "null"]},
        "rewrite_ratio": {"type": ["number", "null"]},
    },
    "required": ["action", "corrected_text", "changes", "confidence", "rewrite_ratio"],
    "additionalProperties": False,
}

# ── Corrección grupal (lista o tabla): array de ítems indexados ──
GROUP_CORRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "action": {"type": "string", "enum": ["correct", "flag", "skip"]},
                    "corrected_text": {"type": "string"},
                    "changes": {"type": "array", "items": _CHANGE_SCHEMA},
                    "confidence": {"type": ["number", "null"]},
                    "rewrite_ratio": {"type": ["number", "null"]},
                },
                "required": [
                    "index", "action", "corrected_text", "changes",
                    "confidence", "rewrite_ratio",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

# ── Auditoría contextual (Pasada 2) ──
AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "final_text": {"type": "string"},
        "reverted_destructions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original_term": {"type": "string"},
                    "pass1_changed_to": {"type": "string"},
                    "reason": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critico", "importante", "sugerencia"]},
                },
                "required": ["original_term", "pass1_changed_to", "reason", "severity"],
                "additionalProperties": False,
            },
        },
        "style_improvements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original_fragment": {"type": "string"},
                    "improved_fragment": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["claridad", "registro", "cohesion", "lexico", "ritmo"],
                    },
                    "explanation": {"type": "string"},
                },
                "required": ["original_fragment", "improved_fragment", "category", "explanation"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": ["number", "null"]},
        "pass1_quality": {"type": "string", "enum": ["ok", "minor_issues", "major_issues"]},
    },
    "required": ["final_text", "reverted_destructions", "style_improvements", "confidence", "pass1_quality"],
    "additionalProperties": False,
}
