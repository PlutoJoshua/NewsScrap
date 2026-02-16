"""범용 폴백 파서 (newspaper3k 기반)."""

from __future__ import annotations

from newspaper import Article as NP3Article

from src.scraper.parsers.base_parser import BaseArticleParser
from src.storage.models import ArticleContent


class GenericParser(BaseArticleParser):
    """전용 파서가 없는 사이트용 폴백."""

    def can_parse(self, url: str) -> bool:
        return True  # 항상 매칭 - 리스트 마지막에 배치

    def parse(self, html: str, url: str) -> ArticleContent:
        article = NP3Article(url, language="ko")
        article.set_html(html)
        article.parse()

        body = self._clean_text(article.text)

        return ArticleContent(
            title=article.title or "",
            body=body,
            author=", ".join(article.authors) if article.authors else "",
            published_at=article.publish_date,
            image_url=article.top_image,
            word_count=len(body),
        )
