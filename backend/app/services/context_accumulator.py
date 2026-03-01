"""
Servicio de Contexto Acumulado para ChatGPT API.
Cada bloque se envía con contexto de bloques anteriores corregidos.
"""

import json
import logging
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from app.utils.openai_client import openai_client

logger = logging.getLogger(__name__)


@dataclass
class BlockContext:
    """Un bloque de texto con su contexto."""
    block_id: str
    block_no: int
    original_text: str
    corrected_text: Optional[str] = None
    position_info: dict = None  # página, coordenadas, font info
    timestamp: datetime = None


@dataclass
class CorrectionRequest:
    """Una petición de corrección que se enviaría a ChatGPT API."""
    block_current: BlockContext
    context_blocks: List[BlockContext]  # bloques anteriores ya corregidos
    document_info: dict
    request_type: str  # "languagetool" | "chatgpt_style"
    prompt: str
    timestamp: datetime


@dataclass
class AccumulatedContext:
    """Contexto acumulado durante el procesamiento del documento."""
    document_id: str
    corrected_blocks: List[BlockContext]
    glossary: dict  # términos específicos encontrados
    style_preferences: dict  # patrones de corrección identificados
    request_history: List[CorrectionRequest]
    
    def add_corrected_block(self, block: BlockContext):
        """Añade un bloque corregido al contexto."""
        self.corrected_blocks.append(block)
    
    def get_recent_context(self, max_blocks: int = 3) -> List[BlockContext]:
        """Obtiene los últimos N bloques para contexto de la siguiente petición."""
        return self.corrected_blocks[-max_blocks:] if self.corrected_blocks else []
    
    def add_request_to_history(self, request: CorrectionRequest):
        """Registra una petición en el historial."""
        self.request_history.append(request)


