# NewsScrap

YouTube 숏츠 자동 생성 파이프라인 — 멀티 프로필 지원

## 프로필

### 뉴스 브리핑 (`--profile news`)
경제/AI 뉴스 자동 수집 → AI 요약 → 숏츠 영상 생성 → YouTube 업로드

```
RSS 뉴스 수집 → AI 브리핑 → TTS → 자막 → 영상 합성 → 업로드
```

### 명언/격언 (`--profile quotes`)
매일 1개 명언 선택 → AI 해설 → 숏츠 영상 생성 → YouTube 업로드

```
명언 선택 (JSON DB) → AI 해설 스크립트 → TTS → 자막 → 영상 합성 → 업로드
```

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ollama (로컬 LLM):
```bash
brew install ollama
ollama serve
ollama pull gemma3:12b
```

## 환경변수

`.env` 파일을 프로젝트 루트에 생성:

```bash
LLM_PROVIDER=ollama          # ollama | openai | claude
TTS_PROVIDER=edge            # edge | google

OPENAI_API_KEY=              # LLM_PROVIDER=openai 사용 시
ANTHROPIC_API_KEY=           # LLM_PROVIDER=claude 사용 시
GOOGLE_APPLICATION_CREDENTIALS=  # TTS_PROVIDER=google 사용 시

PEXELS_API_KEY=              # 배경 영상 (무료, pexels.com/api 에서 발급)
```

## 사용법

### 뉴스 파이프라인

```bash
# 전체 파이프라인 (스크래핑 → 요약 → TTS → 자막 → 영상)
python3 scripts/run_pipeline.py --profile news

# 기존 기사로 요약~영상만
python3 scripts/run_pipeline.py --profile news --skip-scrape

# 기존 브리핑으로 TTS~영상만
python3 scripts/run_pipeline.py --profile news --skip-scrape --skip-summarize

# 기사 수 지정
python3 scripts/run_pipeline.py --profile news --top 5
```

### 명언 파이프라인

```bash
# 전체 파이프라인 (명언 선택 → 해설 → TTS → 영상)
python3 scripts/run_pipeline.py --profile quotes

# 특정 날짜
python3 scripts/run_pipeline.py --profile quotes --date 2026-02-19
```

### 공통 옵션

```bash
--profile {news,quotes}   # 프로필 선택 (기본: news)
--date YYYY-MM-DD         # 대상 날짜
--no-upload               # 업로드 건너뛰기
--upload-only             # 기존 영상 업로드만 (news)
```

### 개별 실행

```bash
# 스크래핑만
python3 scripts/run_scrape.py
python3 scripts/run_scrape.py --feeds hankyung_economy,etnews_ai

# 요약만
python3 scripts/run_summarize.py --top 5
```

## YouTube 업로드 설정

### 1. Google Cloud Console

1. [console.cloud.google.com](https://console.cloud.google.com/) 접속
2. 프로젝트 생성
3. **API 및 서비스 → 라이브러리** → `YouTube Data API v3` 활성화
4. **API 및 서비스 → 사용자 인증 정보** → OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱)
5. JSON 다운로드

### 2. 채널별 설정

| 채널 | OAuth JSON 파일 | 토큰 파일 |
|------|----------------|-----------|
| 뉴스 | `config/news_client_secret.json` | `config/news_youtube_token.json` |
| 명언 | `config/quotes_client_secret.json` | `config/quotes_youtube_token.json` |

### 3. 최초 인증 (채널별 1회)

```bash
python3 scripts/youtube_auth.py --profile news
python3 scripts/youtube_auth.py --profile quotes
```

### 4. 업로드 활성화

`config/profiles/news.yaml` 또는 `config/profiles/quotes.yaml`에서:
```yaml
uploader:
  enabled: true
```

## 뉴스 소스

| 소스 | 방식 | 카테고리 |
|------|------|----------|
| 한국경제 경제 | RSS | economy |
| 한국경제 IT | RSS | tech |
| 전자신문 AI | RSS | ai |
| 전자신문 경제 | RSS | economy |
| 조선일보 경제 | RSS | economy |
| AI타임스 | HTML 크롤링 | ai |

