"""
OVHCloud Text-to-Speech handler for NVIDIA Riva TTS models.

OVH AI Endpoints expose Riva TTS via a custom API at:
  POST {model_endpoint}/api/v1/tts/text_to_audio

Parameter mapping (OpenAI → Riva):
    model          → used to derive api_base
    input          → text
    voice          → voice_name  (OpenAI names mapped to Riva defaults)
    response_format→ encoding    (pcm/wav→LINEAR_PCM, flac→FLAC, etc.)
    speed          → (not supported by Riva – silently dropped)
    ---            → language_code   (defaults to en-US, overridable)
    ---            → sample_rate_hz  (defaults to 16000, overridable)
"""

import httpx
from typing import Any, Coroutine, Dict, Optional, Union
from litellm import verbose_logger as log
from litellm.llms.custom_httpx.http_handler import (
    AsyncHTTPHandler,
    HTTPHandler,
)
from litellm.types.llms.openai import HttpxBinaryResponseContent

# ── Voice defaults ──────────────────────────────────────────────
_DEFAULT_VOICE = "English-US.Male-1"
_DEFAULT_LANG = "en-US"

# OpenAI voice names that should be replaced with Riva defaults
_OPENAI_VOICES = frozenset(
    {"alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral", "sage", "ash"}
)

# response_format → Riva encoding int
# OVH only supports LINEAR_PCM (1) and OGGOPUS (4)
_ENCODING_MAP: Dict[str, int] = {
    "wav": 1,       # LINEAR_PCM
    "pcm": 1,       # LINEAR_PCM
    "mp3": 1,       # Not supported → LINEAR_PCM fallback
    "flac": 1,      # Not supported → LINEAR_PCM fallback
    "aac": 1,       # Not supported → LINEAR_PCM fallback
    "opus": 4,      # OGGOPUS
}


def _build_riva_request(
    model: str,
    input: str,
    voice: Optional[str],
    optional_params: dict,
) -> Dict[str, Any]:
    """
    Build the Riva TTS request body from OpenAI-format parameters.
    """
    params = dict(optional_params) if optional_params else {}

    # Default to English-US (the only confirmed working voice on all OVH endpoints)
    language_code = params.pop("language_code", _DEFAULT_LANG)
    default_voice = _DEFAULT_VOICE

    log.debug(
        f"OVHCloud TTS: model='{model}', voice='{voice}', "
        f"default='{default_voice}', params={params}"
    )

    # ── voice_name ──
    # explicit Riva override in optional_params wins
    voice_name = params.pop("voice_name", None)
    if voice_name is None:
        if voice is None or voice.lower() in _OPENAI_VOICES:
            voice_name = default_voice
        else:
            # User passed a Riva voice name directly — use it as-is
            voice_name = voice

    # ── encoding ──
    encoding = params.pop("encoding", None)
    response_format = params.pop("response_format", None)
    if encoding is None and response_format:
        encoding = _ENCODING_MAP.get(response_format.lower(), 1)
    elif encoding is None:
        encoding = 1 

    # ── speed ── (not supported by Riva)
    speed = params.pop("speed", None)
    if speed is not None:
        log.debug(
            f"OVHCloud TTS: 'speed={speed}' is not supported by Riva – dropping"
        )

    # ── sample_rate_hz ──
    sample_rate_hz = params.pop("sample_rate_hz", 16000)

    body: Dict[str, Any] = {
        "text": input,
        "language_code": language_code,
        "encoding": encoding,
        "sample_rate_hz": sample_rate_hz,
        "voice_name": voice_name,
    }
    # Pass through any remaining Riva-native params
    body.update(params)
    return body


def _get_api_url(api_base: str) -> str:
    """Build the full Riva TTS URL from the api_base."""
    return f"{api_base.rstrip('/')}/api/v1/tts/text_to_audio"


def _derive_api_base(model: str, api_base: Optional[str]) -> str:
    """
    Derive the model-specific OVH endpoint URL.

    Each OVH AI Endpoints model has its own subdomain:
        https://{model_name}.endpoints.kepler.ai.cloud.ovh.net
    """
    if api_base:
        return api_base

    clean_model = model.split("/")[-1] if "/" in model else model
    return f"https://{clean_model}.endpoints.kepler.ai.cloud.ovh.net"


def ovhcloud_speech(
    model: str,
    input: str,
    voice: Optional[str],
    optional_params: dict,
    api_key: Optional[str],
    api_base: Optional[str],
    timeout: Union[float, httpx.Timeout],
    aspeech: Optional[bool] = None,
    **kwargs,
) -> Union[HttpxBinaryResponseContent, Coroutine]:
    api_base = _derive_api_base(model, api_base)

    if aspeech:
        return _async_ovhcloud_speech(
            model=model,
            input=input,
            voice=voice,
            optional_params=optional_params,
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
        )
    return _sync_ovhcloud_speech(
        model=model,
        input=input,
        voice=voice,
        optional_params=optional_params,
        api_key=api_key,
        api_base=api_base,
        timeout=timeout,
    )

# ── Sync implementation ─────────────────────────────────────────
def _sync_ovhcloud_speech(
    model: str,
    input: str,
    voice: Optional[str],
    optional_params: dict,
    api_key: Optional[str],
    api_base: str,
    timeout: Union[float, httpx.Timeout],
) -> HttpxBinaryResponseContent:
    url = _get_api_url(api_base)
    body = _build_riva_request(model, input, voice, optional_params)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    handler = HTTPHandler(timeout=timeout)
    response = handler.post(url=url, json=body, headers=headers)
    return HttpxBinaryResponseContent(response=response)


# ── Async implementation ────────────────────────────────────────
async def _async_ovhcloud_speech(
    model: str,
    input: str,
    voice: Optional[str],
    optional_params: dict,
    api_key: Optional[str],
    api_base: str,
    timeout: Union[float, httpx.Timeout],
) -> HttpxBinaryResponseContent:
    url = _get_api_url(api_base)
    body = _build_riva_request(model, input, voice, optional_params)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    handler = AsyncHTTPHandler(timeout=timeout)
    response = await handler.post(url=url, json=body, headers=headers)
    return HttpxBinaryResponseContent(response=response)