class ContextualCorrectionService:
    """Servicio que simula el flujo de corrección con contexto acumulado."""
    
    def __init__(self):
        self.contexts: dict[str, AccumulatedContext] = {}
    
    def init_document_context(self, document_id: str, document_info: dict) -> AccumulatedContext:
        """Inicializa el contexto para un nuevo documento."""
        context = AccumulatedContext(
            document_id=document_id,
            corrected_blocks=[],
            glossary={},
            style_preferences={},
            request_history=[]
        )
        self.contexts[document_id] = context
        return context
    
    def simulate_languagetool_request(self, 
                                    document_id: str, 
                                    block: BlockContext) -> CorrectionRequest:
        """Simula una petición a LanguageTool (ortografía/gramática)."""
        context = self.contexts[document_id]
        
        # LanguageTool no necesita contexto, solo el bloque actual
        request = CorrectionRequest(
            block_current=block,
            context_blocks=[],
            document_info={"doc_id": document_id},
            request_type="languagetool",
            prompt=f"Corregir ortografía y gramática: '{block.original_text[:50]}...'",
            timestamp=datetime.now()
        )
        
        context.add_request_to_history(request)
        return request
    
    def simulate_chatgpt_request(self, 
                                document_id: str, 
                                block: BlockContext,
                                post_languagetool_text: str) -> CorrectionRequest:
        """Simula una petición a ChatGPT API con contexto acumulado."""
        context = self.contexts[document_id]
        recent_context = context.get_recent_context(max_blocks=3)
        
        # Construir prompt con contexto
        context_text = ""
        if recent_context:
            context_text = "\n\nCONTEXTO PREVIO (últimos párrafos corregidos):\n"
            for i, ctx_block in enumerate(recent_context, 1):
                context_text += f"Párrafo {ctx_block.block_no}: {ctx_block.corrected_text}\n"
        
        prompt = self._build_chatgpt_prompt(
            current_text=post_languagetool_text,
            block_no=block.block_no,
            context_text=context_text,
            glossary=context.glossary,
            style_preferences=context.style_preferences
        )
        
        request = CorrectionRequest(
            block_current=block,
            context_blocks=recent_context.copy(),
            document_info={"doc_id": document_id},
            request_type="chatgpt_style",
            prompt=prompt,
            timestamp=datetime.now()
        )
        
        context.add_request_to_history(request)
        return request
    
    def _build_chatgpt_prompt(self, 
                             current_text: str, 
                             block_no: int, 
                             context_text: str,
                             glossary: dict,
                             style_preferences: dict) -> str:
        """Construye el prompt para ChatGPT API."""
        
        prompt = f"""Eres un corrector de estilo profesional. Corrige ÚNICAMENTE el estilo, claridad y fluidez del siguiente párrafo.

INSTRUCCIONES:
- NO cambies el significado ni el contenido
- Mejora claridad, concisión y elegancia 
- Mantén consistencia con el contexto previo
- Máximo 110% de la longitud original
- Responde SOLO con el texto corregido, sin explicaciones

{context_text}

PÁRRAFO A CORREGIR (#{block_no}):
{current_text}

TEXTO CORREGIDO:"""
        
        return prompt
    
    def process_block_correction(self, 
                                document_id: str, 
                                block: BlockContext) -> tuple[CorrectionRequest, CorrectionRequest]:
        """Procesa la corrección completa de un bloque: LanguageTool → ChatGPT."""
        
        # 1. Petición LanguageTool
        lt_request = self.simulate_languagetool_request(document_id, block)
        
        # Simular respuesta de LanguageTool
        lt_corrected = self._simulate_languagetool_response(block.original_text)
        
        # 2. Petición ChatGPT con texto post-LanguageTool
        chatgpt_request = self.simulate_chatgpt_request(document_id, block, lt_corrected)
        
        # Usar OpenAI API real para corrección de estilo
        context = self.contexts[document_id]
        previous_blocks = [cb.corrected_text for cb in context.corrected_blocks[-3:]]  # Últimos 3
        
        final_corrected = openai_client.correct_text_style(
            original_text=lt_corrected,
            context_blocks=previous_blocks,
            max_length_ratio=1.1
        )
        
        # Si OpenAI falla, usar texto de LanguageTool como respaldo
        if final_corrected is None:
            logger.warning(f"OpenAI falló para bloque {block.block_no}, usando texto de LanguageTool")
            final_corrected = lt_corrected
        
        # Actualizar el bloque y agregarlo al contexto
        block.corrected_text = final_corrected
        block.timestamp = datetime.now()
        self.contexts[document_id].add_corrected_block(block)
        
        return lt_request, chatgpt_request
    
    def _simulate_languagetool_response(self, text: str) -> str:
        """Simula una respuesta de LanguageTool con correcciones ortográficas reales."""
        # Simulación realista de correcciones LanguageTool
        corrections = {
            # Correcciones de tildes
            " esta ": " está ",
            " proposito": " propósito",
            " tambien": " también", 
            " mas ": " más ",
            " redaccion": " redacción",
            " porque ": " porque ",
            " por que ": " porque ",
            "alarga": "alarga",
            "demasiado": "demasiado",
            "separar": "separar",
            "nadie": "nadie",
            "comas.": "comas.",
            
            # Correcciones básicas
            "hola": "Hola",
            "parrafo": "párrafo",
            "parrafos": "párrafos",
            "facil": "fácil",
            "dificil": "difícil"
        }
        
        corrected = text
        for wrong, right in corrections.items():
            corrected = corrected.replace(wrong, right)
            
        return corrected
    
    def _fallback_style_correction(self, text: str) -> str:
        """Corrección de estilo como respaldo cuando OpenAI no está disponible."""
        # Mejoras básicas de estilo como respaldo
        style_improvements = {
            "A veces la frase se alarga demasiado y no separa ideas": 
            "En ocasiones, las frases se extienden excesivamente sin separar las ideas",
            
            "por que nadie puso comas": 
            "porque no se empleó la puntuación adecuada",
            
            "Este texto": "El presente texto",
            "Sirve para medir": "Se utiliza para evaluar",
            "si tu sistema": "si el sistema",
        }
        
        corrected = text
        for original, improved in style_improvements.items():
            if original in corrected:
                corrected = corrected.replace(original, improved)
                break  # Solo una mejora por simulación
                
        return corrected
    
    def get_correction_history(self, document_id: str) -> List[CorrectionRequest]:
        """Obtiene el historial completo de peticiones para un documento."""
        if document_id in self.contexts:
            return self.contexts[document_id].request_history
        return []
    
    def get_context_summary(self, document_id: str) -> dict:
        """Obtiene resumen del contexto acumulado."""
        if document_id not in self.contexts:
            return {}
        
        context = self.contexts[document_id]
        return {
            "total_blocks": len(context.corrected_blocks),
            "total_requests": len(context.request_history),
            "languagetool_requests": len([r for r in context.request_history if r.request_type == "languagetool"]),
            "chatgpt_requests": len([r for r in context.request_history if r.request_type == "chatgpt_style"]),
            "glossary_entries": len(context.glossary),
            "style_patterns": len(context.style_preferences)
        }


# Helper para generar datos de prueba
def generate_sample_document_flow():
    """Genera un flujo de ejemplo para demostración."""
    service = ContextualCorrectionService()
    doc_id = "doc_sample_123"
    
    # Inicializar contexto
    service.init_document_context(doc_id, {"filename": "documento_prueba.docx", "pages": 5})
    
    # Simular 5 bloques de texto con errores realistas
    sample_blocks = [
        BlockContext("blk_1", 1, "Este texto esta mal escrito a proposito. Sirve para medir si tu sistema corrige tildes.", position_info={"page": 1, "x": 50, "y": 100}),
        BlockContext("blk_2", 2, "El segundo parrafo continua la narrativa. Este texto necesita ser mas elegante y claro.", position_info={"page": 1, "x": 50, "y": 150}),
        BlockContext("blk_3", 3, "En este tercer parrafo desarrollamos la idea principal. La redaccion puede ser mas fluida y profesional.", position_info={"page": 1, "x": 50, "y": 200}),
        BlockContext("blk_4", 4, "A veces la frase se alarga demasiado y no separa ideas, por que nadie puso comas.", position_info={"page": 2, "x": 50, "y": 100}),
        BlockContext("blk_5", 5, "Parrafo final que conclude el documento. Necesita un tono mas profesional y un cierre elegante.", position_info={"page": 2, "x": 50, "y": 150}),
    ]
    
    requests_history = []
    
    # Procesar cada bloque
    for block in sample_blocks:
        lt_req, gpt_req = service.process_block_correction(doc_id, block)
        requests_history.extend([lt_req, gpt_req])
    
    return service, doc_id, requests_history