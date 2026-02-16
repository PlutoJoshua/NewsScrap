"""TTS 타임스탬프 기반 자막 생성."""

from __future__ import annotations

import logging
from pathlib import Path

from src.storage.models import SubtitleEntry, TTSResult

logger = logging.getLogger(__name__)

DEFAULT_CHARS_PER_SEGMENT = 15


def generate_subtitles(
    tts_result: TTSResult,
    chars_per_segment: int = DEFAULT_CHARS_PER_SEGMENT,
) -> list[SubtitleEntry]:
    """TTS 타임스탬프로 자막 세그먼트 생성.

    edge-tts 7.x는 문장 단위(SentenceBoundary)로 타임스탬프를 제공하므로,
    긴 문장은 시간 비례로 분할합니다.
    """
    if not tts_result.word_boundaries:
        logger.warning("타임스탬프 없음 - 자막 생성 불가")
        return []

    entries: list[SubtitleEntry] = []
    idx = 1

    for wb in tts_result.word_boundaries:
        text = wb.text.strip()
        if not text:
            continue

        # 짧은 문장은 그대로
        if len(text) <= chars_per_segment:
            entries.append(
                SubtitleEntry(
                    index=idx,
                    start_ms=wb.offset_ms,
                    end_ms=wb.offset_ms + wb.duration_ms,
                    text=text,
                )
            )
            idx += 1
            continue

        # 긴 문장 → 시간 비례 분할
        chunks = _split_text(text, chars_per_segment)
        total_chars = len(text)
        current_offset = wb.offset_ms

        for chunk in chunks:
            ratio = len(chunk) / total_chars
            chunk_duration = int(wb.duration_ms * ratio)

            entries.append(
                SubtitleEntry(
                    index=idx,
                    start_ms=current_offset,
                    end_ms=current_offset + chunk_duration,
                    text=chunk,
                )
            )
            idx += 1
            current_offset += chunk_duration

    logger.info(f"자막 생성: {len(entries)}개 세그먼트")
    return entries


def _split_text(text: str, max_chars: int) -> list[str]:
    """텍스트를 max_chars 이하로 분할. 구두점/공백 기준."""
    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_chars:
        # 구두점이나 공백에서 끊기
        split_pos = max_chars
        for i in range(max_chars, max(0, max_chars - 5), -1):
            if remaining[i] in " ,.:!?·…~":
                split_pos = i + 1
                break

        chunks.append(remaining[:split_pos].strip())
        remaining = remaining[split_pos:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


def write_srt(entries: list[SubtitleEntry], output_path: str) -> str:
    """SubtitleEntry 리스트를 SRT 파일로 저장."""
    lines: list[str] = []
    for entry in entries:
        start = _ms_to_srt_time(entry.start_ms)
        end = _ms_to_srt_time(entry.end_ms)
        lines.append(f"{entry.index}")
        lines.append(f"{start} --> {end}")
        lines.append(entry.text)
        lines.append("")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"SRT 저장: {output_path}")
    return output_path


def _ms_to_srt_time(ms: int) -> str:
    """밀리초를 SRT 타임코드 형식으로 변환."""
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    seconds = ms // 1_000
    millis = ms % 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
