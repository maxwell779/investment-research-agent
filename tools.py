# -*- coding: utf-8 -*-
"""
에이전트가 호출하는 도구(tool) 모음 — 전부 무료 데이터 소스.
- 한국주식: 종목명 → 코드 변환 후 yfinance(.KS/.KQ)로 조회 (FinanceDataReader로 종목명 해석)
- 해외주식: yfinance 심볼 그대로 (AAPL, MSFT ...)
- 뉴스: yfinance가 제공하는 최신 뉴스 (무료)

각 도구는 호출될 때 EVIDENCE 에 '무엇을·어디서 가져왔는지'를 남긴다 → 답변 인용(citation)에 사용.
"""
import os
import re
import io
import html
import json
import zipfile
import xml.etree.ElementTree as ET
import requests
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr

# 도구 호출 근거 로그 (질문 1건마다 agent에서 clear) — 답변의 출처 표기에 사용
EVIDENCE = []

_KRX_CACHE = None


def _krx_listing():
    """KRX 전체 종목 목록(코드/이름/시장)을 1회 로드 후 캐시."""
    global _KRX_CACHE
    if _KRX_CACHE is None:
        _KRX_CACHE = fdr.StockListing("KRX")
    return _KRX_CACHE


def resolve_ticker(query: str) -> dict:
    """종목명 또는 심볼을 yfinance 호환 티커로 변환한다.

    한국 종목명(예: '삼성전자')은 종목코드를 찾아 시장에 맞는 접미사(.KS=코스피, .KQ=코스닥)를 붙인다.
    해외 심볼(예: 'AAPL')이나 이미 접미사가 있는 값은 그대로 반환한다.

    Args:
        query: 종목명(한글) 또는 티커 심볼.

    Returns:
        {"ticker": "005930.KS", "name": "삼성전자", "market": "KOSPI"} 형태.
    """
    q = (query or "").strip()
    # 지수/환율 심볼(^KS11, KRW=X 등)은 그대로 통과
    if q.startswith("^") or q.endswith("=X"):
        return {"ticker": q.upper() if q.endswith("=X") else q, "name": q, "market": "INDEX"}
    # 이미 yfinance 티커 형태(영문/숫자 심볼: AAPL, BRK-B, 005930.KS)면 그대로 사용.
    # ※ 한글은 isalpha()가 True라서 isascii()로 걸러야 KRX 조회로 넘어간다.
    if q and q.isascii() and q.replace(".", "").replace("-", "").isalnum():
        EVIDENCE.append({"tool": "resolve_ticker", "input": query, "source": "입력 심볼 그대로", "output": q.upper()})
        return {"ticker": q.upper(), "name": q.upper(), "market": "US/기타"}
    try:
        df = _krx_listing()
        # 컬럼명이 버전마다 다를 수 있어 방어적으로 처리
        name_col = "Name" if "Name" in df.columns else df.columns[1]
        code_col = "Code" if "Code" in df.columns else df.columns[0]
        mkt_col = "Market" if "Market" in df.columns else None
        hit = df[df[name_col].astype(str).str.replace(" ", "") == q.replace(" ", "")]
        if hit.empty:  # 부분일치 fallback
            hit = df[df[name_col].astype(str).str.contains(q, na=False)]
        if hit.empty:
            EVIDENCE.append({"tool": "resolve_ticker", "input": query, "source": "KRX 목록", "output": "찾지 못함"})
            return {"error": f"'{query}' 종목을 찾을 수 없습니다."}
        row = hit.iloc[0]
        code = str(row[code_col]).zfill(6)
        market = str(row[mkt_col]) if mkt_col else "KOSPI"
        suffix = ".KQ" if "KOSDAQ" in market.upper() else ".KS"
        ticker = code + suffix
        EVIDENCE.append({"tool": "resolve_ticker", "input": query, "source": "KRX 종목목록", "output": f"{row[name_col]} → {ticker}"})
        return {"ticker": ticker, "name": str(row[name_col]), "market": market}
    except Exception as e:
        return {"error": f"종목 변환 실패: {e}"}


def _history(ticker: str, period: str = "1y"):
    """yfinance OHLCV 히스토리(공통 헬퍼)."""
    return yf.Ticker(ticker).history(period=period)


