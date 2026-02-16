"""LLM 프로바이더 팩토리 - 환경변수로 스위칭."""

from __future__ import annotations

import os

from src.summarizer.base import LLMProvider

# LLM_PROVIDER 환경변수 값: ollama (기본) | openai | claude
_PROVIDERS = {
    "ollama": ("src.summarizer.ollama_provider", "OllamaProvider"),
    "openai": ("src.summarizer.openai_provider", "OpenAIProvider"),
    "claude": ("src.summarizer.claude_provider", "ClaudeProvider"),
}


def create_llm_provider(config: dict) -> LLMProvider:
    """LLM_PROVIDER 환경변수에 따라 프로바이더 인스턴스 생성."""
    provider_name = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider_name not in _PROVIDERS:
        raise ValueError(
            f"알 수 없는 LLM 프로바이더: '{provider_name}'. "
            f"사용 가능: {', '.join(_PROVIDERS.keys())}"
        )

    module_path, class_name = _PROVIDERS[provider_name]

    # Lazy import로 불필요한 의존성 로드 방지
    import importlib
    module = importlib.import_module(module_path)
    provider_class = getattr(module, class_name)

    provider_config = config.get("summarizer", {}).get(provider_name, {})
    return provider_class(provider_config)
