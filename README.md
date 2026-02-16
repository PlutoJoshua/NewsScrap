# NewsScrap

경제/AI 뉴스 자동 수집 → AI 요약 → 숏츠 영상 생성 파이프라인

## 파이프라인

```
뉴스 수집 (RSS + 크롤링)
    → AI 요약 (Ollama / OpenAI / Claude)
    → TTS 음성 (edge-tts / Google Cloud)
    → 자막 생성 (타임스탬프 기반)
    → 영상 합성 (9:16, 1080x1920)
```

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ollama 사용 시:
```bash
brew install ollama
ollama serve
ollama pull gemma
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

### 전체 파이프라인

```bash
# 스크래핑 → 요약 → TTS → 자막 → 영상
python3 scripts/run_pipeline.py --top 3

# 기존 기사로 요약~영상만
python3 scripts/run_pipeline.py --skip-scrape --top 5

# 기존 브리핑으로 TTS~영상만
python3 scripts/run_pipeline.py --skip-scrape --skip-summarize
```

### 개별 실행

```bash
# 스크래핑만
python3 scripts/run_scrape.py
python3 scripts/run_scrape.py --feeds hankyung_economy,etnews_ai
python3 scripts/run_scrape.py --date 2026-02-16

# 요약만
python3 scripts/run_summarize.py --top 5
LLM_PROVIDER=openai python3 scripts/run_summarize.py
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

`config/config.yaml`에서 피드 추가/비활성화 가능

## 프로젝트 구조

```
src/
├── scraper/              # 뉴스 수집
│   ├── rss_fetcher.py    # RSS 피드 수집
│   ├── article_crawler.py # 본문 크롤링
│   ├── dedup.py          # 중복 제거
│   ├── rate_limiter.py   # 요청 간격 제한
│   └── parsers/          # 사이트별 파서
│       ├── hankyung.py
│       ├── chosun.py
│       ├── etnews.py
│       ├── aitimes.py
│       └── generic.py    # newspaper3k 폴백
├── summarizer/           # AI 요약
│   ├── ollama_provider.py
│   ├── openai_provider.py
│   ├── claude_provider.py
│   └── factory.py        # LLM_PROVIDER로 스위칭
├── tts/                  # 음성 합성
│   ├── edge_tts_provider.py
│   ├── google_tts_provider.py
│   └── factory.py        # TTS_PROVIDER로 스위칭
├── subtitles/            # 자막 생성
│   └── subtitle_generator.py
├── video/                # 영상 합성
│   ├── background.py     # Pexels 배경 영상
│   └── composer.py       # moviepy 합성
├── storage/              # 데이터 저장
│   ├── models.py         # Pydantic 모델
│   └── json_store.py     # 날짜별 JSON
└── pipeline.py           # 전체 오케스트레이터

scripts/
├── run_scrape.py         # 스크래핑 CLI
├── run_summarize.py      # 요약 CLI
└── run_pipeline.py       # 전체 파이프라인 CLI

config/
├── config.yaml           # RSS 피드, 모델 설정
└── .env.example

data/                     # 런타임 데이터 (gitignore)
├── articles/YYYY-MM-DD/
├── summaries/YYYY-MM-DD/
├── audio/YYYY-MM-DD/
├── subtitles/YYYY-MM-DD/
└── output/YYYY-MM-DD/    # 최종 영상
```

## 출력 영상 스펙

- 해상도: 1080x1920 (9:16)
- FPS: 30
- 코덱: H.264 + AAC
- 최대 길이: 60초

## 기술 스택

- **스크래핑**: feedparser, requests, BeautifulSoup, newspaper3k
- **AI 요약**: Ollama (무료, 기본) / OpenAI / Claude
- **TTS**: edge-tts (무료, 기본) / Google Cloud TTS
- **영상**: moviepy, ffmpeg
- **배경**: Pexels API (무료)
- **데이터**: Pydantic, JSON
