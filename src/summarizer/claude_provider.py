"""Anthropic Claude API 프로바이더."""

from __future__ import annotations

import json
import logging
import os

from src.storage.models import Article, Briefing, BriefingSegment
from src.summarizer.base import LLMProvider
from src.summarizer.prompt_templates import (
    BRIEFING_PROMPT,
    SHORTS_SCRIPT_PROMPT,
    SINGLE_SUMMARY_PROMPT,
)

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    def __init__(self, config: dict):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수를 설정해주세요.")

        from anthropic import Anthropic

        self.client = Anthropic(api_key=api_key)
        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 2048)

    @property
    def provider_name(self) -> str:
        return "claude"

    def summarize_single(self, article: Article) -> str:
        body = article.content.body[:2000] if article.content else ""
        title = article.content.title if article.content else article.rss_title
        prompt = SINGLE_SUMMARY_PROMPT.format(title=title, body=body)
        return self._chat(prompt)

    def generate_briefing(self, articles: list[Article], date: str) -> Briefing:
        articles_text = _format_articles(articles)
        briefing_prompt = BRIEFING_PROMPT.format(articles=articles_text)
        raw_briefing = self._chat(briefing_prompt)

        segments = _parse_briefing_json(raw_briefing, articles)

        briefing_summary = "\n".join(
            f"- {s.headline}: {s.summary}" for s in segments
        )
        script_prompt = SHORTS_SCRIPT_PROMPT.format(briefing=briefing_summary)
        shorts_script = self._chat(script_prompt)

        return Briefing(
            date=date,
            provider=self.provider_name,
            segments=segments,
            shorts_script=shorts_script,
        )

    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        return self._chat(prompt)

    def _chat(self, prompt: str) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        return resp.content[0].text.strip()


def _format_articles(articles: list[Article]) -> str:
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
    raw: str, articles: list[Article]
) -> list[BriefingSegment]:
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("브리핑 JSON 파싱 실패, 원본 텍스트로 폴백")
        return [BriefingSegment(headline="오늘의 뉴스 요약", summary=raw[:500])]

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
