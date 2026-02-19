"""LLM 프로바이더 추상 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.storage.models import Article, Briefing


class LLMProvider(ABC):
    """뉴스 요약 및 브리핑 생성을 위한 LLM 인터페이스."""

    @abstractmethod
    def summarize_single(self, article: Article) -> str:
        """단일 기사를 2~3문장으로 요약."""
        ...

    @abstractmethod
    def generate_briefing(self, articles: list[Article], date: str) -> Briefing:
        """여러 기사를 종합하여 일일 브리핑 + 숏츠 스크립트 생성."""
        ...

    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        """범용 텍스트 생성 (명언 해설 등 프로필별 스크립트 생성용)."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...
