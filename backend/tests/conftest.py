"""
Fixtures compartidas para tests.
"""

import pytest


@pytest.fixture
def sample_profile():
    """Perfil editorial básico para tests."""
    return {
        "register": "formal",
        "intervention_level": "moderada",
        "audience_type": "general",
        "audience_expertise": "medio",
        "tone": "neutro",
        "preserve_author_voice": True,
        "max_rewrite_ratio": 0.30,
        "max_expansion_ratio": 1.15,
        "style_priorities": ["claridad", "cohesion"],
        "protected_terms": ["STYLIA", "MVP"],
        "lt_disabled_rules": [],
    }


@pytest.fixture
def sample_term_registry():
    """Glosario básico con términos protegidos."""
    return [
        {"term": "machine learning editorial", "is_protected": True},
        {"term": "pipeline de corrección", "is_protected": False},
    ]
