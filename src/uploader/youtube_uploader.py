"""YouTube 영상 업로드 모듈."""

from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.storage.models import Briefing

logger = logging.getLogger(__name__)

# 재시도 가능한 HTTP 상태 코드
_RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
_MAX_RETRIES = 3


class YouTubeUploader:
    """YouTube Data API v3를 사용한 영상 업로더."""

    def __init__(self, config: dict):
        self.privacy = config.get("privacy", "private")
        self.category_id = str(config.get("category_id", "25"))
        self.default_tags = config.get(
            "default_tags", ["경제", "뉴스", "숏츠", "브리핑"]
        )
        self.title_template = config.get(
            "title_template", "📰 {date} 오늘의 경제 뉴스 #Shorts"
        )
        self.credentials_path = config.get(
            "credentials_path", "config/client_secret.json"
        )
        self.token_path = config.get("token_path", "config/youtube_token.json")

    def _get_credentials(self) -> Credentials:
        """저장된 토큰에서 credentials를 로드하고 필요 시 갱신."""
        token_file = Path(self.token_path)
        if not token_file.exists():
            raise FileNotFoundError(
                f"YouTube 토큰 파일이 없습니다: {self.token_path}\n"
                "'python scripts/youtube_auth.py'를 먼저 실행하세요."
            )

        with open(token_file, "r", encoding="utf-8") as f:
            token_data = json.load(f)

        creds = Credentials(
            token=token_data["token"],
            refresh_token=token_data["refresh_token"],
            token_uri=token_data["token_uri"],
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
        )

        if creds.expired or not creds.valid:
            logger.info("YouTube 토큰 갱신 중...")
            creds.refresh(Request())
            # 갱신된 토큰 저장
            token_data["token"] = creds.token
            with open(token_file, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2, ensure_ascii=False)
            logger.info("YouTube 토큰 갱신 완료")

        return creds

    def _build_metadata(
        self, briefing: Briefing, date: str
    ) -> dict:
        """브리핑 내용으로 YouTube 메타데이터 생성."""
        title = self.title_template.format(date=date)

        # 설명: 세그먼트 헤드라인 나열
        headlines = "\n".join(
            f"• {s.headline}" for s in briefing.segments
        )
        description = (
            f"📰 {date} 오늘의 주요 경제 뉴스 브리핑\n\n"
            f"{headlines}\n\n"
            "#경제뉴스 #오늘의뉴스 #숏츠 #경제브리핑"
        )

        # 태그: 기본 + 세그먼트 키워드
        tags = list(self.default_tags)
        for segment in briefing.segments:
            for kw in segment.keywords:
                if kw not in tags:
                    tags.append(kw)

        return {
            "snippet": {
                "title": title[:100],  # YouTube 제목 100자 제한
                "description": description[:5000],
                "tags": tags[:30],  # YouTube 태그 30개 제한
                "categoryId": self.category_id,
            },
            "status": {
                "privacyStatus": self.privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

    def upload(
        self,
        video_path: str,
        briefing: Briefing,
        date: str,
        output_dir: str | None = None,
    ) -> dict:
        """영상을 YouTube에 업로드하고 결과를 반환."""
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"영상 파일이 없습니다: {video_path}")

        creds = self._get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        metadata = self._build_metadata(briefing, date)
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=256 * 1024,  # 256KB chunks
        )

        logger.info(
            "YouTube 업로드 시작: %s (%s)",
            metadata["snippet"]["title"],
            metadata["status"]["privacyStatus"],
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=metadata,
            media_body=media,
        )

        response = self._resumable_upload(request)

        result = {
            "video_id": response["id"],
            "youtube_url": f"https://youtu.be/{response['id']}",
            "title": metadata["snippet"]["title"],
            "privacy": metadata["status"]["privacyStatus"],
            "uploaded_at": datetime.now().isoformat(),
            "status": "success",
        }

        # 결과 저장
        if output_dir:
            result_dir = Path(output_dir)
            result_dir.mkdir(parents=True, exist_ok=True)
            result_path = result_dir / "upload_result.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info("업로드 결과 저장: %s", result_path)

        logger.info("YouTube 업로드 완료: %s", result["youtube_url"])
        return result

    def upload_quote(
        self,
        video_path: str,
        quote: dict,
        date: str,
        output_dir: str | None = None,
    ) -> dict:
        """명언 영상을 YouTube에 업로드."""
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"영상 파일이 없습니다: {video_path}")

        creds = self._get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        metadata = self._build_quote_metadata(quote, date)
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=256 * 1024,
        )

        logger.info(
            "YouTube 업로드 시작: %s (%s)",
            metadata["snippet"]["title"],
            metadata["status"]["privacyStatus"],
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=metadata,
            media_body=media,
        )

        response = self._resumable_upload(request)

        result = {
            "video_id": response["id"],
            "youtube_url": f"https://youtu.be/{response['id']}",
            "title": metadata["snippet"]["title"],
            "privacy": metadata["status"]["privacyStatus"],
            "uploaded_at": datetime.now().isoformat(),
            "status": "success",
            "quote_id": quote.get("id", ""),
        }

        if output_dir:
            result_dir = Path(output_dir)
            result_dir.mkdir(parents=True, exist_ok=True)
            result_path = result_dir / "upload_result.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info("업로드 결과 저장: %s", result_path)

        logger.info("YouTube 업로드 완료: %s", result["youtube_url"])
        return result

    def _build_quote_metadata(self, quote: dict, date: str) -> dict:
        """명언 영상용 YouTube 메타데이터 생성."""
        quote_text = quote.get("text", "")
        author = quote.get("author", "")
        category = quote.get("category", "")

        # 제목: 명언 미리보기 + 저자
        quote_short = quote_text[:20] + ("..." if len(quote_text) > 20 else "")
        title = self.title_template.format(
            date=date, quote_short=quote_short, author=author,
        )

        description = (
            f"✨ 오늘의 명언\n\n"
            f'"{quote_text}"\n'
            f"- {author}\n\n"
            f"#명언 #격언 #{category} #지혜 #동기부여 #숏츠"
        )

        tags = list(self.default_tags)
        if author and author not in tags:
            tags.append(author)
        if category and category not in tags:
            tags.append(category)

        return {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:30],
                "categoryId": self.category_id,
            },
            "status": {
                "privacyStatus": self.privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

    def _resumable_upload(self, request) -> dict:
        """지수 백오프를 사용한 resumable upload 실행."""
        response = None
        retry = 0

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info("업로드 진행: %d%%", progress)
            except httplib2.HttpLib2Error as e:
                if retry >= _MAX_RETRIES:
                    raise RuntimeError(f"YouTube 업로드 실패 (최대 재시도 초과): {e}")
                retry += 1
                wait = 2**retry + random.random()
                logger.warning(
                    "업로드 오류, %d초 후 재시도 (%d/%d): %s",
                    wait, retry, _MAX_RETRIES, e,
                )
                time.sleep(wait)
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, "resp") and e.resp.status in _RETRIABLE_STATUS_CODES:
                    if retry >= _MAX_RETRIES:
                        raise RuntimeError(
                            f"YouTube 업로드 실패 (최대 재시도 초과): {e}"
                        )
                    retry += 1
                    wait = 2**retry + random.random()
                    logger.warning(
                        "서버 오류 %s, %d초 후 재시도 (%d/%d)",
                        error_msg, wait, retry, _MAX_RETRIES,
                    )
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"YouTube 업로드 실패: {e}")

        return response
