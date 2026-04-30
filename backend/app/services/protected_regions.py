"""
Detección de regiones protegidas en texto editorial.

Identifica segmentos que NO deben modificarse:
  - ISBN, DOI, URLs
  - Citas APA/numéricas: (Apellido, año) o [N]
  - Nombres propios (secuencias de mayúsculas no al inicio de oración)
  - Términos del glosario marcados como is_protected
  - Términos explícitos del perfil (protected_terms)
  - Fechas formales
"""

import re
from dataclasses import dataclass


@dataclass
class ProtectedRegion:
    start: int
    end: int
    reason: str
    text: str

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "reason": self.reason, "text": self.text}


# ── Patrones compilados ──────────────────────────────────────────────

_RE_ISBN = re.compile(
    r'\bISBN(?:-1[03])?\s*:?\s*(?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx]\b',
    re.IGNORECASE,
)
_RE_DOI = re.compile(
    r'\b(?:doi|DOI)\s*:?\s*10\.\d{4,}(?:[.][0-9]+)*/\S+',
    re.IGNORECASE,
)
_RE_URL = re.compile(
    r'https?://[^\s<>"\')\]]+',
    re.IGNORECASE,
)
_RE_APA_CITATION = re.compile(
    # (Apellido, año) o (Apellido y Apellido, año) o (Apellido et al., año)
    r'\(\s*[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+(?:y|&|et al\.)\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)?\s*,\s*\d{4}\s*\)',
)
_RE_NUMERIC_CITATION = re.compile(r'\[\d+(?:,\s*\d+)*\]')
_RE_FORMAL_DATE = re.compile(
    r'\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)'
    r'(?:\s+de\s+\d{4})?\b',
    re.IGNORECASE,
)
_RE_PROPER_NAME = re.compile(
    # Secuencia de 2+ palabras capitalizadas NO al comienzo de oración
    # Exige que haya un carácter no-inicial antes (no sea comienzo de frase)
    r'(?<=[^.!?]\s)([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]{2,}(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]{2,})+)',
)


def detect_protected_regions(
    text: str,
    profile: dict | None = None,
    term_registry: list | None = None,
) -> list[ProtectedRegion]:
    """
    Detecta todas las regiones del texto que no deben ser modificadas.

    Args:
        text: Texto del párrafo.
        profile: Perfil editorial con campo 'protected_terms' (lista de strings).
        term_registry: Lista de objetos con atributos 'term' e 'is_protected'.

    Returns:
        Lista de ProtectedRegion ordenadas por posición de inicio.
    """
    regions: list[ProtectedRegion] = []

    def _add(m: re.Match, reason: str) -> None:
        regions.append(ProtectedRegion(
            start=m.start(), end=m.end(),
            reason=reason, text=m.group(0),
        ))

    # Identificadores de recursos
    for m in _RE_ISBN.finditer(text):
        _add(m, "isbn")
    for m in _RE_DOI.finditer(text):
        _add(m, "doi")
    for m in _RE_URL.finditer(text):
        _add(m, "url")

    # Citas bibliográficas
    for m in _RE_APA_CITATION.finditer(text):
        _add(m, "apa_citation")
    for m in _RE_NUMERIC_CITATION.finditer(text):
        _add(m, "numeric_citation")

    # Fechas formales
    for m in _RE_FORMAL_DATE.finditer(text):
        _add(m, "formal_date")

    # Nombres propios (heurístico: 2+ palabras capitalizadas no al inicio de frase)
    for m in _RE_PROPER_NAME.finditer(text):
        _add(m, "proper_name")

    # Términos del perfil editorial
    if profile:
        for term in profile.get("protected_terms", []):
            t = term.strip()
            if not t:
                continue
            try:
                for m in re.finditer(re.escape(t), text, re.IGNORECASE):
                    _add(m, "profile_term")
            except re.error:
                pass

    # Términos del glosario marcados como protegidos
    if term_registry:
        for entry in term_registry:
            is_protected = getattr(entry, "is_protected", False) if hasattr(entry, "is_protected") \
                else entry.get("is_protected", False) if isinstance(entry, dict) else False
            if not is_protected:
                continue
            term = getattr(entry, "term", None) if hasattr(entry, "term") \
                else entry.get("term", "") if isinstance(entry, dict) else ""
            if not term:
                continue
            try:
                for m in re.finditer(re.escape(term), text, re.IGNORECASE):
                    _add(m, "glossary_term")
            except re.error:
                pass

    # Ordenar por posición y eliminar solapamientos (mantener el más específico = más largo)
    regions.sort(key=lambda r: (r.start, -(r.end - r.start)))
    deduped: list[ProtectedRegion] = []
    last_end = -1
    for r in regions:
        if r.start >= last_end:
            deduped.append(r)
            last_end = r.end

    return deduped


def regions_to_prompt_text(regions: list[ProtectedRegion]) -> str:
    """Formatea regiones protegidas como texto legible para el prompt del LLM."""
    if not regions:
        return ""
    lines = ["REGIONES PROTEGIDAS (NO MODIFICAR):"]
    for r in regions:
        lines.append(f'  - "{r.text}" (pos {r.start}-{r.end}): {r.reason}')
    return "\n".join(lines)


def modification_touches_protected(
    original: str,
    corrected: str,
    regions: list[ProtectedRegion],
) -> list[ProtectedRegion]:
    """
    Comprueba si alguna corrección afecta a regiones protegidas.
    Retorna lista de regiones violadas (vacía si todo está bien).
    """
    if not regions or original == corrected:
        return []

    violated = []
    for region in regions:
        original_fragment = original[region.start:region.end]
        # Buscar el fragmento en el texto corregido
        if original_fragment.lower() not in corrected.lower():
            violated.append(region)
    return violated
