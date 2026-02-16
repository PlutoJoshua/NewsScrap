"""전체 파이프라인 CLI.

사용법:
    python scripts/run_pipeline.py                        # 전체 파이프라인
    python scripts/run_pipeline.py --skip-scrape          # 기존 기사로 요약~영상만
    python scripts/run_pipeline.py --skip-summarize       # 기존 브리핑으로 TTS~영상만
    python scripts/run_pipeline.py --top 3                # 상위 3개 기사만
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from src.pipeline import run_pipeline
from src.storage.json_store import JSONStore


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config() -> dict:
    with open(PROJECT_ROOT / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main_async():
    setup_logging()

    parser = argparse.ArgumentParser(description="뉴스 숏츠 전체 파이프라인")
    parser.add_argument("--date", help="대상 날짜 (YYYY-MM-DD)", default=None)
    parser.add_argument("--top", type=int, help="상위 N개 기사만 사용", default=None)
    parser.add_argument("--skip-scrape", action="store_true", help="스크래핑 건너뛰기")
    parser.add_argument("--skip-summarize", action="store_true", help="요약 건너뛰기")
    args = parser.parse_args()

    config = load_config()
    store = JSONStore(config["storage"]["base_dir"])
    target_date = args.date or store.get_today_date()

    output = await run_pipeline(
        config=config,
        date=target_date,
        skip_scrape=args.skip_scrape,
        skip_summarize=args.skip_summarize,
        top_n=args.top,
    )

    if output:
        print(f"\n✅ 영상 생성 완료: {output}")
    else:
        print("\n❌ 파이프라인 실패")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
