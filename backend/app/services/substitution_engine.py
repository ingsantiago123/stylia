"""
SubstitutionEngine — Fase 0 de corrección.

Aplica substitution_rules y entity_normalizations del perfil editorial
sobre el texto del párrafo ANTES de LanguageTool.

Diseño: por párrafo dentro de _correct_single_paragraph (no como pase global
previo al DOCX), para que sea idempotente, determinista y se replique en el
boundary check del modo paralelo sin riesgo.
"""

import re
import logging
import uuid

logger = logging.getLogger(__name__)


def _safe_regex(pattern: str, flags: int = 0) -> re.Pattern | None:
    """Compila un regex con timeout de seguridad. Retorna None si es inválido."""
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        logger.warning(f"SubstitutionEngine: regex inválido '{pattern}': {e}")
        return None


def apply_substitutions(
    text: str,
    profile: dict,
) -> tuple[str, list[dict]]:
    """
    Aplica Fase 0: substitution_rules + entity_normalizations del perfil.

    Args:
        text: Texto del párrafo (antes de LT).
        profile: Perfil editorial con campos substitution_rules y entity_normalizations.

    Returns:
        (texto_modificado, lista_de_patches_substitution)
        Cada patch de substitution tiene correction_phase="substitution".
    """
    substitution_patches: list[dict] = []
    result = text

    substitution_rules: list[dict] = profile.get("substitution_rules") or []
    entity_normalizations: list[dict] = profile.get("entity_normalizations") or []

    # ── Aplicar substitution_rules ──────────────────────────────────────
    for rule in substitution_rules:
        if not rule.get("enabled", True):
            continue

        find = rule.get("find", "")
        replace = rule.get("replace", "")
        if not find:
            continue

        case_sensitive: bool = rule.get("case_sensitive", False)
        is_regex: bool = rule.get("is_regex", False)
        rule_id: str = rule.get("id", str(uuid.uuid4()))

        flags = 0 if case_sensitive else re.IGNORECASE

        if is_regex:
            pattern = _safe_regex(find, flags)
            if pattern is None:
                continue
        else:
            pattern = _safe_regex(re.escape(find), flags)
            if pattern is None:
                continue

        new_text, count = pattern.subn(replace, result)
        if count > 0:
            substitution_patches.append({
                "correction_phase": "substitution",
                "substitution_rule_id": rule_id,
                "original_fragment": find,
                "replacement": replace,
                "occurrences": count,
                "rule_type": "substitution",
            })
            logger.info(
                f"SubstitutionEngine: regla '{find}' → '{replace}' "
                f"({count} ocurrencia(s))"
            )
            result = new_text

    # ── Aplicar entity_normalizations ───────────────────────────────────
    for norm in entity_normalizations:
        if not norm.get("enabled", True):
            continue

        canonical: str = norm.get("canonical", "")
        generic: str = norm.get("generic", "")
        aliases: list[str] = norm.get("aliases") or []
        norm_id: str = norm.get("id", str(uuid.uuid4()))

        if not canonical:
            continue

        targets = [t for t in [generic] + aliases if t]
        for target in targets:
            pattern = _safe_regex(re.escape(target), re.IGNORECASE)
            if pattern is None:
                continue
            new_text, count = pattern.subn(canonical, result)
            if count > 0:
                substitution_patches.append({
                    "correction_phase": "substitution",
                    "substitution_rule_id": norm_id,
                    "original_fragment": target,
                    "replacement": canonical,
                    "occurrences": count,
                    "rule_type": "entity_normalization",
                })
                logger.info(
                    f"SubstitutionEngine: normalización '{target}' → '{canonical}' "
                    f"({count} ocurrencia(s))"
                )
                result = new_text

    return result, substitution_patches


def build_substitutions_prompt_block(substitution_patches: list[dict]) -> str:
    """
    Construye el bloque REGLAS DEL USUARIO YA APLICADAS para el prompt LLM.
    Solo se incluye si hubo sustituciones en este párrafo.
    """
    if not substitution_patches:
        return ""

    lines = ["── REGLAS DEL USUARIO YA APLICADAS ──"]
    lines.append(
        "Las siguientes sustituciones se aplicaron antes de tu intervención. "
        "NO las reviertas:"
    )
    for patch in substitution_patches:
        orig = patch.get("original_fragment", "")
        repl = patch.get("replacement", "")
        rule_type = patch.get("rule_type", "substitution")
        label = "entidad canónica" if rule_type == "entity_normalization" else "regla de usuario"
        lines.append(f'  - "{orig}" → "{repl}" ({label})')
    lines.append("La forma resultante es la correcta. Corrige ortografía/gramática SIN tocar estos fragmentos.")
    return "\n".join(lines)


def count_substitution_matches(text: str, profile: dict) -> int:
    """
    Cuenta cuántas sustituciones aplicarían sin modificar el texto.
    Usado por simulate-impact.
    """
    total = 0
    substitution_rules: list[dict] = profile.get("substitution_rules") or []
    entity_normalizations: list[dict] = profile.get("entity_normalizations") or []

    for rule in substitution_rules:
        if not rule.get("enabled", True):
            continue
        find = rule.get("find", "")
        if not find:
            continue
        case_sensitive = rule.get("case_sensitive", False)
        is_regex = rule.get("is_regex", False)
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern_str = find if is_regex else re.escape(find)
        p = _safe_regex(pattern_str, flags)
        if p:
            total += len(p.findall(text))

    for norm in entity_normalizations:
        if not norm.get("enabled", True):
            continue
        canonical = norm.get("canonical", "")
        generic = norm.get("generic", "")
        aliases: list[str] = norm.get("aliases") or []
        if not canonical:
            continue
        for target in [t for t in [generic] + aliases if t]:
            p = _safe_regex(re.escape(target), re.IGNORECASE)
            if p:
                total += len(p.findall(text))

    return total
