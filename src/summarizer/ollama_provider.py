"""Ollama 로컬 LLM 프로바이더 (기본값, 무료)."""

from __future__ import annotations

import json
import logging

import requests

from src.storage.models import Article, Briefing, BriefingSegment
from src.summarizer.base import LLMProvider
from src.summarizer.prompt_templates import (
    BRIEFING_PROMPT,
    SHORTS_SCRIPT_PROMPT,
    SINGLE_SUMMARY_PROMPT,
)

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "gemma2:9b-instruct-q4_K_M")
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 2048)

    @property
    def provider_name(self) -> str:
        return "ollama"

    def summarize_single(self, article: Article) -> str:
        body = article.content.body[:2000] if article.content else ""
        title = article.content.title if article.content else article.rss_title
        prompt = SINGLE_SUMMARY_PROMPT.format(title=title, body=body)
        return self._generate(prompt)

    def generate_briefing(self, articles: list[Article], date: str) -> Briefing:
        # 1) 기사 목록 텍스트 구성
        articles_text = self._format_articles(articles)
        briefing_prompt = BRIEFING_PROMPT.format(articles=articles_text)
        raw_briefing = self._generate(briefing_prompt)

        # 2) JSON 파싱
        segments = self._parse_briefing_json(raw_briefing, articles)

        # 3) 숏츠 스크립트 생성
        briefing_summary = "\n".join(
            f"- {s.headline}: {s.summary}" for s in segments
        )
        script_prompt = SHORTS_SCRIPT_PROMPT.format(briefing=briefing_summary)
        shorts_script = self._generate(script_prompt, max_tokens=512)

        return Briefing(
            date=date,
            provider=self.provider_name,
            segments=segments,
            shorts_script=shorts_script,
        )

    def _generate(self, prompt: str, max_tokens: int | None = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.ConnectionError:
            raise ConnectionError(
                f"Ollama 서버에 연결할 수 없습니다 ({self.base_url}). "
                "'ollama serve' 명령으로 서버를 실행해주세요."
            )
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama 요청 실패: {e}")

    def _format_articles(self, articles: list[Article]) -> str:
        parts = []
        for i, a in enumerate(articles):
            title = a.content.title if a.content else a.rss_title
            body = (a.content.body[:1000] if a.content else "")
            parts.append(
                f"[{i}] 제목: {title}\n"
                f"    출처: {a.source_name} | 카테고리: {a.category}\n"
                f"    본문: {body}"
            )
        return "\n\n".join(parts)

    def _parse_briefing_json(
        self, raw: str, articles: list[Article]
    ) -> list[BriefingSegment]:
        # JSON 블록 추출
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            json_str = raw[start:end]
            data = json.loads(json_str)
        except (ValueError, json.JSONDecodeError):
            logger.warning("브리핑 JSON 파싱 실패, 원본 텍스트로 폴백")
            logger.debug("LLM 원본 출력: %s", raw[:500])
            return [
                BriefingSegment(
                    headline="오늘의 뉴스 요약",
                    summary=raw[:500],
                )
            ]

        # segments / articles 등 다양한 키명 허용
        raw_segments = (
            data.get("segments")
            or data.get("articles")
            or data.get("news")
            or []
        )
        if not raw_segments:
            logger.warning(
                "JSON에 segments가 비어있음. keys=%s, 원본 텍스트로 폴백",
                list(data.keys()),
            )
            return [
                BriefingSegment(
                    headline="오늘의 뉴스 요약",
                    summary=raw[:500],
                )
            ]

        segments = []
        for item in raw_segments:
            source_ids = []
            for idx in item.get("source_indices", []):
                if isinstance(idx, int) and 0 <= idx < len(articles):
                    source_ids.append(articles[idx].id)

            headline = (
                item.get("headline")
                or item.get("title")
                or ""
            )
            summary = (
                item.get("summary")
                or item.get("description")
                or ""
            )

            keywords = item.get("keywords", [])
            if not keywords:
                keywords = _extract_fallback_keywords(headline, summary)

            segments.append(
                BriefingSegment(
                    headline=headline,
                    summary=summary,
                    keywords=keywords,
                    source_articles=source_ids,
                )
            )
        return segments


# 키워드 추출 폴백용 매칭 사전
_KEYWORD_PATTERNS = [
    "GDP", "AI", "금리", "환율", "주식", "코인", "비트코인", "반도체",
    "인플레이션", "부동산", "투자", "수출", "무역", "스타트업", "기술",
    "금융", "경제", "자동차", "배터리", "에너지", "소비", "물가",
    "인공지능", "로봇", "클라우드", "데이터", "제조", "규제", "정책",
    "일본", "미국", "중국", "한국", "유럽",
]


def _extract_fallback_keywords(headline: str, summary: str) -> list[str]:
    """headline/summary에서 키워드를 자동 추출 (LLM이 keywords를 비웠을 때)."""
    text = f"{headline} {summary}"
    found = [kw for kw in _KEYWORD_PATTERNS if kw in text]
    return found[:3] if found else ["경제"]
