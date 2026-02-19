"""명언 숏츠 파이프라인: 명언선택 → 스크립트생성 → TTS → 자막 → 영상 → 업로드."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.content.quotes_picker import QuotesPicker
from src.subtitles.subtitle_generator import generate_subtitles, write_srt
from src.summarizer.factory import create_llm_provider
from src.summarizer.prompt_templates import QUOTE_SCRIPT_PROMPT
from src.tts.factory import create_tts_provider
from src.video.background import download_background_for_quote
from src.video.composer import compose_quote_shorts

logger = logging.getLogger(__name__)


async def run_quotes_pipeline(
    config: dict,
    date: str,
    no_upload: bool = False,
) -> str | None:
    """명언 숏츠 파이프라인 실행. 최종 영상 경로 반환."""
    base_dir = Path(config["storage"]["base_dir"])

    # === Phase 1: 명언 선택 ===
    logger.info("=== Phase 1: 명언 선택 ===")
    picker = QuotesPicker(config["content"]["quotes_file"])
    quote = picker.pick(date)
    logger.info(f"선택된 명언: \"{quote['text']}\" - {quote['author']}")

    # 선택 결과 저장
    selected_dir = base_dir / "selected" / date
    selected_dir.mkdir(parents=True, exist_ok=True)
    with open(selected_dir / "quote.json", "w", encoding="utf-8") as f:
        json.dump(quote, f, indent=2, ensure_ascii=False)

    # === Phase 2: LLM 해설 스크립트 생성 ===
    logger.info("=== Phase 2: 해설 스크립트 생성 ===")
    provider = create_llm_provider(config)
    prompt = QUOTE_SCRIPT_PROMPT.format(
        quote_text=quote["text"],
        author=quote["author"],
    )
    script = provider.generate_text(prompt, max_tokens=512)
    logger.info(f"스크립트 생성 완료 ({len(script)}자)")

    # 스크립트 저장
    script_dir = base_dir / "scripts" / date
    script_dir.mkdir(parents=True, exist_ok=True)
    script_data = {
        "quote_id": quote["id"],
        "quote_text": quote["text"],
        "author": quote["author"],
        "category": quote.get("category", ""),
        "script": script,
    }
    with open(script_dir / "script.json", "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    # === Phase 3: TTS ===
    logger.info("=== Phase 3: TTS 음성 생성 ===")
    audio_dir = base_dir / "audio" / date
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = str(audio_dir / "narration.mp3")

    tts_provider = create_tts_provider(config)
    logger.info(f"TTS: {tts_provider.provider_name}")
    tts_result = await tts_provider.synthesize(script, audio_path)

    # === Phase 4: 자막 ===
    logger.info("=== Phase 4: 자막 생성 ===")
    subtitles = generate_subtitles(tts_result)
    srt_dir = base_dir / "subtitles" / date
    srt_path = str(srt_dir / "narration.srt")
    write_srt(subtitles, srt_path)

    # === Phase 5: 영상 합성 ===
    logger.info("=== Phase 5: 영상 합성 (명언 스타일) ===")
    bg_path = download_background_for_quote(
        output_dir=str(base_dir / "videos"),
    )

    output_dir = base_dir / "output" / date
    output_path = str(output_dir / f"quotes_shorts_{date}.mp4")

    compose_quote_shorts(
        audio_path=audio_path,
        subtitles=subtitles,
        background_path=bg_path,
        output_path=output_path,
        quote_text=quote["text"],
        author=quote["author"],
    )

    logger.info(f"🎬 최종 영상: {output_path}")

    # === Phase 6: YouTube 업로드 ===
    upload_enabled = config.get("uploader", {}).get("enabled", False)
    if upload_enabled and not no_upload:
        logger.info("=== Phase 6: YouTube 업로드 ===")
        from src.uploader.youtube_uploader import YouTubeUploader

        uploader = YouTubeUploader(config["uploader"]["youtube"])
        result = uploader.upload_quote(
            video_path=output_path,
            quote=quote,
            date=date,
            output_dir=str(base_dir / "uploads" / date),
        )
        logger.info(f"📺 업로드 완료: {result['youtube_url']}")

    return output_path
