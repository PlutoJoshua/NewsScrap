"""YouTube OAuth2 최초 인증 스크립트.

사용법:
    python scripts/youtube_auth.py

1회만 실행하면 됩니다. 브라우저에서 Google 계정 로그인 후
refresh token이 config/youtube_token.json에 저장됩니다.
이후 파이프라인 실행 시 자동으로 토큰이 갱신됩니다.
"""

from __future__ import annotations

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CREDENTIALS_PATH = PROJECT_ROOT / "config" / "client_secret.json"
TOKEN_PATH = PROJECT_ROOT / "config" / "youtube_token.json"


def main() -> None:
    if not CREDENTIALS_PATH.exists():
        print(
            "❌ config/client_secret.json 파일이 없습니다.\n\n"
            "Google Cloud Console에서 다음 단계를 수행하세요:\n"
            "1. https://console.cloud.google.com/ 접속\n"
            "2. 프로젝트 생성 (또는 기존 프로젝트 선택)\n"
            "3. API 및 서비스 → 라이브러리 → 'YouTube Data API v3' 활성화\n"
            "4. API 및 서비스 → 사용자 인증 정보 → OAuth 2.0 클라이언트 ID 생성\n"
            "   - 애플리케이션 유형: '데스크톱 앱'\n"
            "5. JSON 다운로드 → config/client_secret.json 으로 저장\n"
        )
        return

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
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

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2, ensure_ascii=False)

    print(f"✅ 인증 완료! 토큰 저장: {TOKEN_PATH}")
    print("이후 파이프라인 실행 시 자동으로 토큰이 갱신됩니다.")


if __name__ == "__main__":
    main()
