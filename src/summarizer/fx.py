"""브리핑용 USD/KRW 환율 조회 (종가 + 전일 대비 변동률)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import yfinance as yf

logger = logging.getLogger(__name__)

TICKER = "KRW=X"


@dataclass(frozen=True)
class FxQuote:
    close: int          # 원 단위 표시용
    prev_close: float
    change_pct: float   # 전일 대비 %, 소수 둘째 자리

    def describe(self) -> str:
        arrow = "▲" if self.change_pct > 0 else "▼" if self.change_pct < 0 else "-"
        return (
            f"- 현재 USD/KRW 환율: 약 {self.close:,}원 "
            f"({arrow} 전일 대비 {abs(self.change_pct):.2f}%)"
        )


def fetch_usd_krw() -> FxQuote | None:
    """최근 5거래일 종가로 환율과 전일 대비 변동률을 계산한다. 실패 시 None."""
    try:
        data = yf.download(TICKER, period="5d", progress=False)
        closes = data["Close"].dropna()
        if len(closes) < 2:
            return None
        curr = float(closes.iloc[-1].item())
        prev = float(closes.iloc[-2].item())
        change_pct = round((curr - prev) / curr * 100, 2)
        return FxQuote(close=int(curr), prev_close=prev, change_pct=change_pct)
    except Exception as e:
        logger.warning(f"환율 정보 조회 실패: {e}")
        return None
