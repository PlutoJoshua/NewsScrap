"""Google Cloud TTS 프로바이더."""

from __future__ import annotations

import logging

from src.storage.models import TTSResult, WordBoundary
from src.tts.base import TTSProvider

logger = logging.getLogger(__name__)


class GoogleTTSProvider(TTSProvider):
    def __init__(self, config: dict):
        from google.cloud import texttospeech

        self.client = texttospeech.TextToSpeechClient()
        self.voice_name = config.get("voice_name", "ko-KR-Neural2-A")
        self.speaking_rate = config.get("speaking_rate", 1.0)
        self.pitch = config.get("pitch", 0.0)
        self._tts = texttospeech

    @property
    def provider_name(self) -> str:
        return "google"

    async def synthesize(self, text: str, output_path: str) -> TTSResult:
        synthesis_input = self._tts.SynthesisInput(text=text)

        voice = self._tts.VoiceSelectionParams(
            language_code="ko-KR",
            name=self.voice_name,
        )

        audio_config = self._tts.AudioConfig(
            audio_encoding=self._tts.AudioEncoding.MP3,
            speaking_rate=self.speaking_rate,
            pitch=self.pitch,
        )

        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )

        with open(output_path, "wb") as f:
            f.write(response.audio_content)

        # Google Cloud TTS는 timepoints를 별도 요청으로 받아야 함
        # 여기서는 빈 word_boundaries로 반환 (Whisper 폴백 사용)
        logger.info(f"TTS 생성 완료: {output_path} (Google Cloud)")

        return TTSResult(
            audio_path=output_path,
            word_boundaries=[],
            duration_ms=0,
            provider=self.provider_name,
        )
