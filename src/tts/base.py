"""TTS 프로바이더 추상 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.storage.models import TTSResult


class TTSProvider(ABC):
    """텍스트를 음성으로 변환하는 TTS 인터페이스."""

    @abstractmethod
    async def synthesize(self, text: str, output_path: str) -> TTSResult:
        """텍스트를 음성 파일로 변환. 워드 타임스탬프 포함."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...
