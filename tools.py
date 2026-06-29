# -*- coding: utf-8 -*-
"""
에이전트가 호출하는 도구(tool) 모음 — 전부 무료 데이터 소스.
- 한국주식: 종목명 → 코드 변환 후 yfinance(.KS/.KQ)로 조회 (FinanceDataReader로 종목명 해석)
- 해외주식: yfinance 심볼 그대로 (AAPL, MSFT ...)
- 뉴스: yfinance가 제공하는 최신 뉴스 (무료)

각 도구는 호출될 때 EVIDENCE 에 '무엇을·어디서 가져왔는지'를 남긴다 → 답변 인용(citation)에 사용.
"""
import re
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


def get_financial_trend(ticker: str) -> dict:
    """최근 연간 매출·영업이익·순이익 추이와 전년대비 성장률(yfinance 재무제표).

    Args:
        ticker: yfinance 호환 티커. resolve_ticker 결과를 사용할 것.

    Returns:
        revenue/operating_income/net_income 연도별 값 + 각 YoY 성장률(%).
    """
    try:
        fin = yf.Ticker(ticker).income_stmt
        if fin is None or fin.empty:
            EVIDENCE.append({"tool": "get_financial_trend", "input": ticker, "source": "yfinance", "output": "재무제표 없음"})
            return {"error": f"{ticker} 재무제표를 찾을 수 없습니다."}
        cols = list(fin.columns)[:4]

        def row(names):
            for n in names:
                if n in fin.index:
                    return fin.loc[n]
            return None

        def series(r):
            if r is None:
                return None
            return [{"year": str(getattr(col, "year", col)), "value": (int(r[col]) if pd.notna(r[col]) else None)} for col in cols]

        def yoy(r):
            if r is None or len(cols) < 2:
                return None
            try:
                cur, prev = float(r[cols[0]]), float(r[cols[1]])
                return round((cur / prev - 1) * 100, 1) if prev else None
            except Exception:
                return None

        rev, op, ni = row(["Total Revenue", "TotalRevenue"]), row(["Operating Income", "OperatingIncome"]), row(["Net Income", "NetIncome"])
        out = {"ticker": ticker,
               "revenue": series(rev), "revenue_yoy_pct": yoy(rev),
               "operating_income": series(op), "operating_income_yoy_pct": yoy(op),
               "net_income": series(ni), "net_income_yoy_pct": yoy(ni)}
        if all(out[k] is None for k in ("revenue", "operating_income", "net_income")):
            return {"error": f"{ticker} 재무 추세 데이터를 찾을 수 없습니다."}
        EVIDENCE.append({"tool": "get_financial_trend", "input": ticker, "source": "yfinance 재무제표(연간)",
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


TOOLS = [resolve_ticker, get_price, get_financials, get_kr_fundamentals,
         get_technicals, get_financial_trend, get_analyst, get_calendar, get_news]
