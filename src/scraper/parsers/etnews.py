"""전자신문 (etnews.com) 기사 파서."""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.scraper.parsers.base_parser import BaseArticleParser
from src.storage.models import ArticleContent


class EtnewsParser(BaseArticleParser):
    DOMAINS = ("www.etnews.com", "etnews.com")

    def can_parse(self, url: str) -> bool:
        return urlparse(url).netloc in self.DOMAINS

    def parse(self, html: str, url: str) -> ArticleContent:
        soup = BeautifulSoup(html, "lxml")

        title_el = soup.select_one("h1.title, h1")
        title = title_el.get_text(strip=True) if title_el else ""

        body = ""
        for selector in ("#articleBody", ".article_txt", ".article_body"):
            article_div = soup.select_one(selector)
            if article_div:
                for tag in article_div.select(
                    "script, style, .ad, .related, figure, .reporter_area"
                ):
                    tag.decompose()
                body = article_div.get_text(separator="\n", strip=True)
                break

        body = self._clean_text(body)

        author = ""
        author_el = soup.select_one(".byline, .reporter")
        if author_el:
            author = author_el.get_text(strip=True)

        return ArticleContent(
            title=title,
            body=body,
            author=author,
            word_count=len(body),
        )
