"""edge-tts 프로바이더 (기본값, 무료, 한국어 지원)."""

from __future__ import annotations

import logging

import edge_tts

from src.storage.models import TTSResult, WordBoundary
from src.tts.base import TTSProvider

logger = logging.getLogger(__name__)


class EdgeTTSProvider(TTSProvider):
    def __init__(self, config: dict):
        self.voice = config.get("voice", "ko-KR-SunHiNeural")
        self.rate = config.get("rate", "+0%")
        self.volume = config.get("volume", "+0%")

    @property
    def provider_name(self) -> str:
        return "edge"

    async def synthesize(self, text: str, output_path: str) -> TTSResult:
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
        )

        submaker = edge_tts.SubMaker()
        word_boundaries: list[WordBoundary] = []
        total_duration_ms = 0

        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                else:
                    # SentenceBoundary / WordBoundary 모두 SubMaker에 전달
                    submaker.feed(chunk)

        # SubMaker cues에서 타임스탬프 추출
        for cue in submaker.cues:
            start_ms = int(cue.start.total_seconds() * 1000)
            end_ms = int(cue.end.total_seconds() * 1000)
            word_boundaries.append(
                WordBoundary(
                    text=cue.content,
                    offset_ms=start_ms,
                    duration_ms=end_ms - start_ms,
                )
            )
            total_duration_ms = max(total_duration_ms, end_ms)

        logger.info(
            f"TTS 생성 완료: {output_path} "
            f"({total_duration_ms / 1000:.1f}초, {len(word_boundaries)} segments)"
        )

        return TTSResult(
            audio_path=output_path,
            word_boundaries=word_boundaries,
            duration_ms=total_duration_ms,
            provider=self.provider_name,
        )
