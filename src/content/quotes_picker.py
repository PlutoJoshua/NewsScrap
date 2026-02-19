"""명언 선택기: JSON 데이터베이스에서 미사용 명언을 선택."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)


class QuotesPicker:
    """JSON 파일에서 명언을 선택하고 사용 이력을 관리."""

    def __init__(self, quotes_file: str):
        self.quotes_file = Path(quotes_file)
        if not self.quotes_file.exists():
            raise FileNotFoundError(f"명언 파일 없음: {self.quotes_file}")

    def pick(self, date: str) -> dict:
        """미사용 명언 1개를 선택하고 used_dates에 날짜를 기록.

        Returns:
            {"id": "q001", "text": "...", "author": "...", "category": "..."}
        """
        quotes = self._load()

        # 이미 오늘 사용한 명언이 있으면 그것을 반환
        today_used = [q for q in quotes if date in q.get("used_dates", [])]
        if today_used:
            logger.info(f"오늘 이미 선택된 명언: {today_used[0]['id']}")
            return today_used[0]

        # 미사용 명언 우선
        unused = [q for q in quotes if not q.get("used_dates")]
        if unused:
            selected = random.choice(unused)
        else:
            # 전부 사용됨 → 가장 오래 전에 사용된 것 선택
            sorted_by_last = sorted(
                quotes,
                key=lambda q: q.get("used_dates", [""])[-1],
            )
            selected = sorted_by_last[0]
            logger.info("모든 명언 사용됨, 가장 오래된 명언 재사용")

        # 사용 기록 추가
        selected.setdefault("used_dates", []).append(date)
        self._save(quotes)

        logger.info(
            f"명언 선택: [{selected['id']}] \"{selected['text']}\" - {selected['author']}"
        )
        return selected

    def _load(self) -> list[dict]:
        with open(self.quotes_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, quotes: list[dict]) -> None:
        with open(self.quotes_file, "w", encoding="utf-8") as f:
            json.dump(quotes, f, indent=2, ensure_ascii=False)