def get_price(ticker: str) -> dict:
    """티커의 시세 요약: 현재가, 기간 수익률(1주·1개월·3개월·1년), 52주 위치, 거래량.

    Args:
        ticker: yfinance 호환 티커(예: '005930.KS', 'AAPL'). resolve_ticker 결과를 사용할 것.

    Returns:
        현재가/통화/기간수익률/52주 고저·위치/거래량 등.
    """
    try:
        h = _history(ticker, "1y")
        if h.empty:
            EVIDENCE.append({"tool": "get_price", "input": ticker, "source": "yfinance", "output": "데이터 없음"})
            return {"error": f"{ticker} 시세 데이터를 찾을 수 없습니다."}
        c = h["Close"]
        last = float(c.iloc[-1])

        def ret(n):
            return round((last / float(c.iloc[-1 - n]) - 1) * 100, 2) if len(c) > n else None

        hi, lo = float(c.max()), float(c.min())
        pos = round((last - lo) / (hi - lo) * 100, 1) if hi > lo else None
        cur = "KRW" if ticker.endswith((".KS", ".KQ")) else "USD"
        out = {"ticker": ticker, "as_of": str(h.index[-1].date()), "currency": cur,
               "last_close": round(last, 2),
               "return_1w_pct": ret(5), "return_1m_pct": ret(21),
               "return_3m_pct": ret(63),
               "return_1y_pct": (round((last / float(c.iloc[0]) - 1) * 100, 2) if len(c) > 200 else None),
               "week52_high": round(hi, 2), "week52_low": round(lo, 2), "week52_position_pct": pos,
               "volume": int(h["Volume"].iloc[-1]), "avg_volume_20d": int(h["Volume"].tail(20).mean())}
        EVIDENCE.append({"tool": "get_price", "input": ticker, "source": f"yfinance ({out['as_of']})",
                         "output": f"종가 {out['last_close']} {cur}, 1M {out['return_1m_pct']}%, 52주위치 {pos}%"})
        return out
    except Exception as e:
        return {"error": f"시세 조회 실패: {e}"}


def get_technicals(ticker: str) -> dict:
    """기술적 지표: 이동평균(20/60/120), RSI(14), 정/역배열·골든/데드크로스 신호.

    Args:
        ticker: yfinance 호환 티커. resolve_ticker 결과를 사용할 것.

    Returns:
        RSI14/RSI_state, MA20/60/120, vs_MA20, cross_signal, as_of.
    """
    try:
        h = _history(ticker, "1y")
        if h.empty or len(h) < 20:
            EVIDENCE.append({"tool": "get_technicals", "input": ticker, "source": "yfinance", "output": "데이터 부족"})
            return {"error": f"{ticker} 기술적 지표 계산용 데이터가 부족합니다."}
        c = h["Close"]
        last = float(c.iloc[-1])
        ma = lambda n: round(float(c.rolling(n).mean().iloc[-1]), 2) if len(c) >= n else None
        ma20, ma60, ma120 = ma(20), ma(60), ma(120)
        # RSI(14)
        d = c.diff()
        gain = d.clip(lower=0).rolling(14).mean()
        loss = (-d.clip(upper=0)).rolling(14).mean()
        last_loss = float(loss.iloc[-1])
        rsi = 100.0 if last_loss == 0 else round(float((100 - 100 / (1 + gain / loss)).iloc[-1]), 1)
        rsi_state = "과매수(>70)" if rsi >= 70 else "과매도(<30)" if rsi <= 30 else "중립"
        # MA20 vs MA60 크로스
        cross = "데이터 부족"
        if len(c) >= 60:
            m20, m60 = c.rolling(20).mean(), c.rolling(60).mean()
            now, prev = m20.iloc[-1] - m60.iloc[-1], m20.iloc[-6] - m60.iloc[-6]
            if prev <= 0 < now:
                cross = "골든크로스(최근 상향돌파)"
            elif prev >= 0 > now:
                cross = "데드크로스(최근 하향돌파)"
            else:
                cross = "정배열(MA20>MA60)" if now > 0 else "역배열(MA20<MA60)"
        out = {"ticker": ticker, "as_of": str(h.index[-1].date()),
               "RSI14": rsi, "RSI_state": rsi_state,
               "MA20": ma20, "MA60": ma60, "MA120": ma120,
               "vs_MA20": "MA20 위" if (ma20 and last > ma20) else "MA20 아래",
               "cross_signal": cross}
        EVIDENCE.append({"tool": "get_technicals", "input": ticker, "source": f"yfinance ({out['as_of']})",
                         "output": f"RSI {rsi}({rsi_state}), {cross}"})
        return out
    except Exception as e:
        return {"error": f"기술적 지표 계산 실패: {e}"}


