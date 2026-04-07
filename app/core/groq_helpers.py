import json
import logging
import groq
from groq import Groq
from fastapi import HTTPException
from app.core.config import Settings

logger = logging.getLogger(__name__)

def call_groq_with_fallback(
    settings: Settings,
    model: str,
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 4096,
    response_format: dict | None = None,
    stream: bool = False
):
    """
    Calls Groq with automatic fallback between two API keys if a RateLimitError occurs.
    Priority: groq_api_key_2 (Primary for interviews) -> groq_api_key (Secondary)
    """
    # Keys to try in order
    api_keys = []
    if settings.groq_api_key_2:
        api_keys.append(settings.groq_api_key_2)
    if settings.groq_api_key:
        api_keys.append(settings.groq_api_key)
    
    if not api_keys:
        raise HTTPException(status_code=503, detail="No Groq API keys configured")

    last_error = None
    for i, key in enumerate(api_keys):
        try:
            client = Groq(api_key=key)
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                stream=stream
            )
            return completion
        except groq.RateLimitError as e:
            logger.warning(f"Groq API key {i+1} rate limited. Error: {str(e)}")
            last_error = e
            if i < len(api_keys) - 1:
                logger.info("Switching to fallback API key...")
                continue
            else:
                # All keys failed
                raise HTTPException(
                    status_code=429,
                    detail=f"All Groq API keys reached their rate limit. Please try again later. {str(e)}"
                )
        except Exception as e:
            logger.error(f"Unexpected error with Groq API key {i+1}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error communicating with AI service: {str(e)}"
            )

    raise HTTPException(status_code=500, detail="Unexpected failure in Groq fallback logic")
