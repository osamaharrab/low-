from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from api.settings import Settings


class TranslationUnavailableError(RuntimeError):
    """Raised when LibreTranslate is unavailable or times out."""


class TranslationBadGatewayError(RuntimeError):
    """Raised when LibreTranslate returns an unusable response."""


def _create_async_client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)


async def translate_arabic_to_english(text: str, settings: Settings) -> str:
    url = f"{settings.libretranslate_url.rstrip('/')}/translate"
    payload = {
        "q": text,
        "source": "ar",
        "target": "en",
        "format": "text",
    }

    try:
        async with _create_async_client(settings.libretranslate_timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
        raise TranslationUnavailableError("LibreTranslate is unavailable.") from exc
    except httpx.HTTPError as exc:
        raise TranslationBadGatewayError("LibreTranslate request failed.") from exc

    if response.status_code >= 500:
        raise TranslationUnavailableError("LibreTranslate is unavailable.")
    if response.status_code >= 400:
        raise TranslationBadGatewayError("LibreTranslate rejected the request.")

    try:
        data = response.json()
    except ValueError as exc:
        raise TranslationBadGatewayError("LibreTranslate returned invalid JSON.") from exc

    translated_text = data.get("translatedText") if isinstance(data, dict) else None
    if not isinstance(translated_text, str) or not translated_text.strip():
        raise TranslationBadGatewayError("LibreTranslate returned an invalid translation.")

    return translated_text.strip()
