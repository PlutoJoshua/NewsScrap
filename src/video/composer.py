"""moviepy 기반 숏츠 영상 합성 (9:16, 1080x1920)."""

from __future__ import annotations

import logging
from pathlib import Path

from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from src.storage.models import SubtitleEntry

logger = logging.getLogger(__name__)

# 영상 스펙
WIDTH = 1080
HEIGHT = 1920
FPS = 30


def compose_shorts(
    audio_path: str,
    subtitles: list[SubtitleEntry],
    background_path: str | None,
    output_path: str,
    title_text: str = "",
    title_duration: float = 3.0,
) -> str:
    """숏츠 영상을 합성하여 MP4로 출력."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 1. 오디오 로드
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    logger.info(f"오디오 길이: {total_duration:.1f}초")

    # 2. 배경 영상 생성
    if background_path and Path(background_path).exists():
        bg = _make_background_from_video(background_path, total_duration)
    else:
        logger.info("배경 영상 없음 - 단색 배경 사용")
        bg = ColorClip(size=(WIDTH, HEIGHT), color=(20, 20, 30)).with_duration(total_duration)

    # 3. 타이틀 카드
    clips = [bg]
    if title_text:
        title_clip = _make_title_card(title_text, title_duration)
        clips.append(title_clip)

    # 4. 자막 오버레이
    for entry in subtitles:
        start = entry.start_ms / 1000.0
        end = entry.end_ms / 1000.0
        if end > total_duration:
            end = total_duration

        try:
            sub_clip = (
                TextClip(
                    text=entry.text,
                    font_size=48,
                    color="white",
                    font="config/fonts/AppleSDGothicNeo-Bold.ttf",
                    stroke_color="black",
                    stroke_width=2,
                    size=(WIDTH - 100, None),
                    method="caption",
                )
                .with_position(("center", HEIGHT - 350))
                .with_start(start)
                .with_duration(end - start)
            )
            clips.append(sub_clip)
        except Exception as e:
            logger.debug(f"자막 클립 생성 실패: {e}")

    # 5. 합성
    video = CompositeVideoClip(clips, size=(WIDTH, HEIGHT))
    video = video.with_audio(audio).with_duration(total_duration)

    # 6. 렌더링
    logger.info(f"영상 렌더링 중... → {output_path}")
    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        logger=None,
    )

    # cleanup
    audio.close()
    video.close()

    logger.info(f"영상 생성 완료: {output_path}")
    return output_path


def _make_background_from_video(video_path: str, duration: float) -> VideoFileClip:
    """배경 영상을 9:16으로 크롭/리사이즈하고 루프."""
    clip = VideoFileClip(video_path)

    # 9:16 비율로 크롭
    src_w, src_h = clip.size
    target_ratio = WIDTH / HEIGHT  # 0.5625

    if src_w / src_h > target_ratio:
        # 소스가 더 넓음 → 좌우 크롭
        new_w = int(src_h * target_ratio)
        x_offset = (src_w - new_w) // 2
        clip = clip.cropped(x1=x_offset, x2=x_offset + new_w)
    else:
        # 소스가 더 좁음 → 상하 크롭
        new_h = int(src_w / target_ratio)
        y_offset = (src_h - new_h) // 2
        clip = clip.cropped(y1=y_offset, y2=y_offset + new_h)

    clip = clip.resized((WIDTH, HEIGHT))

    # 영상이 짧으면 루프
    if clip.duration < duration:
        repeats = int(duration / clip.duration) + 1
        clip = concatenate_videoclips([clip] * repeats)

    return clip.with_duration(duration)


def _make_title_card(text: str, duration: float) -> TextClip:
    """타이틀 카드 오버레이."""
    return (
        TextClip(
            text=text,
            font_size=56,
            color="white",
            font="config/fonts/AppleSDGothicNeo-Bold.ttf",
            stroke_color="black",
            stroke_width=3,
            size=(WIDTH - 120, None),
            method="caption",
        )
        .with_position(("center", 300))
        .with_start(0)
        .with_duration(duration)
    )
