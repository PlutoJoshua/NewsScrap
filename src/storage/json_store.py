"""날짜별 JSON 파일 저장소."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from src.storage.models import Article

logger = logging.getLogger(__name__)


class JSONStore:
    """data/articles/YYYY-MM-DD/articles.json 구조로 저장."""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)

    def save_articles(self, date: str, articles: list[Article]) -> Path:
        """기사 목록을 날짜 디렉토리에 JSON으로 저장 (기존 데이터에 병합)."""
        dir_path = self.base_dir / "articles" / date
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / "articles.json"

        # 기존 데이터 로드 후 병합 (ID 기준 중복 제거)
        existing = self.load_articles(date)
        existing_ids = {a.id for a in existing}
        new_articles = [a for a in articles if a.id not in existing_ids]
        merged = existing + new_articles

        data = [a.model_dump(mode="json") for a in merged]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(
            f"Saved {len(merged)} articles to {file_path} "
            f"(기존 {len(existing)} + 신규 {len(new_articles)})"
        )
        return file_path

    def load_articles(self, date: str) -> list[Article]:
        """날짜 디렉토리에서 기사 목록 로드."""
        file_path = self.base_dir / "articles" / date / "articles.json"
        if not file_path.exists():
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [Article.model_validate(item) for item in data]

    def save_briefing(self, date: str, briefing_data: dict) -> Path:
        """브리핑 데이터 저장."""
        dir_path = self.base_dir / "summaries" / date
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / "briefing.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(briefing_data, f, ensure_ascii=False, indent=2, default=str)

        return file_path

    def get_today_date(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")
