"""TTS 프로바이더 팩토리 - 환경변수로 스위칭."""

from __future__ import annotations

import os

from src.tts.base import TTSProvider


def create_tts_provider(config: dict) -> TTSProvider:
    """TTS_PROVIDER 환경변수에 따라 프로바이더 인스턴스 생성."""
    provider_name = os.getenv("TTS_PROVIDER", "edge").lower()

    tts_config = config.get("tts", {}).get(provider_name, {})

    if provider_name == "edge":
        from src.tts.edge_tts_provider import EdgeTTSProvider
        return EdgeTTSProvider(tts_config)
    elif provider_name == "google":
        from src.tts.google_tts_provider import GoogleTTSProvider
        return GoogleTTSProvider(tts_config)
    else:
        raise ValueError(
            f"알 수 없는 TTS 프로바이더: '{provider_name}'. "
            "사용 가능: edge, google"
        )
