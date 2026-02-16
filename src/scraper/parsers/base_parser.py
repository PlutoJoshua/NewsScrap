"""기사 파서 추상 베이스 클래스."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from src.storage.models import ArticleContent

# 한국 뉴스 기사에서 제거할 패턴
_CLEANUP_PATTERNS = [
    (r"[\w.-]+@[\w.-]+\.\w+", ""),  # 이메일
    (r"\[[\w\s]+\s*기자\]", ""),  # [홍길동 기자]
    (r"[\w\s]+\s*기자\s*=\s*", ""),  # 홍길동 기자 =
    (r"©.*$", ""),  # 저작권
    (r"\(사진[=:].*?\)", ""),  # (사진=연합뉴스)
    (r"▶.*$", ""),  # 관련 기사 링크
    (r"<저작권자.*", ""),  # 저작권 고지
    (r"\[ⓒ.*?\]", ""),  # [ⓒ ...]
    (r"무단\s*전재.*배포\s*금지", ""),  # 무단전재 배포금지
]


class BaseArticleParser(ABC):
    """사이트별 파서가 구현해야 할 인터페이스."""

    @abstractmethod
    def can_parse(self, url: str) -> bool:
        """이 URL을 처리할 수 있는지 여부."""
        ...

    @abstractmethod
    def parse(self, html: str, url: str) -> ArticleContent:
        """HTML에서 기사 내용을 추출."""
        ...

    def _clean_text(self, text: str) -> str:
        """한국 뉴스 기사 텍스트 정리."""
        for pattern, replacement in _CLEANUP_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
        text = re.sub(r"\s+", " ", text).strip()
        return text
