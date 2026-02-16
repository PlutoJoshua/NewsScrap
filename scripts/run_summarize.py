"""뉴스 요약/브리핑 생성 CLI.

사용법:
    python scripts/run_summarize.py                          # 오늘 기사 요약 (Ollama)
    LLM_PROVIDER=openai python scripts/run_summarize.py      # OpenAI 사용
    LLM_PROVIDER=claude python scripts/run_summarize.py      # Claude 사용
    python scripts/run_summarize.py --date 2026-02-16 --top 5
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from src.storage.json_store import JSONStore
from src.summarizer.factory import create_llm_provider


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config() -> dict:
    with open(PROJECT_ROOT / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    setup_logging()
    logger = logging.getLogger("summarizer")

    parser = argparse.ArgumentParser(description="뉴스 요약/브리핑 생성")
    parser.add_argument("--date", help="대상 날짜 (YYYY-MM-DD)", default=None)
    parser.add_argument("--top", type=int, help="상위 N개 기사만 사용", default=None)
    args = parser.parse_args()

    config = load_config()
    store = JSONStore(config["storage"]["base_dir"])
    target_date = args.date or store.get_today_date()

    # 1. 기사 로드
    articles = store.load_articles(target_date)
    if not articles:
        logger.error(f"{target_date} 날짜의 기사가 없습니다. 먼저 스크래핑을 실행하세요.")
        return

    # 본문이 있는 기사만 필터
    articles_with_body = [
        a for a in articles if a.content and len(a.content.body) > 100
    ]
    logger.info(f"기사 로드: 전체 {len(articles)}건, 본문 있는 기사 {len(articles_with_body)}건")

    # 상위 N개 제한
    top_n = args.top or config["summarizer"]["briefing"]["max_articles"]
    target_articles = articles_with_body[:top_n]
    logger.info(f"브리핑 대상: {len(target_articles)}건")

    # 2. LLM 프로바이더 생성
    try:
        provider = create_llm_provider(config)
    except Exception as e:
        logger.error(f"LLM 프로바이더 초기화 실패: {e}")
        return

    logger.info(f"LLM 프로바이더: {provider.provider_name}")

    # 3. 브리핑 생성
    logger.info("=== 브리핑 생성 중... ===")
    try:
        briefing = provider.generate_briefing(target_articles, target_date)
    except Exception as e:
        logger.error(f"브리핑 생성 실패: {e}")
        return

    # 4. 저장
    briefing_data = briefing.model_dump(mode="json")
    saved_path = store.save_briefing(target_date, briefing_data)

    # 5. 결과 출력
    logger.info("=" * 50)
    logger.info(f"브리핑 생성 완료! (프로바이더: {provider.provider_name})")
    logger.info(f"저장 위치: {saved_path}")

    print("\n" + "=" * 50)
    print(f"📋 {target_date} 브리핑 ({provider.provider_name})")
    print("=" * 50)

    for i, seg in enumerate(briefing.segments, 1):
        print(f"\n[{i}] {seg.headline}")
        print(f"    {seg.summary}")
        if seg.keywords:
            print(f"    키워드: {', '.join(seg.keywords)}")

    print("\n" + "-" * 50)
    print("🎬 숏츠 스크립트:")
    print("-" * 50)
    print(briefing.shorts_script)


if __name__ == "__main__":
    main()
