"""한국경제 (hankyung.com) 기사 파서."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.scraper.parsers.base_parser import BaseArticleParser
from src.storage.models import ArticleContent


class HankyungParser(BaseArticleParser):
    DOMAINS = ("www.hankyung.com", "hankyung.com")

    def can_parse(self, url: str) -> bool:
        return urlparse(url).netloc in self.DOMAINS

    def parse(self, html: str, url: str) -> ArticleContent:
        soup = BeautifulSoup(html, "lxml")

        # JSON-LD 구조화 데이터 우선 시도
        content = self._try_jsonld(soup)
        if content and content.body:
            return content

        # DOM 파싱 폴백
        return self._parse_dom(soup)

    def _try_jsonld(self, soup: BeautifulSoup) -> Optional[ArticleContent]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") != "NewsArticle":
                    continue
                body = self._clean_text(data.get("articleBody", ""))
                if not body:
                    continue
                return ArticleContent(
                    title=data.get("headline", ""),
                    body=body,
                    author=self._extract_author_jsonld(data),
                    published_at=_parse_iso(data.get("datePublished")),
                    image_url=_extract_image(data),
                    word_count=len(body),
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    def _parse_dom(self, soup: BeautifulSoup) -> ArticleContent:
        title_el = soup.select_one("h1.headline, h1")
        title = title_el.get_text(strip=True) if title_el else ""

        article_div = soup.select_one("#articletxt")
        body = ""
        if article_div:
            for tag in article_div.select("script, style, .ad, .related, figure"):
                tag.decompose()
            paragraphs = article_div.find_all(
                ["p", "div"], class_=re.compile(r"paragraph")
            )
            if paragraphs:
                body = "\n".join(
                    p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
                )
            else:
                body = article_div.get_text(separator="\n", strip=True)

        body = self._clean_text(body)
        return ArticleContent(title=title, body=body, word_count=len(body))

    @staticmethod
    def _extract_author_jsonld(data: dict) -> str:
        author = data.get("author", {})
        if isinstance(author, list):
            return ", ".join(a.get("name", "") for a in author)
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


def _extract_image(data: dict) -> Optional[str]:
    image = data.get("image")
    if isinstance(image, str):
        return image
    if isinstance(image, dict):
        return image.get("url")
    if isinstance(image, list) and image:
        first = image[0]
        return first if isinstance(first, str) else first.get("url")
    return None
