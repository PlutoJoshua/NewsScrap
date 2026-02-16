"""뉴스 스크래핑 파이프라인 데이터 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RSSEntry(BaseModel):
    """RSS 피드에서 수집한 항목."""

    title: str
    url: str
    source_name: str  # e.g. "한국경제 경제"
    source_key: str  # e.g. "hankyung_economy"
    category: str  # economy, ai, tech
    published_at: Optional[datetime] = None
    description: Optional[str] = None
    author: Optional[str] = None


class ArticleContent(BaseModel):
    """크롤링으로 추출한 기사 본문."""

    title: str
    body: str
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    word_count: int = 0


class Article(BaseModel):
    """RSS 메타데이터 + 크롤링 결과를 통합한 기사 레코드."""

    id: str  # URL의 SHA256 해시 (16자)
    url: str
    source_name: str
    source_key: str
    category: str
    rss_title: str
    content: Optional[ArticleContent] = None
    crawled_at: datetime = Field(default_factory=datetime.now)
    crawl_success: bool = True
    crawl_error: Optional[str] = None


# --- Phase 2에서 사용할 모델 (미리 정의) ---


class BriefingSegment(BaseModel):
    """일일 브리핑의 한 세그먼트."""

    headline: str
    summary: str
    source_articles: list[str] = []  # Article ID 목록
    keywords: list[str] = []


class Briefing(BaseModel):
    """일일 뉴스 브리핑."""

    date: str
    provider: str  # ollama, openai, claude
    segments: list[BriefingSegment] = []
    shorts_script: str = ""
    generated_at: datetime = Field(default_factory=datetime.now)


class WordBoundary(BaseModel):
    """TTS 워드 레벨 타임스탬프."""

    text: str
    offset_ms: int
    duration_ms: int


class TTSResult(BaseModel):
    """TTS 합성 결과."""

    audio_path: str
    word_boundaries: list[WordBoundary] = []
    duration_ms: int = 0
    provider: str


class SubtitleEntry(BaseModel):
    """자막 한 줄."""

    index: int
    start_ms: int
    end_ms: int
    text: str
