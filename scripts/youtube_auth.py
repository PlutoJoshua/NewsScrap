"""YouTube OAuth2 최초 인증 스크립트.

사용법:
    python scripts/youtube_auth.py --profile news
    python scripts/youtube_auth.py --profile quotes

프로필별 1회만 실행하면 됩니다. 브라우저에서 Google 계정 로그인 후
refresh token이 저장됩니다.
이후 파이프라인 실행 시 자동으로 토큰이 갱신됩니다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]



def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube OAuth2 인증")
    parser.add_argument(
        "--profile", required=True,
        help="인증할 프로필 (예: news, quotes, 커스텀계정)",
    )
    args = parser.parse_args()

    # 프로필 설정에서 경로 로드 시도, 없으면 기본값 사용
    profile_path = PROJECT_ROOT / "config" / "profiles" / f"{args.profile}.yaml"
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            profile_config = yaml.safe_load(f) or {}
        yt_config = profile_config.get("uploader", {}).get("youtube", {})
        creds_path = PROJECT_ROOT / yt_config.get(
            "credentials_path", f"config/{args.profile}_client_secret.json"
        )
        token_path = PROJECT_ROOT / yt_config.get(
            "token_path", f"config/{args.profile}_youtube_token.json"
        )
    else:
        creds_path = PROJECT_ROOT / f"config/{args.profile}_client_secret.json"
        token_path = PROJECT_ROOT / f"config/{args.profile}_youtube_token.json"

    print(f"프로필: {args.profile}")
    print(f"OAuth JSON: {creds_path}")
    print(f"토큰 저장: {token_path}")
    print()

    if not creds_path.exists():
        print(
            f"❌ {creds_path.relative_to(PROJECT_ROOT)} 파일이 없습니다.\n\n"
            "Google Cloud Console에서 다음 단계를 수행하세요:\n"
            "1. https://console.cloud.google.com/ 접속\n"
            "2. 프로젝트 생성 (또는 기존 프로젝트 선택)\n"
            "3. API 및 서비스 → 라이브러리 → 'YouTube Data API v3' 활성화\n"
            "4. API 및 서비스 → 사용자 인증 정보 → OAuth 2.0 클라이언트 ID 생성\n"
            "   - 애플리케이션 유형: '데스크톱 앱'\n"
            f"5. JSON 다운로드 → {creds_path.relative_to(PROJECT_ROOT)} 으로 저장\n"
        )
        return

    flow = InstalledAppFlow.from_client_secrets_file(
        str(creds_path),
        scopes=SCOPES,
    )

    credentials = flow.run_local_server(
        port=8080,
        access_type="offline",
        prompt="consent",
    )

    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }

    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ [{args.profile}] 인증 완료! 토큰 저장: {token_path}")
    print("이후 파이프라인 실행 시 자동으로 토큰이 갱신됩니다.")


if __name__ == "__main__":
    main()
