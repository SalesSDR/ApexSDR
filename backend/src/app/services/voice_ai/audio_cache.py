import base64
import logging
import uuid

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_KEY_PREFIX = "voice_tts_audio:"
# Plenty of time for Twilio's <Play> to fetch it once; short enough that
# ElevenLabs audio doesn't pile up in Redis.
_TTL_SECONDS = 300


async def store_audio(redis: aioredis.Redis, audio_bytes: bytes, content_type: str) -> str:
    """Caches synthesized TTS audio ephemerally so Twilio's <Play> verb can
    fetch it over HTTP - ElevenLabs' API returns raw audio bytes, not a
    hosted URL, so this is the thinnest possible way to give Twilio
    something to GET. Base64-encoded since the shared redis_client decodes
    responses as text (see app/database.py)."""
    audio_id = uuid.uuid4().hex
    payload = f"{content_type}|{base64.b64encode(audio_bytes).decode('ascii')}"
    await redis.set(f"{_KEY_PREFIX}{audio_id}", payload, ex=_TTL_SECONDS)
    return audio_id


async def get_audio(redis: aioredis.Redis, audio_id: str) -> tuple[bytes, str] | None:
    raw = await redis.get(f"{_KEY_PREFIX}{audio_id}")
    if raw is None:
        return None
    content_type, _, encoded = raw.partition("|")
    return base64.b64decode(encoded), content_type
