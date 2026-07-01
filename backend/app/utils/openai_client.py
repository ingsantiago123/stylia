"""
Cliente OpenAI para corrección de estilo con contexto.
Plan v4: captura RAW de request/response para trazabilidad total.
"""

import json
import logging
import threading
import time
from typing import Optional, Callable

from openai import (
    OpenAI, RateLimitError, APITimeoutError, APIConnectionError,
    AuthenticationError,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = logging.getLogger(__name__)


def _extract_usage(response) -> dict:
    """Extrae tokens de uso de una respuesta de OpenAI."""
    if response and hasattr(response, "usage") and response.usage:
        return {
            "prompt_tokens": response.usage.prompt_tokens or 0,
            "completion_tokens": response.usage.completion_tokens or 0,
            "total_tokens": response.usage.total_tokens or 0,
        }
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


class OpenAIClient:
    """Cliente para interactuar con la API de OpenAI."""
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self.temperature = settings.openai_temperature
        
        # Inicializar cliente OpenAI con timeout configurable
        if self.api_key and self.api_key != "your_api_key_here":
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=settings.openai_timeout,
            )
        else:
            self.client = None
            logger.warning("OpenAI API key no configurada")

        # Semáforo: max 3 llamadas concurrentes a OpenAI por proceso
        self._semaphore = threading.Semaphore(3)

        # Circuit breaker: tras un 401 (API key inválida) se suspenden las
        # llamadas de este proceso — antes se disparaban cientos de requests
        # condenados (uno por párrafo) y el documento "completaba" sin que
        # nadie viera que la IA nunca corrió.
        self._auth_failed = False

        # Build tenacity retry decorator from config
        self._retry = retry(
            stop=stop_after_attempt(settings.openai_max_retries),
            wait=wait_exponential(multiplier=2, min=2, max=8),
            retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
            before_sleep=lambda rs: logger.warning(
                f"OpenAI retry #{rs.attempt_number} after {type(rs.outcome.exception()).__name__}"
            ),
            reraise=True,
        )
        
    def correct_text_style(
        self,
        original_text: str,
        context_blocks: list[str],
        max_length_ratio: float = 1.1
    ) -> tuple[Optional[str], dict]:
        """
        Corrige el estilo del texto usando ChatGPT con contexto acumulado.

        Returns:
            Tupla (texto_corregido, usage_dict) donde usage_dict tiene
            prompt_tokens, completion_tokens, total_tokens.
        """
        empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if not self.client or self._auth_failed:
            # Fase 0: antes aquí se "simulaba" una corrección con reemplazos
            # hardcodeados — fabricaba cambios falsos en producción cuando
            # faltaba la API key. Ahora se devuelve None (sin corrección).
            logger.warning(
                "OpenAI no disponible (API key ausente o inválida) — "
                "párrafo sin corrección de estilo"
            )
            return None, empty_usage
            
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
            with self._semaphore:
                # Llamar a OpenAI API con retry automático ante errores transitorios
                response = self._retry(self.client.chat.completions.create)(
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
                    max_completion_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"}
                )

            content = response.choices[0].message.content
            usage = _extract_usage(response)

            # Parsear JSON response
            correction_data = json.loads(content)
            corrected_text = correction_data.get("corrected_text", original_text)

            # Validar longitud
            if len(corrected_text) > max_length:
                logger.warning(f"Texto corregido excede longitud máxima ({len(corrected_text)} > {max_length})")
                return original_text, usage

            logger.info(f"OpenAI: {len(correction_data.get('changes_made', []))} cambios aplicados")
            return corrected_text, usage

        except Exception as e:
            if isinstance(e, AuthenticationError):
                self._mark_auth_failed()
            logger.error(f"Error al llamar OpenAI API: {e}")
            return None, empty_usage
    
    def correct_with_profile(
        self,
        system_prompt: str,
        user_prompt: str,
        max_length: int | None = None,
        model_override: str | None = None,
        max_tokens_override: int | None = None,
        on_audit_log: Callable[[dict], None] | None = None,
        response_schema: dict | None = None,
        schema_name: str = "correccion",
    ) -> tuple[dict | None, dict]:
        """
        MVP2: Corrección con prompts parametrizados.
        Retorna tupla (data_dict, usage_dict).

        Args:
            model_override: Modelo alternativo (ej. editorial). Si None usa self.model.
            max_tokens_override: Límite de tokens para esta llamada. Si None usa self.max_tokens.
            response_schema: Fase 5 — JSON Schema estricto (Structured Outputs).
                La API garantiza la forma de la respuesta; si el modelo/API no
                lo soporta se cae automáticamente a json_object.
        """
        empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if not self.client:
            logger.warning("OpenAI cliente no disponible")
            return None, empty_usage
        if self._auth_failed:
            # Circuit breaker abierto: no quemar más llamadas con key inválida
            return None, empty_usage

        model = model_override or self.model
        max_tokens = max_tokens_override or self.max_tokens

        request_payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_completion_tokens": max_tokens,
            "temperature": self.temperature,
        }
        # Fase 5: reproducibilidad del audit trail
        if settings.openai_seed is not None:
            request_payload["seed"] = settings.openai_seed

        response_format: dict = {"type": "json_object"}
        if response_schema and settings.openai_use_json_schema:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": response_schema,
                },
            }

        t0 = time.monotonic()
        try:
            # Fase 0: detectar truncamiento por max_tokens (finish_reason ==
            # "length"). Antes el JSON truncado fallaba el parse y se
            # interpretaba silenciosamente como "el LLM no corrigió".
            response = None
            finish_reason = None
            usage = dict(empty_usage)
            for attempt_tokens in (max_tokens, max_tokens * 2):
                request_payload["max_completion_tokens"] = attempt_tokens
                try:
                    with self._semaphore:
                        response = self._retry(self.client.chat.completions.create)(
                            **{k: v for k, v in request_payload.items()},
                            response_format=response_format,
                        )
                except Exception as _sf_err:
                    # Fallback: modelos/APIs sin soporte json_schema strict
                    if response_format.get("type") == "json_schema":
                        logger.warning(
                            f"json_schema falló ({type(_sf_err).__name__}: {_sf_err}) "
                            f"— fallback a json_object"
                        )
                        response_format = {"type": "json_object"}
                        with self._semaphore:
                            response = self._retry(self.client.chat.completions.create)(
                                **{k: v for k, v in request_payload.items()},
                                response_format=response_format,
                            )
                    else:
                        raise
                attempt_usage = _extract_usage(response)
                # Acumular usage de todos los intentos (costo honesto)
                for k in usage:
                    usage[k] += attempt_usage.get(k, 0)
                finish_reason = (
                    response.choices[0].finish_reason if response.choices else None
                )
                if finish_reason != "length":
                    break
                logger.warning(
                    f"Respuesta LLM truncada por max_tokens={attempt_tokens} "
                    f"(modelo={model}) — reintentando con {attempt_tokens * 2}"
                )

            latency_ms = int((time.monotonic() - t0) * 1000)
            content = response.choices[0].message.content

            if finish_reason == "length":
                logger.error(
                    f"Respuesta LLM truncada incluso con max_tokens={max_tokens * 2} "
                    f"(modelo={model}) — descartando (fallback a LT)"
                )
                if on_audit_log:
                    on_audit_log({
                        "request_payload": request_payload,
                        "response_payload": None,
                        "latency_ms": latency_ms,
                        "model_used": model,
                        **usage,
                        "error_text": "truncated_by_max_tokens",
                    })
                return None, usage

            try:
                data = json.loads(content)
            except json.JSONDecodeError as je:
                logger.error(
                    f"Respuesta LLM no es JSON válido (finish_reason={finish_reason}, "
                    f"modelo={model}): {je} — contenido[:200]={content[:200]!r}"
                )
                if on_audit_log:
                    on_audit_log({
                        "request_payload": request_payload,
                        "response_payload": {"raw_content": content[:2000]},
                        "latency_ms": latency_ms,
                        "model_used": model,
                        **usage,
                        "error_text": f"json_decode_error: {je}",
                    })
                return None, usage

            # Captura RAW para auditoría
            if on_audit_log:
                response_payload = {
                    "id": getattr(response, "id", None),
                    "model": getattr(response, "model", model),
                    "choices": [
                        {
                            "finish_reason": c.finish_reason,
                            "message": {"role": "assistant", "content": c.message.content},
                        }
                        for c in (response.choices or [])
                    ],
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                    },
                }
                on_audit_log({
                    "request_payload": request_payload,
                    "response_payload": response_payload,
                    "latency_ms": latency_ms,
                    "model_used": model,
                    **usage,
                    "error_text": None,
                })

            # Validar longitud si se especifica
            corrected = data.get("corrected_text", "")
            if max_length and corrected and len(corrected) > max_length:
                logger.warning(
                    f"Texto corregido excede máximo ({len(corrected)} > {max_length}), descartando"
                )
                data["action"] = "skip"
                data["corrected_text"] = ""
                data["changes"] = []

            return data, usage

        except Exception as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            if isinstance(e, AuthenticationError):
                self._mark_auth_failed()
            logger.error(f"Error en correct_with_profile: {e}")
            if on_audit_log:
                on_audit_log({
                    "request_payload": request_payload,
                    "response_payload": None,
                    "latency_ms": latency_ms,
                    "model_used": model,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "error_text": str(e),
                })
            return None, empty_usage

    def _mark_auth_failed(self) -> None:
        """Abre el circuit breaker tras un 401: la key es inválida/revocada.

        Sin esto, un documento de N párrafos disparaba N llamadas HTTP
        condenadas (con retries) y terminaba "completed" sin que el operador
        viera que la IA jamás corrió.
        """
        if not self._auth_failed:
            logger.error(
                "OPENAI_API_KEY INVÁLIDA (401): se suspenden las llamadas LLM "
                "de este proceso. El documento continuará SOLO con LanguageTool. "
                "Verifica la clave en .env y RECREA los contenedores "
                "(docker compose up -d — 'restart' NO recarga el .env)."
            )
        self._auth_failed = True


# Instancia global del cliente
openai_client = OpenAIClient()