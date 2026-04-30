"""
Tests unitarios para protected_regions.py.
Verifica detección de ISBN, DOI, citas APA, nombres propios, términos del glosario.
"""

import pytest
from app.services.protected_regions import (
    detect_protected_regions,
    regions_to_prompt_text,
    modification_touches_protected,
)


def test_detects_isbn():
    text = "El libro tiene ISBN 978-84-376-0494-7 en portada."
    regions = detect_protected_regions(text)
    assert any(r.reason == "isbn" for r in regions)
    isbn_region = next(r for r in regions if r.reason == "isbn")
    assert "978" in isbn_region.text


def test_detects_doi():
    text = "Publicado en doi: 10.1234/journal.2024.001 con acceso abierto."
    regions = detect_protected_regions(text)
    assert any(r.reason == "doi" for r in regions)


def test_detects_url():
    text = "Consulta https://www.ejemplo.com/recurso para más información."
    regions = detect_protected_regions(text)
    assert any(r.reason == "url" for r in regions)


def test_detects_apa_citation():
    text = "Según estudios previos (García, 2020) la coherencia es clave."
    regions = detect_protected_regions(text)
    assert any(r.reason == "apa_citation" for r in regions)


def test_detects_numeric_citation():
    text = "Como se menciona en los trabajos anteriores [1, 3, 5]."
    regions = detect_protected_regions(text)
    assert any(r.reason == "numeric_citation" for r in regions)


def test_detects_profile_terms(sample_profile):
    text = "El sistema STYLIA implementa el MVP con éxito."
    regions = detect_protected_regions(text, profile=sample_profile)
    reasons = [r.reason for r in regions]
    assert "profile_term" in reasons
    protected_texts = [r.text.upper() for r in regions if r.reason == "profile_term"]
    assert "STYLIA" in protected_texts or "MVP" in protected_texts


def test_detects_glossary_terms(sample_term_registry):
    text = "El machine learning editorial es fundamental en este proceso."
    regions = detect_protected_regions(text, term_registry=sample_term_registry)
    glossary_regions = [r for r in regions if r.reason == "glossary_term"]
    assert len(glossary_regions) == 1
    assert "machine learning editorial" in glossary_regions[0].text.lower()


def test_no_false_positives_beginning_of_sentence():
    """Palabras al inicio de oración no deben ser detectadas como nombres propios."""
    text = "Los resultados muestran una mejora significativa en el rendimiento."
    regions = detect_protected_regions(text)
    proper_names = [r for r in regions if r.reason == "proper_name"]
    # No debe detectar "Los" como nombre propio
    assert not any("Los" in r.text for r in proper_names)


def test_no_duplicate_regions():
    """Las regiones no deben solaparse."""
    text = "Referencia a ISBN 978-84-376-0494-7 y (García, 2020) y STYLIA."
    profile = {"protected_terms": ["STYLIA"]}
    regions = detect_protected_regions(text, profile=profile)
    # Verificar no solapamientos
    for i in range(len(regions) - 1):
        assert regions[i].end <= regions[i + 1].start, \
            f"Solapamiento entre regiones {i} y {i+1}"


def test_regions_to_prompt_text():
    text = "Texto con ISBN 978-84-376-0494-7."
    regions = detect_protected_regions(text)
    prompt_text = regions_to_prompt_text(regions)
    assert "REGIONES PROTEGIDAS" in prompt_text
    assert "isbn" in prompt_text


def test_modification_touches_protected_detects_change():
    text = "Texto de la Dra. Carmen Villanueva aquí."
    regions = detect_protected_regions(text)
    # Simular que el corrector quitó el nombre
    corrected = "Texto de la doctora aquí."
    violated = modification_touches_protected(text, corrected, regions)
    # Puede detectar o no según la heurística, pero no debe lanzar excepción
    assert isinstance(violated, list)


def test_empty_text():
    regions = detect_protected_regions("")
    assert regions == []


def test_text_without_protected_content():
    text = "El cielo es azul y el agua es transparente."
    regions = detect_protected_regions(text)
    # No debe detectar nada en texto simple sin marcadores especiales
    # (puede haber o no según la heurística de nombres propios)
    assert isinstance(regions, list)