`config/profiles/news.yaml`에서 피드 추가/비활성화 가능

## 명언 데이터베이스

`data/quotes/quotes.json`에 수동 관리:

```json
{
  "id": "q001",
  "text": "삶이 있는 한 희망은 있다.",
  "author": "키케로",
  "category": "인생",
  "used_dates": []
}
```

- 카테고리: 인생, 성공, 지혜, 용기, 사랑
- 사용된 명언은 `used_dates`에 자동 기록
- 미사용 명언 우선 선택, 전부 사용 시 가장 오래된 것 재사용

## 프로젝트 구조

```
config/
├── config.yaml              # 공통 설정 (LLM, TTS, 영상 스펙)
├── profiles/
│   ├── news.yaml            # 뉴스 프로필 (피드, 브리핑, 업로더)
│   └── quotes.yaml          # 명언 프로필 (콘텐츠, TTS 목소리, 업로더)
└── fonts/

src/
├── config/
│   └── profile_loader.py    # 프로필 설정 로더
├── scraper/                 # 뉴스 수집
│   ├── rss_fetcher.py
│   ├── article_crawler.py
│   ├── dedup.py
│   └── parsers/             # 사이트별 파서
├── content/
│   └── quotes_picker.py     # 명언 선택기
├── summarizer/              # AI 요약/스크립트 생성
│   ├── ollama_provider.py
│   ├── openai_provider.py
│   ├── claude_provider.py
│   ├── prompt_templates.py  # 뉴스 + 명언 프롬프트
│   └── factory.py
├── tts/                     # 음성 합성
│   ├── edge_tts_provider.py
│   ├── google_tts_provider.py
│   └── factory.py
├── subtitles/
│   └── subtitle_generator.py
├── video/
│   ├── background.py        # Pexels 배경 영상
│   └── composer.py          # 뉴스 + 명언 영상 합성
├── uploader/
│   └── youtube_uploader.py  # YouTube 업로드
├── storage/
│   ├── models.py
│   └── json_store.py
├── pipeline.py              # 뉴스 파이프라인
└── pipeline_quotes.py       # 명언 파이프라인

scripts/
├── run_pipeline.py          # 메인 CLI (--profile)
├── run_scrape.py
├── run_summarize.py
└── youtube_auth.py          # YouTube OAuth 인증

data/
├── news/                    # 뉴스 데이터
│   ├── articles/YYYY-MM-DD/
│   ├── summaries/YYYY-MM-DD/
│   ├── audio/YYYY-MM-DD/
│   ├── subtitles/YYYY-MM-DD/
│   └── output/YYYY-MM-DD/
└── quotes/                  # 명언 데이터
    ├── quotes.json          # 명언 DB
    ├── selected/YYYY-MM-DD/
    ├── scripts/YYYY-MM-DD/
    ├── audio/YYYY-MM-DD/
    └── output/YYYY-MM-DD/
```

## 영상 스펙

| 항목 | 뉴스 | 명언 |
|------|------|------|
| 해상도 | 1080x1920 (9:16) | 1080x1920 (9:16) |
| FPS | 30 | 30 |
| 코덱 | H.264 + AAC | H.264 + AAC |
| 최대 길이 | 59초 | 59초 |
| 배경 | 키워드별 멀티 배경 | 자연/추상 단일 배경 |
| 특징 | 뉴스 타이틀 + 자막 | 명언 텍스트 + 저자 + 해설 자막 |

## 기술 스택

- **스크래핑**: feedparser, requests, BeautifulSoup, newspaper3k
- **AI**: Ollama gemma3:12b (기본) / OpenAI / Claude
- **TTS**: edge-tts (기본, 무료) / Google Cloud TTS
- **영상**: moviepy, ffmpeg
- **배경**: Pexels API (무료)
- **업로드**: YouTube Data API v3, OAuth2
- **데이터**: Pydantic, JSON, YAML
