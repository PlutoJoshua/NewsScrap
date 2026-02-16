"""기사 본문 크롤링 - HTTP 요청 + 파서 디스패치 + 재시도."""

from __future__ import annotations

import hashlib
import logging
import time

import requests
from bs4 import BeautifulSoup

from src.scraper.parsers.base_parser import BaseArticleParser
from src.scraper.rate_limiter import RateLimiter
from src.storage.models import Article, ArticleContent, RSSEntry

logger = logging.getLogger(__name__)


class ArticleCrawler:
    def __init__(self, config: dict, parsers: list[BaseArticleParser]):
        self.scraping_cfg = config["scraping"]
        self.parsers = parsers
        self.rate_limiter = RateLimiter(self.scraping_cfg["rate_limit_per_domain"])
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": self.scraping_cfg["user_agent"],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        return session

    def crawl_articles(self, entries: list[RSSEntry]) -> list[Article]:
        """RSSEntry 리스트의 본문을 크롤링하여 Article 리스트 반환."""
        articles: list[Article] = []
        total = len(entries)

        for i, entry in enumerate(entries, 1):
            logger.info(f"[{i}/{total}] {entry.source_name}: {entry.title[:40]}...")
            article = self._crawl_single(entry)
            articles.append(article)

        success = sum(1 for a in articles if a.crawl_success)
        logger.info(f"크롤링 완료: {success}/{total}건 성공")
        return articles

    def _crawl_single(self, entry: RSSEntry) -> Article:
        article_id = hashlib.sha256(entry.url.encode()).hexdigest()[:16]

        article = Article(
            id=article_id,
            url=entry.url,
            source_name=entry.source_name,
            source_key=entry.source_key,
            category=entry.category,
            rss_title=entry.title,
        )

        try:
            self.rate_limiter.wait(entry.url)
            response = self._fetch_with_retry(entry.url)
            html = response.text

            parser = self._find_parser(entry.url)
            content = parser.parse(html, entry.url)

            # 파서가 본문 추출 실패 시 RSS description 폴백
            if not content.body and entry.description:
                content.body = _strip_html(entry.description)
                content.word_count = len(content.body)

            if not content.title:
                content.title = entry.title

            article.content = content
            article.crawl_success = True

        except Exception as e:
            logger.warning(f"크롤링 실패 [{entry.url}]: {e}")
            article.crawl_success = False
            article.crawl_error = str(e)

            # RSS description으로 최소 콘텐츠 생성
            if entry.description:
                article.content = ArticleContent(
                    title=entry.title,
                    body=_strip_html(entry.description),
                    published_at=entry.published_at,
                    author=entry.author or "",
                    word_count=len(entry.description),
                )

        return article

    def _fetch_with_retry(self, url: str) -> requests.Response:
        max_retries = self.scraping_cfg["max_retries"]
        backoff = self.scraping_cfg["retry_backoff"]

        for attempt in range(max_retries):
            try:
                resp = self.session.get(
                    url, timeout=self.scraping_cfg["request_timeout"]
                )
                resp.raise_for_status()
                if resp.encoding is None or resp.encoding == "ISO-8859-1":
                    resp.encoding = resp.apparent_encoding or "utf-8"
                return resp
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                wait = backoff ** attempt
                logger.debug(f"재시도 {attempt + 1}/{max_retries} [{url}]: {e}")
                time.sleep(wait)

        raise RuntimeError("unreachable")

    def _find_parser(self, url: str) -> BaseArticleParser:
        for parser in self.parsers:
            if parser.can_parse(url):
                return parser
        return self.parsers[-1]  # GenericParser (폴백)


def _strip_html(text: str) -> str:
    return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
