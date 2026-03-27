"""
Quality Gates — Validación post-corrección (MVP2 Lote 5).

Cada gate recibe texto original + corregido + parámetros del perfil,
y retorna un GateResult indicando si pasó o falló.

Gates críticos (fallan → descartar corrección):
  - expansion_ratio: texto no debe expandirse más de max_expansion_ratio
  - protected_terms: términos protegidos deben mantenerse
  - not_empty: texto corregido no puede estar vacío

Gates no-críticos (fallan → marcar para revisión manual):
  - rewrite_ratio: distancia de edición no debe superar max_rewrite_ratio
  - language_preserved: idioma del texto no debe cambiar
  - readability_inflesz: legibilidad INFLESZ dentro del rango objetivo
"""

import logging
import re
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Resultado de un quality gate."""
    passed: bool
    gate_name: str
    value: float
    threshold: float
    message: str
    critical: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# =====================================================================
# GATES INDIVIDUALES
# =====================================================================

def gate_not_empty(corrected: str) -> GateResult:
    """El texto corregido no debe estar vacío."""
    is_empty = not corrected or not corrected.strip()
    return GateResult(
        passed=not is_empty,
        gate_name="not_empty",
        value=0.0 if is_empty else 1.0,
        threshold=1.0,
        message="" if not is_empty else "Texto corregido está vacío",
        critical=True,
    )


def gate_expansion_ratio(original: str, corrected: str, max_ratio: float = 1.15) -> GateResult:
    """len(corrected) / len(original) <= max_ratio"""
    orig_len = len(original)
    corr_len = len(corrected)
    if orig_len == 0:
        return GateResult(
            passed=True, gate_name="expansion_ratio",
            value=0.0, threshold=max_ratio,
            message="Original vacío, gate no aplica",
            critical=True,
        )
    ratio = corr_len / orig_len
    passed = ratio <= max_ratio
    return GateResult(
        passed=passed,
        gate_name="expansion_ratio",
        value=round(ratio, 4),
        threshold=max_ratio,
        message="" if passed else f"Expansión {ratio:.1%} excede máximo {max_ratio:.0%}",
        critical=True,
    )


def gate_rewrite_ratio(original: str, corrected: str, max_ratio: float = 0.35) -> GateResult:
    """Distancia de edición normalizada <= max_ratio.
    Usa SequenceMatcher de difflib (stdlib, sin dependencias).
    """
    if not original or not corrected:
        return GateResult(
            passed=True, gate_name="rewrite_ratio",
            value=0.0, threshold=max_ratio,
            message="Texto vacío, gate no aplica",
        )
    similarity = SequenceMatcher(None, original, corrected).ratio()
    rewrite = round(1.0 - similarity, 4)
    passed = rewrite <= max_ratio
    return GateResult(
        passed=passed,
        gate_name="rewrite_ratio",
        value=rewrite,
        threshold=max_ratio,
        message="" if passed else f"Reescritura {rewrite:.1%} excede máximo {max_ratio:.0%}",
    )


def gate_protected_terms(
    original: str, corrected: str, terms: list[str]
) -> GateResult:
    """Todos los protected_terms presentes en original deben estar en corrected."""
    if not terms:
        return GateResult(
            passed=True, gate_name="protected_terms",
            value=1.0, threshold=1.0,
            message="Sin términos protegidos",
            critical=True,
        )

    original_lower = original.lower()
    corrected_lower = corrected.lower()
    missing = []
    checked = 0
    for term in terms:
        t = term.lower().strip()
        if not t:
            continue
        # Solo validar si el término estaba en el original
        if t in original_lower:
            checked += 1
            if t not in corrected_lower:
                missing.append(term)

    if checked == 0:
        return GateResult(
            passed=True, gate_name="protected_terms",
            value=1.0, threshold=1.0,
            message="Ningún término protegido presente en el original",
            critical=True,
        )

    preserved_ratio = (checked - len(missing)) / checked
    passed = len(missing) == 0
    return GateResult(
        passed=passed,
        gate_name="protected_terms",
        value=round(preserved_ratio, 4),
        threshold=1.0,
        message="" if passed else f"Términos protegidos eliminados: {', '.join(missing)}",
        critical=True,
    )


def gate_language_preserved(original: str, corrected: str) -> GateResult:
    """Heurístico rápido: el idioma del texto no debe cambiar.
    Compara proporción de caracteres ASCII vs Unicode en original y corregido.
    Si el original tiene muchos acentos/ñ (español) y el corregido no, falló.
    """
    def spanish_char_ratio(text: str) -> float:
        if not text:
            return 0.0
        spanish_chars = len(re.findall(r'[áéíóúüñÁÉÍÓÚÜÑ¿¡]', text))
        return spanish_chars / max(len(text), 1)

    orig_ratio = spanish_char_ratio(original)
    corr_ratio = spanish_char_ratio(corrected)

    # Si el original tiene caracteres españoles pero el corregido perdió >80%, flag
    if orig_ratio > 0.005:
        preservation = corr_ratio / orig_ratio if orig_ratio > 0 else 1.0
        passed = preservation >= 0.2  # muy permisivo — solo detecta cambios de idioma drásticos
    else:
        passed = True
        preservation = 1.0

    return GateResult(
        passed=passed,
        gate_name="language_preserved",
        value=round(preservation, 4),
        threshold=0.2,
        message="" if passed else "Posible cambio de idioma detectado",
    )


# =====================================================================
# INFLESZ — Legibilidad en español (Fernández Huerta)
# =====================================================================

def _count_syllables_spanish(word: str) -> int:
    """Cuenta sílabas en una palabra española (heurístico).
    Basado en reglas básicas de división silábica del español.
    """
    word = word.lower().strip()
    if not word:
        return 0

    vowels = set("aeiouáéíóúüy")
    count = 0
    prev_is_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    return max(count, 1)


def _count_sentences(text: str) -> int:
    """Cuenta oraciones en un texto."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    return max(len(sentences), 1)


