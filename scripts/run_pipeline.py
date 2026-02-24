"""전체 파이프라인 CLI.

사용법:
    python scripts/run_pipeline.py                        # 뉴스 프로필 (기본)
    python scripts/run_pipeline.py --profile quotes       # 명언 프로필
    python scripts/run_pipeline.py --skip-scrape          # 기존 기사로 요약~영상만
    python scripts/run_pipeline.py --skip-summarize       # 기존 브리핑으로 TTS~영상만
    python scripts/run_pipeline.py --top 3                # 상위 3개 기사만
    python scripts/run_pipeline.py --no-upload            # 업로드 건너뛰기
    python scripts/run_pipeline.py --upload-only          # 기존 영상 업로드만
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from src.config.profile_loader import load_profile_config
from src.pipeline import run_pipeline, upload_existing_video

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def main_async():
    setup_logging()

    parser = argparse.ArgumentParser(description="뉴스/명언 숏츠 파이프라인")
    parser.add_argument(
        "--profile", default="news",
        help="프로필 선택 (예: news, quotes, 커스텀계정)",
    )
    parser.add_argument("--date", help="대상 날짜 (YYYY-MM-DD)", default=None)
    parser.add_argument("--top", type=int, help="상위 N개 기사만 사용 (news만)", default=None)
    parser.add_argument("--skip-scrape", action="store_true", help="스크래핑 건너뛰기 (news만)")
    parser.add_argument("--skip-summarize", action="store_true", help="요약 건너뛰기 (news만)")
    parser.add_argument("--no-upload", action="store_true", help="업로드 건너뛰기")
    parser.add_argument("--upload-only", action="store_true", help="기존 영상 업로드만 실행")
    args = parser.parse_args()

    config = load_profile_config(args.profile)
    target_date = args.date or datetime.now().strftime("%Y-%m-%d")

    logger.info(f"프로필: {args.profile} | 날짜: {target_date}")

    # 파이프라인 종류 판별: config 내용에 따라 결정
    # 명언 파이프라인인지 확인 (pipeline_type 필드나 content.quotes_file 존재 여부)
    is_quotes = config.get("pipeline_type") == "quotes" or "content" in config

    # === 명언 파이프라인 ===
    if is_quotes:
        from src.pipeline_quotes import run_quotes_pipeline

        output = await run_quotes_pipeline(
            config=config,
            date=target_date,
            no_upload=args.no_upload,
        )

        if output:
            print(f"\n✅ 명언 영상 생성 완료: {output}")
        else:
            print("\n❌ 명언 파이프라인 실패")
        return

    # === 뉴스 프로필 ===
    # 업로드만 실행
    if args.upload_only:
        logger.info(f"=== 업로드 전용 모드: {target_date} ===")
        result = upload_existing_video(config, target_date)
        if result:
            print(f"\n✅ 업로드 완료: {result['youtube_url']}")
        else:
            print("\n❌ 업로드 실패")
        return

    output = await run_pipeline(
        config=config,
        date=target_date,
        skip_scrape=args.skip_scrape,
        skip_summarize=args.skip_summarize,
        no_upload=args.no_upload,
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
