"""
Tests unitarios para quality_gates.py.
Verifica que los gates críticos y no-críticos funcionen correctamente.
"""

import pytest
from app.services.quality_gates import (
    gate_not_empty,
    gate_expansion_ratio,
    gate_rewrite_ratio,
    gate_protected_terms,
    gate_language_preserved,
    validate_correction,
)


# ── gate_not_empty ───────────────────────────────────────────────────

def test_gate_not_empty_passes_with_text():
    result = gate_not_empty("Texto corregido válido.")
    assert result.passed is True
    assert result.critical is True


def test_gate_not_empty_fails_with_empty():
    result = gate_not_empty("")
    assert result.passed is False
    assert result.critical is True


def test_gate_not_empty_fails_with_whitespace():
    result = gate_not_empty("   \n\t  ")
    assert result.passed is False


# ── gate_expansion_ratio ─────────────────────────────────────────────

def test_gate_expansion_ratio_passes():
    original = "Texto con diez palabras exactamente aquí."
    # Solo añadir 1 char — ratio 1.025, bien por debajo de 1.15
    corrected = "Texto con diez palabras exactamente aquí."
    result = gate_expansion_ratio(original, corrected, max_ratio=1.15)
    assert result.passed is True


def test_gate_expansion_ratio_fails():
    original = "Texto corto."
    corrected = "Texto mucho más largo con muchas palabras adicionales innecesarias."
    result = gate_expansion_ratio(original, corrected, max_ratio=1.15)
    assert result.passed is False
    assert result.critical is True


def test_gate_expansion_ratio_handles_empty_original():
    result = gate_expansion_ratio("", "algo", max_ratio=1.15)
    assert result.passed is True  # no aplica si original vacío


# ── gate_rewrite_ratio ───────────────────────────────────────────────

def test_gate_rewrite_ratio_passes_minor_change():
    original = "El gato come ratones silenciosamente."
    corrected = "El gato come ratones con sigilo."
    result = gate_rewrite_ratio(original, corrected, max_ratio=0.40)
    assert result.passed is True


def test_gate_rewrite_ratio_fails_major_rewrite():
    original = "El cielo es azul."
    corrected = "La cúpula celeste exhibe una tonalidad añil intensa."
    result = gate_rewrite_ratio(original, corrected, max_ratio=0.35)
    assert result.passed is False
    assert result.critical is False  # no-crítico


# ── gate_protected_terms ─────────────────────────────────────────────

def test_gate_protected_terms_passes_when_all_present():
    original = "El sistema STYLIA procesa documentos."
    corrected = "STYLIA procesa documentos editoriales."
    result = gate_protected_terms(original, corrected, ["STYLIA"])
    assert result.passed is True


def test_gate_protected_terms_fails_when_term_removed():
    original = "El sistema STYLIA procesa documentos."
    corrected = "El sistema procesa documentos editoriales."
    result = gate_protected_terms(original, corrected, ["STYLIA"])
    assert result.passed is False
    assert result.critical is True


def test_gate_protected_terms_passes_when_no_terms():
    result = gate_protected_terms("original", "corrected", [])
    assert result.passed is True


def test_gate_protected_terms_ignores_terms_not_in_original():
    original = "Texto sin el término especial."
    corrected = "Texto sin el concepto especial."
    result = gate_protected_terms(original, corrected, ["STYLIA"])
    assert result.passed is True  # STYLIA no estaba en original


# ── gate_language_preserved ─────────────────────────────────────────

def test_gate_language_preserved_passes_spanish():
    original = "La implementación de las metodologías propuestas contribuirá."
    corrected = "La implementación metodológica propuesta contribuirá significativamente."
    result = gate_language_preserved(original, corrected)
    assert result.passed is True


def test_gate_language_preserved_fails_on_language_change():
    original = "La implementación de las metodologías españolas es importante."
    corrected = "The implementation of the methodologies is important."
    result = gate_language_preserved(original, corrected)
    assert result.passed is False


# ── validate_correction (integración de gates) ──────────────────────

def test_validate_correction_all_pass():
    original = "El texto tiene algunos errores de estilo que deben corregirse."
    corrected = "El texto tiene algunos problemas de estilo que deben mejorarse."
    gates = validate_correction(original, corrected)
    # Debería haber al menos 4 gates
    assert len(gates) >= 4
    critical_fails = [g for g in gates if not g.passed and g.critical]
    assert len(critical_fails) == 0


def test_validate_correction_critical_fail_on_empty():
    original = "Texto original válido."
    corrected = ""
    gates = validate_correction(original, corrected)
    critical_fails = [g for g in gates if not g.passed and g.critical]
    assert len(critical_fails) > 0


def test_validate_correction_no_1_05_expansion_for_tables():
    """Regression: la expansión 1.05 para celda_tabla fue eliminada — no debe rechazar."""
    original = "Calif."  # 6 chars
    corrected = "Calificación"  # 12 chars — ratio 2.0, pero max_expansion default es 1.15
    profile = {"max_expansion_ratio": 1.15}
    gates = validate_correction(original, corrected, profile=profile, paragraph_type="celda_tabla")
    # El gate de expansión debería fallar por ratio 2.0, pero NO por una regla especial de 1.05
    expansion_gate = next((g for g in gates if g.gate_name == "expansion_ratio"), None)
    assert expansion_gate is not None
    # El umbral debe ser 1.15 (el del perfil), no 1.05
    assert expansion_gate.threshold == 1.15
