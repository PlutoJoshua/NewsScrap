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
        shorts_script = self._generate(script_prompt)

        return Briefing(
            date=date,
            provider=self.provider_name,
            segments=segments,
            shorts_script=shorts_script,
        )

    def _generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
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
            body = (a.content.body[:500] if a.content else "")
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
            data = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.warning("브리핑 JSON 파싱 실패, 원본 텍스트로 폴백")
            return [
                BriefingSegment(
                    headline="오늘의 뉴스 요약",
                    summary=raw[:500],
                )
            ]

        segments = []
        for item in data.get("segments", []):
            source_ids = []
            for idx in item.get("source_indices", []):
                if isinstance(idx, int) and 0 <= idx < len(articles):
                    source_ids.append(articles[idx].id)

            segments.append(
                BriefingSegment(
                    headline=item.get("headline", ""),
                    summary=item.get("summary", ""),
                    keywords=item.get("keywords", []),
                    source_articles=source_ids,
                )
            )
        return segments
