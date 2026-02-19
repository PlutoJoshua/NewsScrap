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

from src.storage.models import BriefingSegment, SubtitleEntry, WordBoundary

logger = logging.getLogger(__name__)

# 영상 스펙
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# 세그먼트별 ColorClip 폴백 색상
_SEGMENT_COLORS = [
    (20, 20, 40),  # dark navy
    (30, 20, 30),  # dark purple
    (20, 30, 30),  # dark teal
    (25, 25, 25),  # dark gray
    (30, 20, 20),  # dark maroon
]


def compose_shorts(
    audio_path: str,
    subtitles: list[SubtitleEntry],
    background_paths: list[str | None],
    output_path: str,
    segments: list[BriefingSegment] | None = None,
    word_boundaries: list[WordBoundary] | None = None,
    title_text: str = "",
    title_duration: float = 3.0,
    crossfade_duration: float = 0.5,
) -> str:
    """숏츠 영상을 합성하여 MP4로 출력."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 1. 오디오 로드
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    logger.info(f"오디오 길이: {total_duration:.1f}초")

    # 2. 배경 영상 생성
    if segments and len(background_paths) > 1 and len(background_paths) == len(segments):
        # 멀티 배경: 세그먼트별 배경 전환
        time_ranges = compute_segment_time_ranges(
            segments,
            int(total_duration * 1000),
            word_boundaries,
            title_duration_ms=int(title_duration * 1000) if title_text else 0,
        )
        bg = _make_multi_background(
            background_paths, time_ranges, total_duration, crossfade_duration,
        )
        logger.info(f"멀티 배경: {len(segments)}개 세그먼트")
    else:
        # 단일 배경 폴백
        bg_path = background_paths[0] if background_paths else None
        if bg_path and Path(bg_path).exists():
            bg = _make_background_from_video(bg_path, total_duration)
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


def compute_segment_time_ranges(
    segments: list[BriefingSegment],
    total_duration_ms: int,
    word_boundaries: list[WordBoundary] | None = None,
    title_duration_ms: int = 3000,
) -> list[tuple[int, int]]:
    """세그먼트별 (start_ms, end_ms) 계산. summary 길이 비례 분배."""
    if not segments:
        return [(title_duration_ms, total_duration_ms)]

    available_ms = total_duration_ms - title_duration_ms

    # summary 길이 비례
    lengths = [len(seg.summary) for seg in segments]
    total_len = sum(lengths) or 1

    ranges: list[tuple[int, int]] = []
    current_ms = title_duration_ms

    for i, seg in enumerate(segments):
        proportion = lengths[i] / total_len
        segment_duration = int(available_ms * proportion)

        end_ms = current_ms + segment_duration
        if i == len(segments) - 1:
            end_ms = total_duration_ms

        # 문장 경계로 스냅
        if word_boundaries and i < len(segments) - 1:
            end_ms = _snap_to_boundary(end_ms, word_boundaries, tolerance_ms=2000)

        ranges.append((current_ms, end_ms))
        current_ms = end_ms

    logger.info(
        "세그먼트 시간 분할: "
        + ", ".join(f"{s/1000:.1f}-{e/1000:.1f}s" for s, e in ranges)
    )
    return ranges


def _snap_to_boundary(
    target_ms: int,
    boundaries: list[WordBoundary],
    tolerance_ms: int,
) -> int:
    """target_ms에 가장 가까운 문장 경계로 스냅."""
    best_ms = target_ms
    best_diff = tolerance_ms + 1

    for wb in boundaries:
        boundary_end = wb.offset_ms + wb.duration_ms
        diff = abs(boundary_end - target_ms)
        if diff < best_diff:
            best_diff = diff
            best_ms = boundary_end

    return best_ms


def _make_multi_background(
    paths: list[str | None],
    time_ranges: list[tuple[int, int]],
    total_duration: float,
    crossfade_dur: float = 0.5,
) -> CompositeVideoClip:
    """세그먼트별 배경 클립을 연결하여 하나의 배경 생성."""
    clips = []

    for i, (path, (start_ms, end_ms)) in enumerate(zip(paths, time_ranges)):
        segment_duration = (end_ms - start_ms) / 1000.0
        if segment_duration <= 0:
            continue

        if path and Path(path).exists():
            clip = _make_background_from_video(path, segment_duration)
        else:
            color = _SEGMENT_COLORS[i % len(_SEGMENT_COLORS)]
            clip = ColorClip(size=(WIDTH, HEIGHT), color=color).with_duration(segment_duration)

        clips.append(clip)

    if not clips:
        return ColorClip(size=(WIDTH, HEIGHT), color=(20, 20, 30)).with_duration(total_duration)

    if len(clips) == 1:
        return clips[0].with_duration(total_duration)

    # 크로스페이드 전환으로 연결
    if crossfade_dur > 0:
        result = concatenate_videoclips(
            clips, method="compose", padding=-crossfade_dur,
        )
    else:
        result = concatenate_videoclips(clips, method="compose")

    return result.with_duration(total_duration)


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


def compose_quote_shorts(
    audio_path: str,
    subtitles: list[SubtitleEntry],
    background_path: str | None,
    output_path: str,
    quote_text: str,
    author: str,
    quote_display_duration: float = 5.0,
) -> str:
    """명언 숏츠 영상 합성.

    레이아웃 (1080x1920):
    - 배경: 자연/추상 영상 + 반투명 어두운 오버레이
    - 명언 텍스트: 중앙 상단 (y=500), 72px, 흰색
    - 저자: 명언 아래, 40px, 금색
    - 해설 자막: 하단 (y=1570), 44px
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 1. 오디오 로드
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    logger.info(f"오디오 길이: {total_duration:.1f}초")

    # 2. 배경 영상
    if background_path and Path(background_path).exists():
        bg = _make_background_from_video(background_path, total_duration)
    else:
        bg = ColorClip(size=(WIDTH, HEIGHT), color=(15, 15, 25)).with_duration(total_duration)

    # 3. 반투명 어두운 오버레이 (가독성 향상)
    overlay = (
        ColorClip(size=(WIDTH, HEIGHT), color=(0, 0, 0))
        .with_duration(total_duration)
        .with_opacity(0.4)
    )

    clips = [bg, overlay]

    # 4. 명언 텍스트 (0~quote_display_duration초)
    try:
        quote_clip = (
            TextClip(
                text=f'"{quote_text}"',
                font_size=64,
                color="white",
                font="config/fonts/AppleSDGothicNeo-Bold.ttf",
                stroke_color="black",
                stroke_width=3,
                size=(WIDTH - 120, None),
                method="caption",
            )
            .with_position(("center", 500))
            .with_start(0)
            .with_duration(quote_display_duration)
        )
        clips.append(quote_clip)
    except Exception as e:
        logger.warning(f"명언 텍스트 클립 생성 실패: {e}")

    # 5. 저자 텍스트
    try:
        author_clip = (
            TextClip(
                text=f"- {author}",
                font_size=40,
                color="#FFD700",
                font="config/fonts/AppleSDGothicNeo-Bold.ttf",
                size=(WIDTH - 200, None),
                method="caption",
            )
            .with_position(("center", 750))
            .with_start(0)
            .with_duration(quote_display_duration)
        )
        clips.append(author_clip)
    except Exception as e:
        logger.warning(f"저자 텍스트 클립 생성 실패: {e}")

    # 6. 해설 자막 오버레이
    for entry in subtitles:
        start = entry.start_ms / 1000.0
        end = entry.end_ms / 1000.0
        if end > total_duration:
            end = total_duration

        try:
            sub_clip = (
                TextClip(
                    text=entry.text,
                    font_size=44,
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

    # 7. 합성 및 렌더링
    video = CompositeVideoClip(clips, size=(WIDTH, HEIGHT))
    video = video.with_audio(audio).with_duration(total_duration)

    logger.info(f"영상 렌더링 중... → {output_path}")
    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        logger=None,
    )

    audio.close()
    video.close()

    logger.info(f"명언 영상 생성 완료: {output_path}")
    return output_path


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