def get_financial_trend(ticker: str, freq: str = "annual") -> dict:
    """매출·영업이익·순이익 추이와 직전대비 성장률(yfinance 재무제표).

    Args:
        ticker: yfinance 호환 티커. resolve_ticker 결과를 사용할 것.
        freq: 'annual'(연간) 또는 'quarter'(분기).

    Returns:
        revenue/operating_income/net_income 기간별 값 + 각 성장률(%), freq.
    """
    try:
        t = yf.Ticker(ticker)
        fin = t.quarterly_income_stmt if freq == "quarter" else t.income_stmt
        if fin is None or fin.empty:
            EVIDENCE.append({"tool": "get_financial_trend", "input": ticker, "source": "yfinance", "output": "재무제표 없음"})
            return {"error": f"{ticker} 재무제표를 찾을 수 없습니다."}
        cols = list(fin.columns)[:4]

        def row(names):
            for n in names:
                if n in fin.index:
                    return fin.loc[n]
            return None

        def label(col):
            if freq == "quarter" and hasattr(col, "year"):
                return f"{str(col.year)[2:]}.{col.month:02d}"
            return str(getattr(col, "year", col))

        def series(r):
            if r is None:
                return None
            return [{"year": label(col), "value": (int(r[col]) if pd.notna(r[col]) else None)} for col in cols]

        def yoy(r):
            if r is None or len(cols) < 2:
                return None
            try:
                cur, prev = float(r[cols[0]]), float(r[cols[1]])
                return round((cur / prev - 1) * 100, 1) if prev else None
            except Exception:
                return None

        rev, op, ni = row(["Total Revenue", "TotalRevenue"]), row(["Operating Income", "OperatingIncome"]), row(["Net Income", "NetIncome"])
        out = {"ticker": ticker, "freq": freq,
               "revenue": series(rev), "revenue_yoy_pct": yoy(rev),
               "operating_income": series(op), "operating_income_yoy_pct": yoy(op),
               "net_income": series(ni), "net_income_yoy_pct": yoy(ni)}
        if all(out[k] is None for k in ("revenue", "operating_income", "net_income")):
            return {"error": f"{ticker} 재무 추세 데이터를 찾을 수 없습니다."}
        EVIDENCE.append({"tool": "get_financial_trend", "input": ticker, "source": f"yfinance 재무제표({freq})",
                         "output": f"매출 YoY {out['revenue_yoy_pct']}%, 영업이익 YoY {out['operating_income_yoy_pct']}%"})
        return out
    except Exception as e:
        return {"error": f"재무 추세 조회 실패: {e}"}


_REC_KR = {"strong_buy": "적극 매수", "buy": "매수", "hold": "보유",
           "sell": "매도", "strong_sell": "적극 매도", "underperform": "시장수익률 하회",
           "outperform": "시장수익률 상회", "none": "의견 없음"}


def get_analyst(ticker: str) -> dict:
    """애널리스트 컨센서스: 목표주가(평균/고/저), 상승여력, 투자의견, 애널리스트 수.

    Args:
        ticker: yfinance 호환 티커. resolve_ticker 결과를 사용할 것.

    Returns:
        target_mean/high/low, upside_pct, recommendation(+한글), num_analysts 등.
        (yfinance 커버리지 한계로 한국 종목 등은 비어 있을 수 있음)
    """
    try:
        info = yf.Ticker(ticker).info or {}
        out = {}
        for k, label in {"targetMeanPrice": "target_mean", "targetHighPrice": "target_high",
                         "targetLowPrice": "target_low", "numberOfAnalystOpinions": "num_analysts",
                         "recommendationKey": "recommendation", "recommendationMean": "rec_mean"}.items():
            if info.get(k) is not None:
                out[label] = info.get(k)
        last = info.get("currentPrice") or info.get("regularMarketPrice")
        if out.get("target_mean") and last:
            out["upside_pct"] = round((out["target_mean"] / last - 1) * 100, 1)
        if out.get("recommendation"):
            out["recommendation_kr"] = _REC_KR.get(str(out["recommendation"]).lower(), out["recommendation"])
        out["currency"] = "KRW" if ticker.endswith((".KS", ".KQ")) else "USD"
        if not out.get("target_mean") and not out.get("recommendation"):
            EVIDENCE.append({"tool": "get_analyst", "input": ticker, "source": "yfinance", "output": "컨센서스 없음"})
            return {"error": f"{ticker} 애널리스트 컨센서스가 없습니다(커버리지 제한)."}
        EVIDENCE.append({"tool": "get_analyst", "input": ticker, "source": "yfinance(애널리스트)",
                         "output": f"목표가 {out.get('target_mean')}, 의견 {out.get('recommendation_kr', '-')}, {out.get('num_analysts', '?')}명"})
        return out
    except Exception as e:
        return {"error": f"컨센서스 조회 실패: {e}"}


