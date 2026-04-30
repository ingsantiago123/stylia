"""
Tests unitarios para prompt_builder.py.
Verifica que los bloques estructurales se incluyan correctamente en el prompt.
"""

import pytest
from app.services.prompt_builder import build_user_prompt, build_system_prompt, ParagraphMeta


def test_system_prompt_is_string():
    result = build_system_prompt()
    assert isinstance(result, str)
    assert len(result) > 100


def test_basic_prompt_builds():
    prompt = build_user_prompt(text="El gato come ratones.")
    assert "El gato come ratones" in prompt
    assert "PÁRRAFO A CORREGIR" in prompt


def test_perfil_block_present_with_profile(sample_profile):
    prompt = build_user_prompt(text="Texto.", profile=sample_profile)
    assert "PERFIL:" in prompt
    assert "formal" in prompt
    assert "moderada" in prompt


def test_ubicacion_block_with_paragraph_type():
    prompt = build_user_prompt(text="Texto.", paragraph_type="narrativo")
    assert "UBICACIÓN ESTRUCTURAL" in prompt
    assert "narrativo" in prompt


def test_ubicacion_block_with_titulo():
    prompt = build_user_prompt(text="Capítulo 3", paragraph_type="titulo")
    assert "TÍTULO" in prompt.upper()


def test_ubicacion_block_with_celda_tabla():
    prompt = build_user_prompt(
        text="42",
        paragraph_type="celda_tabla",
        table_context={"header_row": ["Año", "Ventas"], "num_cols": 2, "col_index": 1},
    )
    assert "Ventas" in prompt


def test_page_break_warning_included():
    prompt = build_user_prompt(text="Texto con salto.", has_page_break=True)
    assert "SALTO DE PÁGINA" in prompt.upper() or "salto de página" in prompt.lower()


def test_protected_regions_text_included():
    prompt = build_user_prompt(
        text="ISBN 978-84-376-0494-7",
        protected_regions_text='REGIONES PROTEGIDAS (NO MODIFICAR):\n  - "ISBN 978-84-376-0494-7": isbn',
    )
    assert "REGIONES PROTEGIDAS" in prompt


def test_context_prev_as_dict():
    ctx = {
        "text": "El capítulo anterior abordó el tema.",
        "type": "narrativo",
        "ends_abruptly": False,
        "location_type": "body",
    }
    prompt = build_user_prompt(text="El presente capítulo.", context_prev=ctx)
    assert "CONTEXTO PREVIO" in prompt
    assert "El capítulo anterior" in prompt


def test_context_prev_ends_abruptly():
    ctx = {
        "text": "El párrafo termina de manera abrupta sin punto final",
        "type": "narrativo",
        "ends_abruptly": True,
        "location_type": "body",
    }
    prompt = build_user_prompt(text="Continuación.", context_prev=ctx)
    assert "continúa" in prompt.lower() or "abrupt" in prompt.lower()


def test_context_prev_as_string_legacy():
    prompt = build_user_prompt(text="Párrafo 2.", context_prev="Párrafo 1 anterior.")
    assert "Párrafo 1 anterior" in prompt


def test_context_prev_none_shows_inicio():
    prompt = build_user_prompt(text="Primer párrafo.", context_prev=None)
    assert "Inicio de documento" in prompt


def test_section_summary_included():
    prompt = build_user_prompt(
        text="Texto de la sección.",
        section_summary="Esta sección aborda los métodos de análisis",
    )
    assert "SECCIÓN:" in prompt
    assert "métodos de análisis" in prompt


def test_next_paragraph_type_hint():
    prompt = build_user_prompt(
        text="Párrafo narrativo.",
        next_paragraph_type="titulo",
    )
    assert "SIGUIENTE" in prompt
    assert "TÍTULO" in prompt.upper()


def test_paragraph_meta_dataclass():
    meta = ParagraphMeta(
        paragraph_index=5,
        location="body:5",
        paragraph_type="narrativo",
        text="Texto de prueba.",
    )
    ctx_dict = meta.to_context_dict()
    assert ctx_dict["type"] == "narrativo"
    assert ctx_dict["text"] == "Texto de prueba."
    assert meta.location_type() == "body"


def test_paragraph_meta_ends_abruptly():
    meta = ParagraphMeta(
        paragraph_index=3,
        location="body:3",
        paragraph_type="narrativo",
        text="Texto que no termina bien",
        ends_abruptly=True,
    )
    ctx_dict = meta.to_context_dict()
    assert ctx_dict["ends_abruptly"] is True


def test_no_extra_whitespace_in_prompt():
    prompt = build_user_prompt(text="Texto.", paragraph_type="narrativo", profile={
        "register": "formal",
        "intervention_level": "moderada",
        "preserve_author_voice": True,
        "max_rewrite_ratio": 0.3,
    })
    # No debe haber líneas completamente vacías múltiples consecutivas
    lines = prompt.split("\n")
    consecutive_empty = 0
    for line in lines:
        if not line.strip():
            consecutive_empty += 1
        else:
            consecutive_empty = 0
        assert consecutive_empty < 4, "Demasiadas líneas vacías consecutivas"
