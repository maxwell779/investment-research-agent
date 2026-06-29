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


def get_price(ticker: str) -> dict:
    """티커의 최근 시세를 조회한다(최근 종가, 5일 등락률).

    Args:
        ticker: yfinance 호환 티커(예: '005930.KS', 'AAPL'). resolve_ticker 결과를 사용할 것.

    Returns:
        현재가/통화/5일 등락률 등.
    """
    try:
        h = yf.Ticker(ticker).history(period="1mo")
        if h.empty:
            EVIDENCE.append({"tool": "get_price", "input": ticker, "source": "yfinance", "output": "데이터 없음"})
            return {"error": f"{ticker} 시세 데이터를 찾을 수 없습니다."}
        last = float(h["Close"].iloc[-1])
        prev5 = float(h["Close"].iloc[-6]) if len(h) >= 6 else float(h["Close"].iloc[0])
        chg5 = (last - prev5) / prev5 * 100
        cur = "KRW" if ticker.endswith((".KS", ".KQ")) else "USD"
        out = {"ticker": ticker, "last_close": round(last, 2), "currency": cur,
               "pct_change_5d": round(chg5, 2), "as_of": str(h.index[-1].date())}
        EVIDENCE.append({"tool": "get_price", "input": ticker, "source": f"yfinance ({out['as_of']})",
                         "output": f"종가 {out['last_close']} {cur}, 5일 {out['pct_change_5d']}%"})
        return out
    except Exception as e:
        return {"error": f"시세 조회 실패: {e}"}


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


TOOLS = [resolve_ticker, get_price, get_financials, get_kr_fundamentals, get_news]
