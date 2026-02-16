"""조선일보/조선비즈 기사 파서."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.scraper.parsers.base_parser import BaseArticleParser
from src.storage.models import ArticleContent


class ChosunParser(BaseArticleParser):
    DOMAINS = (
        "www.chosun.com",
        "chosun.com",
        "biz.chosun.com",
    )

    def can_parse(self, url: str) -> bool:
        return urlparse(url).netloc in self.DOMAINS

    def parse(self, html: str, url: str) -> ArticleContent:
        soup = BeautifulSoup(html, "lxml")

        # JSON-LD 우선
        content = self._try_jsonld(soup)
        if content and content.body:
            return content

        return self._parse_dom(soup)

    def _try_jsonld(self, soup: BeautifulSoup) -> Optional[ArticleContent]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") not in ("NewsArticle", "Article"):
                    continue
                body = self._clean_text(data.get("articleBody", ""))
                if not body:
                    continue
                return ArticleContent(
                    title=data.get("headline", ""),
                    body=body,
                    author=self._get_author(data),
                    published_at=_parse_iso(data.get("datePublished")),
                    word_count=len(body),
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    def _parse_dom(self, soup: BeautifulSoup) -> ArticleContent:
        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        # 조선일보 본문 셀렉터들
        body = ""
        for selector in (
            "section.article-body",
            ".article_body",
            "#articleBody",
            ".news_text",
        ):
            article_div = soup.select_one(selector)
            if article_div:
                for tag in article_div.select("script, style, figure, .ad"):
                    tag.decompose()
                body = article_div.get_text(separator="\n", strip=True)
                break

        body = self._clean_text(body)
        return ArticleContent(title=title, body=body, word_count=len(body))

    @staticmethod
    def _get_author(data: dict) -> str:
        author = data.get("author", {})
        if isinstance(author, list):
            return ", ".join(a.get("name", "") for a in author if a.get("name"))
        if isinstance(author, dict):
            return author.get("name", "")
        return ""


def _parse_iso(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None
