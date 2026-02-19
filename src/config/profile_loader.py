"""프로필 기반 설정 로더.

base config(config/config.yaml)에 프로필 설정(config/profiles/{name}.yaml)을
deep merge하여 최종 설정을 생성한다.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _deep_merge(base: dict, override: dict) -> dict:
    """override 값으로 base를 재귀적으로 덮어쓰기."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_profile_config(profile: str = "news") -> dict:
    """base config + profile config를 deep merge하여 반환."""
    base_path = PROJECT_ROOT / "config" / "config.yaml"
    profile_path = PROJECT_ROOT / "config" / "profiles" / f"{profile}.yaml"

    if not base_path.exists():
        raise FileNotFoundError(f"기본 설정 파일 없음: {base_path}")
    if not profile_path.exists():
        raise FileNotFoundError(f"프로필 설정 파일 없음: {profile_path}")

    with open(base_path, "r", encoding="utf-8") as f:
        base_config = yaml.safe_load(f) or {}

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_config = yaml.safe_load(f) or {}

    merged = _deep_merge(base_config, profile_config)
    merged["profile_name"] = profile
    return merged