def _count_words(text: str) -> int:
    """Cuenta palabras en un texto."""
    words = re.findall(r'\b\w+\b', text)
    return max(len(words), 1)


def compute_inflesz(text: str) -> float:
    """Calcula el índice INFLESZ (Fernández Huerta) para texto en español.

    Fórmula: INFLESZ = 206.84 - 60 * (sílabas/palabras) - 1.02 * (palabras/oraciones)

    Escala:
      > 80: Muy fácil
      60-80: Fácil
      40-60: Normal
      20-40: Difícil
      < 20: Muy difícil
    """
    if not text or len(text.strip()) < 10:
        return 0.0

    words = re.findall(r'\b\w+\b', text)
    n_words = len(words)
    if n_words == 0:
        return 0.0

    n_syllables = sum(_count_syllables_spanish(w) for w in words)
    n_sentences = _count_sentences(text)

    score = 206.84 - 60 * (n_syllables / n_words) - 1.02 * (n_words / n_sentences)
    return round(score, 2)


def gate_readability_inflesz(
    corrected: str,
    target_min: int | None = None,
    target_max: int | None = None,
) -> GateResult:
    """Verifica que el INFLESZ del texto corregido esté en el rango objetivo."""
    score = compute_inflesz(corrected)

    if target_min is None and target_max is None:
        return GateResult(
            passed=True,
            gate_name="readability_inflesz",
            value=score,
            threshold=0.0,
            message=f"INFLESZ={score:.1f} (sin rango objetivo)",
        )

    t_min = target_min if target_min is not None else -999
    t_max = target_max if target_max is not None else 999
    passed = t_min <= score <= t_max

    return GateResult(
        passed=passed,
        gate_name="readability_inflesz",
        value=score,
        threshold=t_min,
        message="" if passed else f"INFLESZ={score:.1f} fuera de rango [{t_min}, {t_max}]",
    )


# =====================================================================
# ORQUESTADOR
# =====================================================================

def validate_correction(
    original: str,
    corrected: str,
    profile: dict | None = None,
    protected_terms: list[str] | None = None,
) -> list[GateResult]:
    """
    Ejecuta todos los quality gates sobre una corrección.
    Retorna lista de resultados. Si alguno crítico falla → descartar.
    """
    profile = profile or {}
    max_expansion = profile.get("max_expansion_ratio", 1.15)
    max_rewrite = profile.get("max_rewrite_ratio", 0.35)
    terms = protected_terms or profile.get("protected_terms", [])
    target_min = profile.get("target_inflesz_min")
    target_max = profile.get("target_inflesz_max")

    gates = [
        gate_not_empty(corrected),
        gate_expansion_ratio(original, corrected, max_expansion),
        gate_rewrite_ratio(original, corrected, max_rewrite),
        gate_protected_terms(original, corrected, terms),
        gate_language_preserved(original, corrected),
    ]

    # INFLESZ solo si hay rango objetivo en el perfil
    if target_min is not None or target_max is not None:
        gates.append(gate_readability_inflesz(corrected, target_min, target_max))

    return gates
