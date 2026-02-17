"""Pexels API로 배경 영상 다운로드."""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path

import requests

from src.storage.models import BriefingSegment

logger = logging.getLogger(__name__)

PEXELS_API_URL = "https://api.pexels.com/videos/search"

# 한국어 키워드 → Pexels에서 실제로 좋은 영상이 나오는 시각적 검색어
# 핵심: 직역이 아니라 "어떤 영상이 배경으로 어울리는가" 기준
KEYWORD_VISUAL_MAP: dict[str, list[str]] = {
    # 경제/금융 → 주식 차트, 트레이딩 화면, 도시 야경
    "경제": ["stock market screen", "financial district", "city aerial night"],
    "금융": ["stock trading screen", "financial charts", "bank building"],
    "금리": ["stock market screen", "financial charts data"],
    "환율": ["currency exchange", "money bills close up"],
    "인플레이션": ["grocery store shopping", "money printing", "price tags"],
    "GDP": ["city skyline timelapse", "stock market screen", "aerial city"],
    "성장률": ["stock chart green", "city construction", "financial data screen"],
    "무역": ["cargo ship ocean", "shipping containers port", "freight logistics"],
    "수출": ["cargo ship ocean", "shipping containers port"],
    "수입": ["cargo ship ocean", "port logistics crane"],
    # 투자/시장
    "주식": ["stock market trading screen", "stock chart candlestick"],
    "코인": ["bitcoin cryptocurrency", "crypto trading screen"],
    "비트코인": ["bitcoin gold coin", "crypto trading screen"],
    "투자": ["stock market screen", "business meeting office"],
    "부동산": ["apartment building aerial", "city buildings skyline"],
    "채권": ["financial data screen", "stock market trading"],
    # 산업/기업
    "반도체": ["microchip circuit board close up", "semiconductor factory clean room"],
    "스타트업": ["modern office workspace", "people working laptop"],
    "기업": ["corporate office building", "business meeting"],
    "제조": ["factory assembly line", "industrial manufacturing robot"],
    "자동차": ["car factory assembly", "cars driving highway"],
    "배터리": ["electric car charging", "battery technology"],
    "에너지": ["solar panels field", "wind turbines aerial"],
    # 기술/AI
    "AI": ["robot artificial intelligence", "computer code screen", "neural network abstract"],
    "인공지능": ["robot artificial intelligence", "futuristic technology"],
    "기술": ["technology abstract lights", "computer code screen"],
    "데이터": ["server room lights", "data center"],
    "로봇": ["robot arm factory", "humanoid robot"],
    "자율주행": ["self driving car technology", "car dashboard driving"],
    "클라우드": ["server room data center", "cloud computing abstract"],
    "소프트웨어": ["computer code programming", "developer typing laptop"],
    # 생활/소비
    "소비": ["shopping mall people", "retail store"],
    "물가": ["grocery store shopping", "supermarket shelves"],
    "편의점": ["convenience store night", "retail shopping"],
    "유통": ["warehouse logistics", "delivery truck"],
    # 국가 → 대표적 도시 풍경
    "한국": ["seoul city night aerial", "seoul skyline"],
    "미국": ["new york skyline night", "wall street new york"],
    "일본": ["tokyo city night aerial", "tokyo shibuya crossing"],
    "중국": ["shanghai skyline night", "china city aerial"],
    "유럽": ["london city aerial", "european city street"],
    # 뉴스/정책
    "뉴스": ["news studio broadcast", "newspaper printing"],
    "정책": ["government building", "parliament congress"],
    "규제": ["legal document gavel", "government building"],
}

# 폴백 쿼리 리스트
FALLBACK_QUERIES = [
    "stock market trading screen",
    "city skyline night aerial",
    "financial district buildings",
    "technology abstract lights",
    "business office modern",
    "data visualization screen",
    "world map global",
    "money currency bills",
    "newspaper headlines",
    "corporate meeting room",
]


def translate_keywords_to_query(keywords: list[str]) -> str:
    """한국어 키워드를 Pexels 시각 검색어로 변환. 가장 관련성 높은 1개만 사용."""
    for kw in keywords:
        if kw in KEYWORD_VISUAL_MAP:
            return random.choice(KEYWORD_VISUAL_MAP[kw])
        if kw.isascii() and len(kw) > 1:
            return kw

    return random.choice(FALLBACK_QUERIES)


def download_backgrounds_for_segments(
    segments: list[BriefingSegment],
    output_dir: str,
    orientation: str = "portrait",
    min_duration: int = 10,
) -> list[str | None]:
    """세그먼트별로 키워드 기반 배경 영상 다운로드.

    Returns:
        세그먼트 수만큼의 파일 경로 리스트 (실패 시 None).
    """
    paths: list[str | None] = []

    # 이미 캐시된 영상 ID도 exclude에 포함 → 매일 새로운 영상 사용
    used_ids = _get_cached_video_ids(output_dir)
    logger.info(f"기존 캐시 영상 {len(used_ids)}개 제외")

    for i, segment in enumerate(segments):
        query = translate_keywords_to_query(segment.keywords)
        logger.info(
            f"세그먼트 {i + 1}/{len(segments)} 배경 검색: "
            f"keywords={segment.keywords} → query='{query}'"
        )

        path = download_background(
            output_dir=output_dir,
            query=query,
            min_duration=min_duration,
            orientation=orientation,
            exclude_ids=used_ids,
        )

        # 실패 시 폴백 쿼리로 재시도
        if path is None:
            fallback_query = random.choice(FALLBACK_QUERIES)
            logger.info(f"세그먼트 {i + 1} 폴백 검색: '{fallback_query}'")
            path = download_background(
                output_dir=output_dir,
                query=fallback_query,
                min_duration=min_duration,
                orientation=orientation,
                exclude_ids=used_ids,
            )

        if path:
            video_id = Path(path).stem.replace("bg_", "")
            used_ids.add(video_id)

        paths.append(path)

    return paths


def _get_cached_video_ids(output_dir: str) -> set[str]:
    """이미 다운로드된 배경 영상 ID 목록."""
    cache_dir = Path(output_dir)
    if not cache_dir.exists():
        return set()
    return {
        f.stem.replace("bg_", "")
        for f in cache_dir.glob("bg_*.mp4")
    }


def download_background(
    output_dir: str,
    query: str | None = None,
    min_duration: int = 15,
    orientation: str = "portrait",
    exclude_ids: set[str] | None = None,
) -> str | None:
    """Pexels에서 배경 영상을 검색하고 다운로드.

    Returns:
        다운로드된 파일 경로, 또는 실패 시 None
    """
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        logger.warning("PEXELS_API_KEY 없음 - 배경 영상 다운로드 불가")
        return None

    search_query = query or random.choice(FALLBACK_QUERIES)

    headers = {"Authorization": api_key}
    params = {
        "query": search_query,
        "orientation": orientation,
        "per_page": 15,
        "size": "medium",
        "page": random.randint(1, 5),  # 페이지 랜덤화로 매번 다른 영상
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

    # 이미 사용한 영상 제외
    if exclude_ids:
        videos = [v for v in videos if str(v.get("id", "")) not in exclude_ids] or videos

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
