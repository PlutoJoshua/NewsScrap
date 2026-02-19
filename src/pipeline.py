"""전체 파이프라인 오케스트레이터: 스크래핑 → 요약 → TTS → 자막 → 영상 → 업로드."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from itertools import islice
from pathlib import Path

from src.storage.json_store import JSONStore
from src.storage.models import Article, Briefing
from src.subtitles.subtitle_generator import generate_subtitles, write_srt
from src.summarizer.factory import create_llm_provider
from src.tts.factory import create_tts_provider
from src.video.background import download_backgrounds_for_segments
from src.video.composer import compose_shorts

logger = logging.getLogger(__name__)


async def run_pipeline(
    config: dict,
    date: str,
    skip_scrape: bool = False,
    skip_summarize: bool = False,
    no_upload: bool = False,
    top_n: int | None = None,
) -> str | None:
    """전체 파이프라인 실행. 최종 영상 경로 반환."""
    store = JSONStore(config["storage"]["base_dir"])
    base_dir = Path(config["storage"]["base_dir"])

    # === Phase 1: 스크래핑 ===
    if not skip_scrape:
        logger.info("=== Phase 1: 스크래핑 ===")
        from scripts.run_scrape import run_scrape
        run_scrape(config, date)

    # === Phase 2: 요약 ===
    briefing: Briefing | None = None

    if not skip_summarize:
        logger.info("=== Phase 2: AI 요약 ===")
        articles = store.load_articles(date)
        articles_with_body = [
            a for a in articles if a.content and len(a.content.body) > 100
        ]

        if not articles_with_body:
            logger.error("본문이 있는 기사가 없습니다.")
            return None

        max_articles = top_n or config["summarizer"]["briefing"]["max_articles"]
        target_articles = _select_diverse_articles(articles_with_body, max_articles)

        provider = create_llm_provider(config)
        logger.info(f"LLM: {provider.provider_name}, 기사: {len(target_articles)}건")
        briefing = provider.generate_briefing(target_articles, date)
        store.save_briefing(date, briefing.model_dump(mode="json"))
    else:
        # 기존 브리핑 로드
        import json
        briefing_path = base_dir / "summaries" / date / "briefing.json"
        if briefing_path.exists():
            with open(briefing_path, "r", encoding="utf-8") as f:
                briefing = Briefing.model_validate(json.load(f))
        else:
            logger.error(f"브리핑 파일 없음: {briefing_path}")
            return None

    if not briefing or not briefing.shorts_script:
        logger.error("숏츠 스크립트가 비어있습니다.")
        return None

    # === Phase 3: TTS ===
    logger.info("=== Phase 3: TTS 음성 생성 ===")
    audio_dir = base_dir / "audio" / date
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = str(audio_dir / "briefing.mp3")

    tts_provider = create_tts_provider(config)
    logger.info(f"TTS: {tts_provider.provider_name}")
    tts_result = await tts_provider.synthesize(briefing.shorts_script, audio_path)

    # === Phase 4: 자막 ===
    logger.info("=== Phase 4: 자막 생성 ===")
    subtitles = generate_subtitles(tts_result)
    srt_dir = base_dir / "subtitles" / date
    srt_path = str(srt_dir / "briefing.srt")
    write_srt(subtitles, srt_path)

    # === Phase 5: 영상 합성 ===
    logger.info("=== Phase 5: 영상 합성 ===")
    bg_paths = download_backgrounds_for_segments(
        segments=briefing.segments,
        output_dir=str(base_dir / "videos"),
    )

    output_dir = base_dir / "output" / date
    output_path = str(output_dir / f"news_shorts_{date}.mp4")

    title = f"📰 {date} 경제 브리핑"
    compose_shorts(
        audio_path=audio_path,
        subtitles=subtitles,
        background_paths=bg_paths,
        output_path=output_path,
        segments=briefing.segments,
        word_boundaries=tts_result.word_boundaries,
        title_text=title,
    )

    logger.info(f"🎬 최종 영상: {output_path}")

    # === Phase 6: YouTube 업로드 ===
    upload_enabled = config.get("uploader", {}).get("enabled", False)
    if upload_enabled and not no_upload:
        logger.info("=== Phase 6: YouTube 업로드 ===")
        from src.uploader.youtube_uploader import YouTubeUploader

        uploader = YouTubeUploader(config["uploader"]["youtube"])
        result = uploader.upload(
            video_path=output_path,
            briefing=briefing,
            date=date,
            output_dir=str(base_dir / "uploads" / date),
        )
        logger.info(f"📺 업로드 완료: {result['youtube_url']}")

    return output_path


def upload_existing_video(config: dict, date: str) -> dict | None:
    """기존 영상을 YouTube에 업로드만 실행."""
    base_dir = Path(config["storage"]["base_dir"])
    output_path = base_dir / "output" / date / f"news_shorts_{date}.mp4"

    if not output_path.exists():
        logger.error(f"영상 파일 없음: {output_path}")
        return None

    # 브리핑 로드
    briefing_path = base_dir / "summaries" / date / "briefing.json"
    if not briefing_path.exists():
        logger.error(f"브리핑 파일 없음: {briefing_path}")
        return None

    with open(briefing_path, "r", encoding="utf-8") as f:
        briefing = Briefing.model_validate(json.load(f))

    from src.uploader.youtube_uploader import YouTubeUploader

    uploader = YouTubeUploader(config["uploader"]["youtube"])
    result = uploader.upload(
        video_path=str(output_path),
        briefing=briefing,
        date=date,
        output_dir=str(base_dir / "uploads" / date),
    )
    logger.info(f"📺 업로드 완료: {result['youtube_url']}")
    return result


def _select_diverse_articles(
    articles: list[Article], max_count: int
) -> list[Article]:
    """소스별 라운드로빈으로 다양한 기사를 선택."""
    by_source: dict[str, list[Article]] = defaultdict(list)
    for a in articles:
        by_source[a.source_name].append(a)

    selected: list[Article] = []
    iterators = {src: iter(arts) for src, arts in by_source.items()}

    while len(selected) < max_count and iterators:
        exhausted = []
        for src, it in iterators.items():
            if len(selected) >= max_count:
                break
            article = next(it, None)
            if article is None:
                exhausted.append(src)
            else:
                selected.append(article)
        for src in exhausted:
            del iterators[src]

    return selected
