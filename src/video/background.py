"""Pexels API로 배경 영상 다운로드."""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

PEXELS_API_URL = "https://api.pexels.com/videos/search"

DEFAULT_QUERIES = [
    "technology abstract",
    "city skyline night",
    "data visualization",
    "stock market graph",
]


def download_background(
    output_dir: str,
    query: str | None = None,
    min_duration: int = 15,
    orientation: str = "portrait",
) -> str | None:
    """Pexels에서 배경 영상을 검색하고 다운로드.

    Returns:
        다운로드된 파일 경로, 또는 실패 시 None
    """
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        logger.warning("PEXELS_API_KEY 없음 - 배경 영상 다운로드 불가")
        return None

    search_query = query or random.choice(DEFAULT_QUERIES)

    headers = {"Authorization": api_key}
    params = {
        "query": search_query,
        "orientation": orientation,
        "per_page": 10,
        "size": "medium",
    }

    try:
        resp = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"Pexels API 요청 실패: {e}")
        return None

    videos = data.get("videos", [])
    if not videos:
        logger.warning(f"검색 결과 없음: '{search_query}'")
        return None

    # 최소 길이 필터링 후 랜덤 선택
    candidates = [v for v in videos if v.get("duration", 0) >= min_duration]
    if not candidates:
        candidates = videos

    video = random.choice(candidates)

    # HD 파일 찾기 (portrait 우선)
    video_file = _select_video_file(video.get("video_files", []))
    if not video_file:
        logger.error("적합한 비디오 파일을 찾을 수 없음")
        return None

    # 다운로드
    download_url = video_file["link"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / f"bg_{video['id']}.mp4"

    if file_path.exists():
        logger.info(f"캐시된 배경 영상 사용: {file_path}")
        return str(file_path)

    logger.info(f"배경 영상 다운로드: {download_url}")
    try:
        dl_resp = requests.get(download_url, stream=True, timeout=60)
        dl_resp.raise_for_status()
        with open(file_path, "wb") as f:
            for chunk in dl_resp.iter_content(chunk_size=8192):
                f.write(chunk)
    except requests.RequestException as e:
        logger.error(f"다운로드 실패: {e}")
        return None

    logger.info(f"배경 영상 저장: {file_path}")
    return str(file_path)


def _select_video_file(files: list[dict]) -> dict | None:
    """HD 이상, portrait 방향 우선으로 비디오 파일 선택."""
    # height > width인 것 우선 (portrait)
    portrait = [
        f for f in files
        if f.get("height", 0) > f.get("width", 0) and f.get("height", 0) >= 720
    ]
    if portrait:
        return max(portrait, key=lambda f: f.get("height", 0))

    # portrait 없으면 HD 이상 아무거나
    hd = [f for f in files if f.get("height", 0) >= 720]
    if hd:
        return max(hd, key=lambda f: f.get("height", 0))

    return files[0] if files else None