SECTOR_KO = {
    "Technology": "기술", "Financial Services": "금융", "Healthcare": "헬스케어",
    "Consumer Cyclical": "경기소비재", "Consumer Defensive": "필수소비재",
    "Communication Services": "커뮤니케이션", "Industrials": "산업재",
    "Energy": "에너지", "Basic Materials": "소재", "Real Estate": "부동산", "Utilities": "유틸리티",
}
INDUSTRY_KO = {
    "Semiconductors": "반도체", "Semiconductor Equipment & Materials": "반도체 장비·소재",
    "Consumer Electronics": "가전·전자", "Software - Infrastructure": "인프라 소프트웨어",
    "Software - Application": "응용 소프트웨어", "Information Technology Services": "IT 서비스",
    "Internet Content & Information": "인터넷 콘텐츠", "Internet Retail": "인터넷 소매",
    "Auto Manufacturers": "자동차", "Auto Parts": "자동차 부품",
    "Banks - Diversified": "은행", "Banks - Regional": "지방은행", "Asset Management": "자산운용",
    "Insurance - Diversified": "보험", "Credit Services": "여신·결제",
    "Drug Manufacturers - General": "제약", "Drug Manufacturers - Specialty & Generic": "제약(전문·제네릭)",
    "Biotechnology": "바이오", "Medical Devices": "의료기기",
    "Beverages - Non-Alcoholic": "음료(무알콜)", "Beverages - Alcoholic": "주류",
    "Packaged Foods": "식품", "Confectioners": "제과", "Discount Stores": "할인소매",
    "Oil & Gas Integrated": "석유·가스(종합)", "Oil & Gas E&P": "석유·가스(개발)", "Oil & Gas Midstream": "석유·가스(수송)",
    "Specialty Chemicals": "특수화학", "Chemicals": "화학", "Steel": "철강", "Aluminum": "알루미늄",
    "Aerospace & Defense": "항공·방산", "Specialty Industrial Machinery": "산업기계",
    "Telecom Services": "통신", "Entertainment": "엔터테인먼트", "Apparel Retail": "의류소매",
    "Luxury Goods": "명품", "Household & Personal Products": "생활용품",
    "Travel Services": "여행", "Restaurants": "외식", "Airlines": "항공",
    "Utilities - Regulated Electric": "전력", "REIT - Diversified": "리츠",
}


def ko_sector(sector, industry=None):
    """섹터/산업을 한국어로(산업이 더 구체적이면 산업 우선)."""
    if industry and industry in INDUSTRY_KO:
        return INDUSTRY_KO[industry]
    if sector in SECTOR_KO:
        return SECTOR_KO[sector]
    return industry or sector or "—"


_INDICES = [("^KS11", "코스피"), ("^KQ11", "코스닥"), ("^IXIC", "나스닥"),
            ("^GSPC", "S&P 500"), ("^DJI", "다우"), ("^N225", "닛케이225"), ("KRW=X", "원/달러")]


def get_market_indices() -> dict:
    """주요 지수·환율(코스피·코스닥·나스닥·S&P·다우·닛케이·원달러) 현재값·등락률."""
    out = []
    for sym, name in _INDICES:
        try:
            h = yf.Ticker(sym).history(period="5d")
            if h.empty:
                continue
            last = float(h["Close"].iloc[-1])
            prev = float(h["Close"].iloc[-2]) if len(h) >= 2 else last
            out.append({"name": name, "symbol": sym, "last": round(last, 2),
                        "change_pct": round((last / prev - 1) * 100, 2) if prev else None})
        except Exception:
            continue
    return {"indices": out}


def get_profile(ticker: str) -> dict:
    """기업 개요: 섹터·산업·사업 요약·직원수·본사 국가·홈페이지(이 회사가 무엇을 하는지).

    Args:
        ticker: yfinance 호환 티커.

    Returns:
        sector/industry/summary/employees/country/website.
    """
    try:
        info = yf.Ticker(ticker).info or {}
        summary = info.get("longBusinessSummary")
        out = {"sector": info.get("sector"), "industry": info.get("industry"),
               "sector_ko": ko_sector(info.get("sector"), info.get("industry")),
               "summary": summary, "employees": info.get("fullTimeEmployees"),
               "country": info.get("country"), "website": info.get("website")}
        if not (summary or out.get("industry")):
            return {"error": f"{ticker} 기업 개요를 찾을 수 없습니다."}
        EVIDENCE.append({"tool": "get_profile", "input": ticker, "source": "yfinance(기업개요)",
                         "output": f"{out.get('sector')}/{out.get('industry')}"})
        return out
    except Exception as e:
        return {"error": f"기업 개요 조회 실패: {e}"}


