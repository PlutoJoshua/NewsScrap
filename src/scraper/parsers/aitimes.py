"""AI타임스 (aitimes.com) 파서 - RSS 없이 HTML 리스트 크롤링."""

from __future__ import annotations

import logging
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from src.scraper.parsers.base_parser import BaseArticleParser
from src.storage.models import ArticleContent, RSSEntry

logger = logging.getLogger(__name__)


class AITimesParser(BaseArticleParser):
    DOMAINS = ("www.aitimes.com", "aitimes.com")

    def can_parse(self, url: str) -> bool:
        return urlparse(url).netloc in self.DOMAINS

    def parse(self, html: str, url: str) -> ArticleContent:
        soup = BeautifulSoup(html, "lxml")

        title_el = soup.select_one("h3.heading, h1.heading, h1")
        title = title_el.get_text(strip=True) if title_el else ""

        body = ""
        article_div = soup.select_one("#article-view-content-div")
        if article_div:
            for tag in article_div.select("script, style, figure, .ad"):
                tag.decompose()
            body = article_div.get_text(separator="\n", strip=True)

        body = self._clean_text(body)

        author = ""
        author_el = soup.select_one(".byline, .writer")
        if author_el:
            author = author_el.get_text(strip=True)

        return ArticleContent(
            title=title,
            body=body,
            author=author,
            word_count=len(body),
        )


class AITimesListScraper:
    """AI타임스 기사 목록 페이지에서 RSSEntry 수집."""

    BASE_URL = "https://www.aitimes.com"

    def fetch_entries(
        self,
        list_url: str,
        source_key: str,
        source_name: str,
        category: str,
        max_articles: int = 20,
        user_agent: str = "",
    ) -> list[RSSEntry]:
        headers = {"User-Agent": user_agent} if user_agent else {}

        try:
            resp = requests.get(list_url, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"AI타임스 목록 수집 실패: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        entries: list[RSSEntry] = []
        seen_urls: set[str] = set()

        # articleView 링크를 직접 탐색 (CSS 클래스가 없는 구조)
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            if "articleView" not in href:
                continue

            title = a_tag.get_text(strip=True)
            if not title:
                continue

            url = urljoin(self.BASE_URL, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            entries.append(
                RSSEntry(
                    title=title,
                    url=url,
                    source_name=source_name,
                    source_key=source_key,
                    category=category,
                )
            )

            if len(entries) >= max_articles:
                break

        logger.info(f"[{source_name}] {len(entries)}건 수집 (HTML 리스트)")
        return entries
