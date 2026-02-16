"""기사 중복 제거 (URL + 제목 유사도 기반)."""

from __future__ import annotations

import re
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse

from src.storage.json_store import JSONStore
from src.storage.models import RSSEntry

logger = logging.getLogger(__name__)


class ArticleDeduplicator:
    def __init__(self, config: dict, store: JSONStore):
        self.threshold = config["dedup"]["title_similarity_threshold"]
        self.lookback_days = config["dedup"]["lookback_days"]
        self.store = store

    def filter_duplicates(self, entries: list[RSSEntry]) -> list[RSSEntry]:
        """이전에 수집한 기사 및 배치 내 중복 제거."""
        seen_urls = self._load_seen_urls()
        seen_titles = self._load_seen_titles()

        unique: list[RSSEntry] = []
        batch_urls: set[str] = set()
        batch_titles: list[str] = []

        for entry in entries:
            norm_url = _normalize_url(entry.url)

            if norm_url in seen_urls or norm_url in batch_urls:
                continue

            norm_title = _normalize_title(entry.title)
            if _is_similar(norm_title, seen_titles + batch_titles, self.threshold):
                continue

            batch_urls.add(norm_url)
            batch_titles.append(norm_title)
            unique.append(entry)

        filtered = len(entries) - len(unique)
        if filtered:
            logger.info(f"중복 제거: {filtered}건 필터링, {len(unique)}건 유지")

        return unique

    def _load_seen_urls(self) -> set[str]:
        urls: set[str] = set()
        today = datetime.now()
        for i in range(self.lookback_days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            for a in self.store.load_articles(date):
                urls.add(_normalize_url(a.url))
        return urls

    def _load_seen_titles(self) -> list[str]:
        titles: list[str] = []
        today = datetime.now()
        for i in range(self.lookback_days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            for a in self.store.load_articles(date):
                titles.append(_normalize_title(a.rss_title))
        return titles


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(scheme="https", fragment="", query="")).rstrip("/")


def _normalize_title(title: str) -> str:
    title = re.sub(r"\[.*?\]", "", title)
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _is_similar(title: str, seen: list[str], threshold: float) -> bool:
    tokens = set(title.split())
    if not tokens:
        return False
    for s in seen:
        s_tokens = set(s.split())
        if not s_tokens:
            continue
        intersection = tokens & s_tokens
        union = tokens | s_tokens
        if len(intersection) / len(union) >= threshold:
            return True
    return False