def get_recommendations(ticker: str) -> dict:
    """최근 애널리스트 등급 변경 이력(증권사·상향/하향·등급)을 조회한다.

    Args:
        ticker: yfinance 호환 티커.

    Returns:
        {"items": [{"date","firm","to","from","action"}, ...]}  (최신순, 합법적 공개 데이터)
    """
    try:
        df = yf.Ticker(ticker).upgrades_downgrades
        if df is None or df.empty:
            EVIDENCE.append({"tool": "get_recommendations", "input": ticker, "source": "yfinance", "output": "등급변경 없음"})
            return {"error": f"{ticker} 애널리스트 등급변경 이력이 없습니다.", "items": []}
        df = df.sort_index(ascending=False).head(8)
        amap = {"up": "상향", "down": "하향", "init": "신규", "main": "유지", "reit": "유지"}
        items = []
        for idx, r in df.iterrows():
            act = str(r.get("Action", "")).lower()
            items.append({"date": str(idx)[:10], "firm": r.get("Firm"),
                          "to": r.get("ToGrade"), "from": r.get("FromGrade"),
                          "action": amap.get(act, act or "-")})
        EVIDENCE.append({"tool": "get_recommendations", "input": ticker, "source": "yfinance(애널리스트 등급변경)",
                         "output": f"최근 {items[0]['firm']} {items[0]['to']}({items[0]['action']}) 등 {len(items)}건"})
        return {"items": items}
    except Exception as e:
        return {"error": f"등급변경 조회 실패: {e}", "items": []}


def get_calendar(ticker: str) -> dict:
    """다음 실적 발표일과 배당 정보(배당수익률·배당락일·배당성향)를 조회한다.

    Args:
        ticker: yfinance 호환 티커. resolve_ticker 결과를 사용할 것.

    Returns:
        next_earnings, dividend_yield_pct, dividend_rate, ex_dividend_date, payout_ratio_pct 등.
    """
    import datetime
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        out = {}
        try:
            cal = t.calendar
            ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if isinstance(ed, (list, tuple)) and ed:
                ed = ed[0]
            if ed is not None:
                out["next_earnings"] = str(ed)
        except Exception:
            pass
        dy = info.get("dividendYield")
        if dy is not None:
            # 현재 yfinance는 dividendYield를 퍼센트값으로 제공(예: 0.38 = 0.38%)
            out["dividend_yield_pct"] = round(dy, 2)
        if info.get("dividendRate") is not None:
            out["dividend_rate"] = info.get("dividendRate")
        exd = info.get("exDividendDate")
        if exd:
            out["ex_dividend_date"] = (str(datetime.datetime.utcfromtimestamp(exd).date())
                                       if isinstance(exd, (int, float)) else str(exd))
        if info.get("payoutRatio") is not None:
            out["payout_ratio_pct"] = round(info["payoutRatio"] * 100, 1)
        if not out:
            EVIDENCE.append({"tool": "get_calendar", "input": ticker, "source": "yfinance", "output": "일정 없음"})
            return {"error": f"{ticker} 실적/배당 일정을 찾을 수 없습니다."}
        EVIDENCE.append({"tool": "get_calendar", "input": ticker, "source": "yfinance(실적·배당)",
                         "output": f"실적 {out.get('next_earnings', '-')}, 배당수익률 {out.get('dividend_yield_pct', '-')}%"})
        return out
    except Exception as e:
        return {"error": f"실적/배당 조회 실패: {e}"}


def get_history(ticker: str, period: str = "6mo") -> dict:
    """차트용 OHLCV 시계열을 반환한다(UI/대시보드 전용). MA20/MA60도 함께 계산.

    Returns:
        {"ticker","period","candles":[{t,o,h,l,c,v,ma20,ma60}, ...]}
    """
    try:
        h = _history(ticker, period)
        if h.empty:
            return {"error": f"{ticker} 히스토리를 찾을 수 없습니다.", "candles": []}
        h = h.copy()
        h["MA20"] = h["Close"].rolling(20).mean()
        h["MA60"] = h["Close"].rolling(60).mean()
        _d = h["Close"].diff()
        _rs = _d.clip(lower=0).rolling(14).mean() / (-_d.clip(upper=0)).rolling(14).mean()
        h["RSI"] = 100 - 100 / (1 + _rs)
        candles = []
        for idx, r in h.iterrows():
            candles.append({"t": str(idx.date()),
                            "o": round(float(r["Open"]), 2), "h": round(float(r["High"]), 2),
                            "l": round(float(r["Low"]), 2), "c": round(float(r["Close"]), 2),
                            "v": int(r["Volume"]),
                            "ma20": (round(float(r["MA20"]), 2) if pd.notna(r["MA20"]) else None),
                            "ma60": (round(float(r["MA60"]), 2) if pd.notna(r["MA60"]) else None),
                            "rsi": (round(float(r["RSI"]), 1) if pd.notna(r["RSI"]) else None)})
        return {"ticker": ticker, "period": period, "candles": candles}
    except Exception as e:
        return {"error": f"히스토리 조회 실패: {e}", "candles": []}


