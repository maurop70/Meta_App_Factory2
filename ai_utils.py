"""
ai_utils.py — Aether Native AI Utilities
═════════════════════════════════════════
Provides exponential backoff wrappers for Google GenAI SDK calls.

Two variants:
  - generate_with_backoff_sync  → for code running in threads (asyncio.to_thread / sync contexts)
  - generate_with_backoff_async → for native async/await call sites

Retryable errors: 503 (Unavailable), 429 (Resource Exhausted)
Backoff schedule: 2s → 4s → 8s (base_delay=2, factor=2, max_api_retries=3)
"""

import asyncio
import time
import logging

logger = logging.getLogger(__name__)


def _is_retryable(err_str: str) -> bool:
    """Returns True if the error is a transient API availability issue."""
    markers = ("503", "429", "UNAVAILABLE", "Resource Exhausted", "rate limit", "quota")
    lower = err_str.lower()
    return any(m.lower() in lower for m in markers)


def generate_with_backoff_sync(
    generate_fn,
    *args,
    max_api_retries: int = 3,
    base_delay: float = 2.0,
    backoff_factor: float = 2.0,
    **kwargs
):
    """
    Synchronous exponential backoff wrapper.
    Use this inside functions called via asyncio.to_thread() or pure sync contexts.

    Usage:
        response = generate_with_backoff_sync(
            client.models.generate_content,
            model='gemini-2.5-pro',
            contents=prompt
        )
    """
    delay = base_delay
    last_exc: Exception = None

    for attempt in range(1, max_api_retries + 1):
        try:
            return generate_fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if _is_retryable(err_str) and attempt < max_api_retries:
                logger.warning(
                    f"[AI BACKOFF SYNC] Attempt {attempt}/{max_api_retries} failed "
                    f"(retryable: {e.__class__.__name__}). Waiting {delay:.0f}s..."
                )
                time.sleep(delay)
                delay *= backoff_factor
                last_exc = e
            else:
                # Non-retryable, or attempts exhausted — let it bubble
                raise

    raise last_exc  # exhausted retries


async def generate_with_backoff_async(
    generate_fn,
    *args,
    max_api_retries: int = 3,
    base_delay: float = 2.0,
    backoff_factor: float = 2.0,
    **kwargs
):
    """
    Asynchronous exponential backoff wrapper.
    Use this for native async call sites (e.g. async Gemini SDK methods).

    Usage:
        response = await generate_with_backoff_async(
            client.aio.models.generate_content,
            model='gemini-2.5-pro',
            contents=prompt
        )
    """
    delay = base_delay
    last_exc: Exception = None

    for attempt in range(1, max_api_retries + 1):
        try:
            return await generate_fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if _is_retryable(err_str) and attempt < max_api_retries:
                logger.warning(
                    f"[AI BACKOFF ASYNC] Attempt {attempt}/{max_api_retries} failed "
                    f"(retryable: {e.__class__.__name__}). Waiting {delay:.0f}s..."
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
                last_exc = e
            else:
                raise

    raise last_exc  # exhausted retries
