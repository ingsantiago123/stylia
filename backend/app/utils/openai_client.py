"""
Cliente OpenAI para corrección de estilo con contexto.
Usa gpt-4o-mini para ser económico y eficiente.
"""

import logging
from difflib import SequenceMatcher
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from app.config import settings

logger = logging.getLogger(__name__)
# Se compara solo una muestra para mantener costo computacional bajo en textos largos.
MAX_SIMILARITY_COMPARISON_CHARS = 1500


class StyleCorrectionResponse(BaseModel):
    corrected_text: str
    changes_made: list[str] = []
    character_count: Optional[int] = None


class OpenAIClient:
    """Cliente para interactuar con la API de OpenAI."""
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self.temperature = settings.openai_temperature
        
        # Inicializar cliente OpenAI
        if self.api_key and self.api_key != "your_api_key_here":
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OpenAI API key no configurada")

    def _build_context_text(self, context_blocks: list[str]) -> str:
        """Construye contexto acotado para controlar consumo de tokens/caracteres."""
        if not context_blocks:
            return ""

        selected: list[str] = []
        used_chars = 0
        for block in reversed(context_blocks):
            clean = block.strip()
            if not clean:
                continue
            remaining_chars = settings.openai_max_context_chars - used_chars
            if remaining_chars <= 0:
                break
            if len(clean) > remaining_chars:
                logger.warning(
                    "Bloque de contexto truncado de %s a %s caracteres",
                    len(clean),
                    remaining_chars,
                )
                clean = clean[:remaining_chars]
            projected = used_chars + len(clean)
            selected.append(clean)
            used_chars = projected
            if len(selected) >= settings.openai_max_context_blocks:
                break

        # Puede ocurrir cuando context_blocks tiene entradas vacías o espacios.
        if not selected:
            return ""

        # Se mantiene en español porque el corrector está orientado a documentos en español.
        selected.reverse()
        context_lines = [f"Párrafo {i}: {block}" for i, block in enumerate(selected, 1)]
        return (
            "\n\nCONTEXTO PREVIO (párrafos ya corregidos):\n"
            f"{chr(10).join(context_lines)}\n\n"
        )

    @staticmethod
    def _is_semantically_safe(original_text: str, corrected_text: str) -> bool:
        """Valida cambios extremos para evitar desviación de significado."""
        compare_len = min(
            len(original_text),
            len(corrected_text),
            MAX_SIMILARITY_COMPARISON_CHARS,
        )
        ratio = SequenceMatcher(
            None,
            original_text[:compare_len],
            corrected_text[:compare_len],
        ).ratio()
        return ratio >= settings.openai_min_similarity_ratio
        
    def correct_text_style(
        self,
        original_text: str,
        context_blocks: list[str],
        max_length_ratio: float = 1.1
    ) -> Optional[str]:
        """
        Corrige el estilo del texto usando ChatGPT con contexto acumulado.
        
        Args:
            original_text: Texto a corregir (ya pasó por LanguageTool)
            context_blocks: Párrafos anteriores ya corregidos para contexto
            max_length_ratio: Máxima expansión permitida (1.1 = 110%)
        
        Returns:
            Texto corregido o None si hay error
        """
        if not self.client:
            logger.warning("OpenAI cliente no disponible, usando simulación")
            return self._simulate_correction(original_text)
            
        # Construir contexto acotado por configuración
        context_text = self._build_context_text(context_blocks)
        
        # Calcular longitud máxima permitida
        max_length = int(len(original_text) * max_length_ratio)
        
        # Construir prompt
        prompt = f"""Eres un corrector de estilo profesional en español. Tu tarea es corregir y mejorar el siguiente párrafo.

INSTRUCCIONES ESTRICTAS:
- Mejora claridad, concisión y fluidez del texto
- Mejora la redacción y el estilo sin alterar el tono del autor
- NO cambies el significado ni el contenido
- Mantén consistencia con el contexto previo
- Máximo {max_length} caracteres
- Responde SOLO con el JSON sin explicaciones

Formato de respuesta JSON requerido:
{{
  "corrected_text": "texto corregido aquí",
  "changes_made": ["lista", "de", "cambios", "aplicados"],
  "character_count": número_de_caracteres
}}

{context_text}PÁRRAFO A CORREGIR:
{original_text}"""

        try:
            # Llamar a OpenAI API con el cliente oficial
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un corrector de estilo experto en español. Siempre respondes en formato JSON válido."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            
            if not content:
                logger.error("OpenAI devolvió contenido vacío")
                return original_text

            # Parsear y validar JSON response
            parsed = StyleCorrectionResponse.model_validate_json(content)
            corrected_text = parsed.corrected_text
            
            # Validar longitud
            if len(corrected_text) > max_length:
                logger.warning(f"Texto corregido excede longitud máxima ({len(corrected_text)} > {max_length})")
                return original_text  # Retornar original si excede

            # Validar coherencia semántica aproximada
            if not self._is_semantically_safe(original_text, corrected_text):
                logger.warning("OpenAI devolvió una corrección demasiado distante; se conserva texto original")
                return original_text
                
            logger.info(f"OpenAI: {len(parsed.changes_made)} cambios aplicados")
            if response.usage:
                logger.info(
                    "OpenAI usage: prompt=%s completion=%s total=%s",
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    response.usage.total_tokens,
                )
            return corrected_text
            
        except ValidationError as e:
            logger.error(f"Respuesta OpenAI inválida: {e}")
            return original_text
        except Exception as e:
            logger.error(f"Error al llamar OpenAI API: {e}")
            return original_text
    
    def _simulate_correction(self, text: str) -> str:
        """Simulación de corrección cuando no hay API key."""
        # Mejoras básicas de estilo como respaldo
        style_improvements = {
            "Este texto": "El presente texto",
            "Sirve para": "Se utiliza para",
            "tu sistema": "el sistema",
            " más elegante y claro": " con mayor elegancia y claridad",
            "A veces": "En ocasiones",
            "por que": "porque"
        }
        
        corrected = text
        for original, improved in style_improvements.items():
            if original in corrected:
                corrected = corrected.replace(original, improved)
                break
                
        return corrected


# Instancia global del cliente
openai_client = OpenAIClient()