def get_financials(ticker: str) -> dict:
    """티커의 핵심 밸류에이션/재무 지표를 조회한다(PER, PBR, 시가총액, 배당수익률 등).

    Args:
        ticker: yfinance 호환 티커.

    Returns:
        주요 지표 딕셔너리(없는 값은 생략될 수 있음).
    """
    try:
        info = yf.Ticker(ticker).info or {}
        keys = {"trailingPE": "PER", "priceToBook": "PBR", "marketCap": "시가총액",
                "dividendYield": "배당수익률", "returnOnEquity": "ROE",
                "fiftyTwoWeekHigh": "52주최고", "fiftyTwoWeekLow": "52주최저",
                "sector": "섹터", "longName": "회사명"}
        out = {label: info.get(k) for k, label in keys.items() if info.get(k) is not None}
        if not out:
            EVIDENCE.append({"tool": "get_financials", "input": ticker, "source": "yfinance", "output": "지표 없음"})
            return {"error": f"{ticker} 재무 지표를 찾을 수 없습니다."}
        # yfinance .info 는 정확한 기준일을 주지 않는다 → 모델이 날짜를 지어내지 않도록 명시
        out["기준일"] = "미제공(yfinance .info 최신값)"
        # 한국 종목은 yfinance가 PER/PBR을 비워두는 경우가 많음 → 별도 도구 안내
        if ticker.endswith((".KS", ".KQ")) and "PER" not in out:
            out["참고"] = "한국 종목 PER/PBR은 get_kr_fundamentals를 사용하세요."
        EVIDENCE.append({"tool": "get_financials", "input": ticker, "source": "yfinance .info(기준일 미제공)",
                         "output": ", ".join(f"{k}={v}" for k, v in out.items() if k in ("PER", "PBR", "시가총액"))})
        return out
    except Exception as e:
        return {"error": f"재무 조회 실패: {e}"}


def get_kr_fundamentals(ticker: str) -> dict:
    """한국 종목의 PER/PBR/EPS/BPS/시가총액을 네이버 금융에서 조회한다.

    yfinance가 한국 종목의 PER/PBR을 비워둘 때 사용한다(미국 종목엔 쓰지 말 것).

    Args:
        ticker: 한국 티커(예: '005930.KS', '000660.KQ'). resolve_ticker 결과를 사용.

    Returns:
        {"PER": ..., "PBR": ..., "EPS": ..., "BPS": ..., "시가총액": ...} (네이버 금융 실시간 지표)
    """
    if not ticker.endswith((".KS", ".KQ")):
        return {"error": "한국 종목 전용 도구입니다(.KS/.KQ 티커). 해외는 get_financials를 사용하세요."}
    try:
        code = ticker.split(".")[0]
        url = f"https://m.stock.naver.com/api/stock/{code}/integration"
        data = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).json()
        infos = {i.get("code"): i.get("value") for i in data.get("totalInfos", [])}

        def num(s):  # "25.78배" → 25.78 / "12,372원" → 12372.0
            if not s:
                return None
            cleaned = re.sub(r"[^0-9.\-]", "", str(s))
            return float(cleaned) if cleaned not in ("", ".", "-") else None

        out = {}
        if num(infos.get("per")) is not None:
            out["PER"] = num(infos.get("per"))
        if num(infos.get("pbr")) is not None:
            out["PBR"] = num(infos.get("pbr"))
        if num(infos.get("eps")) is not None:
            out["EPS"] = int(num(infos.get("eps")))
        if num(infos.get("bps")) is not None:
            out["BPS"] = int(num(infos.get("bps")))
        if infos.get("marketValue"):
            out["시가총액"] = infos.get("marketValue")  # "1,864조 9,629억"
        if num(infos.get("dvr")) is not None:
            out["배당수익률"] = num(infos.get("dvr"))
        if not out:
            EVIDENCE.append({"tool": "get_kr_fundamentals", "input": ticker, "source": "네이버 금융", "output": "지표 없음"})
            return {"error": f"{ticker} 한국 지표를 찾을 수 없습니다."}
        out["기준"] = "네이버 금융 실시간 지표(정확한 기준일 미제공)"
        EVIDENCE.append({"tool": "get_kr_fundamentals", "input": ticker, "source": "네이버 금융",
                         "output": ", ".join(f"{k}={v}" for k, v in out.items() if k in ("PER", "PBR", "시가총액"))})
        return out
    except Exception as e:
        return {"error": f"한국 지표 조회 실패: {e}"}


