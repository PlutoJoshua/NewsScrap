"""뉴스 스크래핑 CLI 진입점.

사용법:
    python scripts/run_scrape.py                 # 오늘 날짜로 전체 스크래핑
    python scripts/run_scrape.py --date 2026-02-16
    python scripts/run_scrape.py --feeds hankyung_economy,etnews_ai
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.scraper.article_crawler import ArticleCrawler
from src.scraper.dedup import ArticleDeduplicator
from src.scraper.parsers.aitimes import AITimesListScraper, AITimesParser
from src.scraper.parsers.chosun import ChosunParser
from src.scraper.parsers.etnews import EtnewsParser
from src.scraper.parsers.generic import GenericParser
from src.scraper.parsers.hankyung import HankyungParser
from src.scraper.rss_fetcher import RSSFetcher
from src.storage.json_store import JSONStore


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config(config_path: str = "config/config.yaml") -> dict:
    path = PROJECT_ROOT / config_path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_parsers() -> list:
    """사이트별 파서 리스트 (GenericParser는 마지막)."""
    return [
        HankyungParser(),
        ChosunParser(),
        EtnewsParser(),
        AITimesParser(),
        GenericParser(),  # 폴백 - 항상 마지막
    ]


def run_scrape(config: dict, target_date: str, feed_filter: list[str] | None = None):
    logger = logging.getLogger("scraper")

    store = JSONStore(config["storage"]["base_dir"])

    # 특정 피드만 필터링
    if feed_filter:
        config = {**config}
        config["feeds"] = {
            k: v for k, v in config["feeds"].items() if k in feed_filter
        }

    # 1. RSS 피드 수집
    logger.info("=== Phase 1: RSS 피드 수집 ===")
    rss_fetcher = RSSFetcher(config)
    entries = rss_fetcher.fetch_all()
    logger.info(f"RSS에서 총 {len(entries)}건 수집")

    # 1-1. HTML 리스트 소스 수집 (aitimes 등)
    for key, feed_cfg in config["feeds"].items():
        if feed_cfg.get("mode") != "html_list" or not feed_cfg.get("enabled", True):
            continue
        scraper = AITimesListScraper()
        html_entries = scraper.fetch_entries(
            list_url=feed_cfg["url"],
            source_key=key,
            source_name=feed_cfg["name"],
            category=feed_cfg.get("category", "ai"),
            max_articles=config["scraping"]["max_articles_per_feed"],
            user_agent=config["scraping"]["user_agent"],
        )
        entries.extend(html_entries)

    logger.info(f"전체 수집: {len(entries)}건")

    # 2. 중복 제거
    logger.info("=== Phase 2: 중복 제거 ===")
    dedup = ArticleDeduplicator(config, store)
    unique_entries = dedup.filter_duplicates(entries)
    logger.info(f"중복 제거 후: {len(unique_entries)}건")

    if not unique_entries:
        logger.info("새로운 기사가 없습니다.")
        return

    # 3. 본문 크롤링
    logger.info("=== Phase 3: 본문 크롤링 ===")
    parsers = create_parsers()
    crawler = ArticleCrawler(config, parsers)
    articles = crawler.crawl_articles(unique_entries)

    # 4. 저장
    logger.info("=== Phase 4: 저장 ===")
    saved_path = store.save_articles(target_date, articles)

    # 결과 요약
    success = sum(1 for a in articles if a.crawl_success)
    with_body = sum(
        1 for a in articles if a.content and len(a.content.body) > 100
    )

    logger.info("=" * 50)
    logger.info(f"스크래핑 완료!")
    logger.info(f"  총 기사: {len(articles)}건")
    logger.info(f"  크롤링 성공: {success}건")
    logger.info(f"  본문 추출 성공 (100자+): {with_body}건")
    logger.info(f"  저장 위치: {saved_path}")


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="경제/AI 뉴스 스크래핑")
    parser.add_argument("--date", help="저장 날짜 (YYYY-MM-DD)", default=None)
    parser.add_argument("--feeds", help="수집할 피드 (쉼표 구분)", default=None)
    parser.add_argument("--config", help="설정 파일 경로", default="config/config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)

    store = JSONStore(config["storage"]["base_dir"])
    target_date = args.date or store.get_today_date()

    feed_filter = args.feeds.split(",") if args.feeds else None

    run_scrape(config, target_date, feed_filter)


if __name__ == "__main__":
    main()
