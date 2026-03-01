"""
Cliente OpenAI para corrección de estilo con contexto.
Usa gpt-4o-mini para ser económico y eficiente.
"""

import json
import logging
from typing import Optional

from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)


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
            
        # Construir contexto
        context_text = ""
        if context_blocks:
            context_lines = []
            for i, block in enumerate(context_blocks[-3:], 1):  # Últimos 3 bloques
                context_lines.append(f"Párrafo {i}: {block}")
            context_text = f"\\n\\nCONTEXTO PREVIO (párrafos ya corregidos):\\n{chr(10).join(context_lines)}\\n\\n"
        
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
            
            # Parsear JSON response
            correction_data = json.loads(content)
            corrected_text = correction_data.get("corrected_text", original_text)
            
            # Validar longitud
            if len(corrected_text) > max_length:
                logger.warning(f"Texto corregido excede longitud máxima ({len(corrected_text)} > {max_length})")
                return original_text  # Retornar original si excede
                
            logger.info(f"OpenAI: {len(correction_data.get('changes_made', []))} cambios aplicados")
            logger.info(f"OpenAI response: {correction_data.get('changes_made', [])}")
            return corrected_text
            
        except Exception as e:
            logger.error(f"Error al llamar OpenAI API: {e}")
            return None
    
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