def get_news(ticker: str, limit: int = 5) -> dict:
    """티커 관련 최신 뉴스 제목/출처/링크를 조회한다.

    Args:
        ticker: yfinance 호환 티커.
        limit: 가져올 뉴스 개수(기본 5).

    Returns:
        {"news": [{"title":..., "publisher":..., "link":...}, ...]}
    """
    try:
        raw = yf.Ticker(ticker).news or []
        items = []
        for n in raw[:limit]:
            # yfinance 뉴스 포맷이 버전에 따라 평면/중첩으로 다름 → 둘 다 대응
            c = n.get("content", n)
            title = c.get("title") or n.get("title")
            pub = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else n.get("publisher")
            link = (c.get("canonicalUrl") or {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else n.get("link")
            if title:
                items.append({"title": title, "publisher": pub, "link": link})
        if not items:
            EVIDENCE.append({"tool": "get_news", "input": ticker, "source": "yfinance news", "output": "뉴스 없음"})
            return {"news": [], "note": "관련 뉴스를 찾지 못했습니다."}
        for it in items:
            EVIDENCE.append({"tool": "get_news", "input": ticker, "source": it.get("publisher") or "뉴스",
                             "output": it["title"], "link": it.get("link")})
        return {"news": items}
    except Exception as e:
        return {"error": f"뉴스 조회 실패: {e}"}


def attractiveness_score(price, tech, fund, analyst):
    """단순 규칙 기반 투자매력 점수(0~100, 4요소 ×25). 투명·정보제공용(투자조언 아님)."""
    c = {}
    r3 = (price or {}).get("return_3m_pct")
    c["모멘텀"] = max(0, min(25, round(12.5 + (r3 or 0) * 0.6, 1))) if r3 is not None else 12
    tr = 12.0
    if tech:
        if tech.get("vs_MA20") == "MA20 위":
            tr += 6
        cs = tech.get("cross_signal", "")
        if "골든" in cs or "정배열" in cs:
            tr += 5
        elif "데드" in cs or "역배열" in cs:
            tr -= 4
        rsi = tech.get("RSI14")
        if rsi is not None and 40 <= rsi <= 65:
            tr += 2
    c["추세"] = max(0, min(25, tr))
    per = (fund or {}).get("PER")
    c["밸류"] = (12 if per is None else 25 if per <= 10 else 19 if per <= 20 else 13 if per <= 30 else 7 if per <= 50 else 4)
    up = (analyst or {}).get("upside_pct")
    c["애널"] = 12 if up is None else max(0, min(25, round(12 + up * 0.45, 1)))
    total = round(sum(c.values()), 1)
    label = "매력적" if total >= 68 else "보통" if total >= 45 else "주의"
    return {"score": total, "label": label, "breakdown": c}


# ── DART(전자공시) 한국 기업 재무 ──
_DART_MAP = None


def _dart_corp_map():
    """주식코드(6자리)→corp_code 매핑. corpCode.xml 1회 다운로드 후 파일 캐시."""
    global _DART_MAP
    if _DART_MAP is not None:
        return _DART_MAP
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dart_corp.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            _DART_MAP = json.load(f)
        return _DART_MAP
    key = os.environ.get("DART_API_KEY")
    _DART_MAP = {}
    if not key:
        return _DART_MAP
    try:
        r = requests.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": key}, timeout=30)
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        root = ET.fromstring(zf.read(zf.namelist()[0]))
        for el in root.iter("list"):
            sc = (el.findtext("stock_code") or "").strip()
            cc = (el.findtext("corp_code") or "").strip()
            if sc and cc:
                _DART_MAP[sc] = cc
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_DART_MAP, f)
    except Exception:
        pass
    return _DART_MAP


def get_dart_financials(ticker: str) -> dict:
    """한국 기업의 연간 매출·영업이익·순이익(3개년)을 DART 전자공시에서 조회(공식·정확).

    Args:
        ticker: 한국 티커('005930.KS' 등). 한국 외에는 사용 불가.

    Returns:
        revenue/operating_income/net_income 연도별 + 성장률(get_financial_trend와 동일 포맷), source=DART.
    """
    if not ticker.endswith((".KS", ".KQ")):
        return {"error": "DART는 한국 종목 전용입니다."}
    key = os.environ.get("DART_API_KEY")
    if not key:
        return {"error": "DART_API_KEY가 없습니다(.env)."}
    code = ticker.split(".")[0]
    corp = _dart_corp_map().get(code)
    if not corp:
        return {"error": f"{ticker} DART corp_code를 찾지 못했습니다."}

    def fetch(year):
        try:
            d = requests.get("https://opendart.fss.or.kr/api/fnlttSinglAcnt.json",
                             params={"crtfc_key": key, "corp_code": corp, "bsns_year": str(year), "reprt_code": "11011"},
                             timeout=15).json()
            return d.get("list", []) if d.get("status") == "000" else None
        except Exception:
            return None

    import datetime
    rows = None
    for y in (datetime.date.today().year, datetime.date.today().year - 1):
        rows = fetch(y)
        if rows:
            break
    if not rows:
        return {"error": f"{ticker} DART 재무 데이터를 찾지 못했습니다."}

    def num(s):
        try:
            return int(str(s).replace(",", ""))
        except Exception:
            return None

    want = {"매출액": "revenue", "영업이익": "operating_income", "당기순이익": "net_income"}
    acc = {v: {} for v in want.values()}
    yrs = set()
    # thstrm/frmtrm/bfefrmtrm = 당기/전기/전전기 → 3개년
    base_year = int(rows[0].get("bsns_year", 0)) if rows else 0
    year_for = {"thstrm_amount": base_year, "frmtrm_amount": base_year - 1, "bfefrmtrm_amount": base_year - 2}
    for it in rows:
        if it.get("fs_div") != "CFS":
            continue
        kn = want.get(it.get("account_nm"))
        if not kn:
            continue
        for amt_key, yr in year_for.items():
            v = num(it.get(amt_key))
            if v is not None and yr:
                acc[kn][yr] = v
                yrs.add(yr)
    if not yrs:
        return {"error": f"{ticker} DART 재무 항목을 파싱하지 못했습니다."}
    years = sorted(yrs, reverse=True)[:3]

    def series(metric):
        s = [{"year": str(y), "value": acc[metric].get(y)} for y in years]
        return s if any(x["value"] is not None for x in s) else None

    def yoy(metric):
        if len(years) >= 2 and acc[metric].get(years[0]) and acc[metric].get(years[1]):
            return round((acc[metric][years[0]] / acc[metric][years[1]] - 1) * 100, 1)
        return None

    out = {"ticker": ticker, "freq": "annual", "source": "DART",
           "revenue": series("revenue"), "revenue_yoy_pct": yoy("revenue"),
           "operating_income": series("operating_income"), "operating_income_yoy_pct": yoy("operating_income"),
           "net_income": series("net_income"), "net_income_yoy_pct": yoy("net_income")}
    EVIDENCE.append({"tool": "get_dart_financials", "input": ticker, "source": "DART 전자공시(연결)",
                     "output": f"매출 YoY {out['revenue_yoy_pct']}%, 영업이익 YoY {out['operating_income_yoy_pct']}%"})
    return out


def get_naver_news(query: str, display: int = 6) -> dict:
    """네이버 뉴스 검색 API로 한국어 뉴스를 조회한다(한국 종목에 적합).

    Args:
        query: 검색어(회사명 권장, 예: '삼성전자').
        display: 가져올 개수(기본 6).

    Returns:
        {"news": [{"title","publisher","link"}, ...]}  (한국어 제목)
    """
    cid, csec = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        return {"error": "NAVER API 키가 없습니다(.env의 NAVER_CLIENT_ID/SECRET).", "news": []}
    try:
        r = requests.get("https://openapi.naver.com/v1/search/news.json",
                         params={"query": query, "display": display, "sort": "date"},
                         headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}, timeout=15)
        items = []
        for it in r.json().get("items", []):
            title = html.unescape(re.sub(r"<[^>]+>", "", it.get("title", "")))
            items.append({"title": title, "publisher": it.get("pubDate", "")[:16],
                          "link": it.get("originallink") or it.get("link")})
        if not items:
            return {"news": [], "note": "관련 뉴스를 찾지 못했습니다."}
        for it in items:
            EVIDENCE.append({"tool": "get_naver_news", "input": query, "source": "네이버 뉴스",
                             "output": it["title"], "link": it["link"]})
        return {"news": items}
    except Exception as e:
        return {"error": f"네이버 뉴스 조회 실패: {e}", "news": []}


TOOLS = [resolve_ticker, get_profile, get_price, get_financials, get_kr_fundamentals,
         get_technicals, get_financial_trend, get_dart_financials, get_analyst, get_recommendations,
         get_calendar, get_naver_news, get_news]
