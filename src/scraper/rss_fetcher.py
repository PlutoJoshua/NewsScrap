"""RSS 피드 수집 및 정규화."""

from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import feedparser
import requests

from src.storage.models import RSSEntry

logger = logging.getLogger(__name__)

# URL에서 제거할 트래킹 파라미터
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "ref"}


class RSSFetcher:
    """RSS 피드를 수집하여 RSSEntry 리스트로 반환."""

    def __init__(self, config: dict):
        self.feeds = config["feeds"]
        self.user_agent = config["scraping"]["user_agent"]
        self.max_per_feed = config["scraping"]["max_articles_per_feed"]

    def fetch_all(self) -> list[RSSEntry]:
        """활성화된 모든 RSS 피드를 수집."""
        all_entries: list[RSSEntry] = []

        for key, feed_cfg in self.feeds.items():
            if not feed_cfg.get("enabled", True):
                continue
            # html_list 모드는 별도 처리 (aitimes 등)
            if feed_cfg.get("mode") == "html_list":
                continue

            try:
                entries = self._fetch_feed(key, feed_cfg)
                all_entries.extend(entries)
                logger.info(f"[{feed_cfg['name']}] {len(entries)}건 수집")
            except Exception as e:
                logger.error(f"[{feed_cfg['name']}] 피드 수집 실패: {e}")

        return all_entries

    def _fetch_feed(self, key: str, feed_cfg: dict) -> list[RSSEntry]:
        # requests로 먼저 가져온 뒤 feedparser로 파싱 (SSL 인증서 문제 회피)
        resp = requests.get(
            feed_cfg["url"],
            headers={"User-Agent": self.user_agent},
            timeout=15,
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        if feed.bozo and not feed.entries:
            raise ValueError(f"피드 파싱 오류: {feed.bozo_exception}")

        entries: list[RSSEntry] = []
        for item in feed.entries[: self.max_per_feed]:
            url = _normalize_url(item.get("link", ""))
            title = item.get("title", "").strip()
            if not url or not title:
                continue

            entries.append(
                RSSEntry(
                    title=title,
                    url=url,
                    source_name=feed_cfg["name"],
                    source_key=key,
                    category=feed_cfg.get("category", "general"),
                    published_at=_parse_date(item.get("published")),
                    description=item.get("description", ""),
                    author=item.get("author", ""),
                )
            )

        return entries


def _normalize_url(url: str) -> str:
    """트래킹 파라미터 제거, fragment 제거."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    clean_params = {k: v for k, v in params.items() if k not in _TRACKING_PARAMS}
    return urlunparse(
        parsed._replace(query=urlencode(clean_params, doseq=True), fragment="")
    )


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None
