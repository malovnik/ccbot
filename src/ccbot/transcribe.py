"""Voice-to-text transcription — Deepgram or OpenAI, auto-selected.

Uses whichever API key is available (priority: Deepgram > OpenAI).
Both providers accept OGG audio and return plain text.

Key function: transcribe_voice(ogg_data) -> str
"""

import logging

import httpx

from .config import config

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return a lazily-initialized httpx client singleton."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


async def _transcribe_deepgram(client: httpx.AsyncClient, ogg_data: bytes) -> str:
    """Transcribe via Deepgram Nova-2 API."""
    response = await client.post(
        "https://api.deepgram.com/v1/listen",
        headers={
            "Authorization": f"Token {config.deepgram_api_key}",
            "Content-Type": "audio/ogg",
        },
        params={"model": "nova-2", "language": "ru", "smart_format": "true"},
        content=ogg_data,
    )
    response.raise_for_status()

    data = response.json()
    channels = data.get("results", {}).get("channels", [])
    if not channels:
        raise ValueError("Deepgram returned no channels")
    alternatives = channels[0].get("alternatives", [])
    if not alternatives:
        raise ValueError("Deepgram returned no alternatives")
    text = alternatives[0].get("transcript", "").strip()
    if not text:
        raise ValueError("Empty transcription returned by Deepgram")
    return text


async def _transcribe_openai(client: httpx.AsyncClient, ogg_data: bytes) -> str:
    """Transcribe via OpenAI gpt-4o-transcribe API."""
    url = f"{config.openai_base_url.rstrip('/')}/audio/transcriptions"
    response = await client.post(
        url,
        headers={"Authorization": f"Bearer {config.openai_api_key}"},
        files={"file": ("voice.ogg", ogg_data, "audio/ogg")},
        data={"model": "gpt-4o-transcribe"},
    )
    response.raise_for_status()

    text = response.json().get("text", "").strip()
    if not text:
        raise ValueError("Empty transcription returned by OpenAI")
    return text


async def transcribe_voice(ogg_data: bytes) -> str:
    """Transcribe OGG voice data to text.

    Auto-selects provider: Deepgram if DEEPGRAM_API_KEY is set,
    otherwise OpenAI if OPENAI_API_KEY is set.

    Raises:
        httpx.HTTPStatusError: On API errors (401, 429, 5xx, etc.)
        ValueError: If no API key is configured or transcription is empty.
    """
    client = _get_client()

    if config.deepgram_api_key:
        logger.debug("Transcribing via Deepgram")
        return await _transcribe_deepgram(client, ogg_data)
    elif config.openai_api_key:
        logger.debug("Transcribing via OpenAI")
        return await _transcribe_openai(client, ogg_data)
    else:
        raise ValueError(
            "No transcription API key configured. "
            "Set DEEPGRAM_API_KEY or OPENAI_API_KEY in your .env file."
        )


async def close_client() -> None:
    """Close the httpx client (call on shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
