# -*- coding: utf-8 -*-
"""
FastAPI 백엔드 — React 프론트에 데이터/AI를 제공한다.
- GET  /api/dashboard?query=삼성전자  : 시세·기술·재무·차트·뉴스를 한 번에 (LLM 불필요 → 빠르고 쿼터 0)
- POST /api/chat {question}          : 에이전트(GitHub Models/Gemini) AI 리서치
- 빌드된 React(frontend/dist)가 있으면 정적 서빙(프로덕션/HF).
"""
import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
import tools
from agent import build_agent, ask

app = FastAPI(title="Investment Research Agent API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_AGENT = None


def _agent():
    global _AGENT
    if _AGENT is None:
        _AGENT = build_agent()
    return _AGENT


@app.get("/api/health")
def health():
    return {"ok": True, "provider": os.environ.get("LLM_PROVIDER", "gemini")}


_DASH_CACHE = {}
_DASH_TTL = 60  # 초 — 같은 종목 반복 조회 시 yfinance 재호출 방지


@app.get("/api/dashboard")
def dashboard(query: str, period: str = "6mo"):
    """종목 1개의 대시보드 데이터 묶음(LLM 미사용). 60초 TTL 캐시."""
    key = (query.strip().lower(), period)
    hit = _DASH_CACHE.get(key)
    if hit and time.time() - hit[0] < _DASH_TTL:
        return hit[1]
    r = tools.resolve_ticker(query)
    if "error" in r:
        return {"error": r["error"]}
    tk = r["ticker"]
    is_kr = tk.endswith((".KS", ".KQ"))
    result = {
        "ticker": tk, "name": r.get("name"), "market": r.get("market"),
        "profile": tools.get_profile(tk),
        "price": tools.get_price(tk),
        "technicals": tools.get_technicals(tk),
        "fundamentals": (tools.get_kr_fundamentals(tk) if is_kr else tools.get_financials(tk)),
        "financial_trend": tools.get_financial_trend(tk),
        "analyst": tools.get_analyst(tk),
        "recommendations": tools.get_recommendations(tk),
        "calendar": tools.get_calendar(tk),
        "history": tools.get_history(tk, period),
        "news": (tools.get_naver_news(r.get("name") or tk) if is_kr else tools.get_news(tk, 6)),
    }
    _DASH_CACHE[key] = (time.time(), result)
    return result


@app.get("/api/compare")
def compare(tickers: str, period: str = "6mo"):
    """2~4개 종목 비교: 핵심 지표 + 정규화(100 기준) 가격 시계열."""
    syms = [s.strip() for s in tickers.split(",") if s.strip()][:4]
    items = []
    for q in syms:
        r = tools.resolve_ticker(q)
        if "error" in r:
            items.append({"query": q, "error": r["error"]})
            continue
        tk = r["ticker"]
        is_kr = tk.endswith((".KS", ".KQ"))
        price = tools.get_price(tk)
        tech = tools.get_technicals(tk)
        fund = tools.get_kr_fundamentals(tk) if is_kr else tools.get_financials(tk)
        candles = tools.get_history(tk, period).get("candles", [])
        base = candles[0]["c"] if candles else None
        norm = [{"t": c["t"], "v": round(c["c"] / base * 100, 2)} for c in candles] if base else []
        items.append({
            "query": q, "ticker": tk, "name": r.get("name"), "currency": price.get("currency"),
            "last": price.get("last_close"),
            "return_1m": price.get("return_1m_pct"), "return_3m": price.get("return_3m_pct"), "return_1y": price.get("return_1y_pct"),
            "PER": fund.get("PER"), "PBR": fund.get("PBR"), "RSI": tech.get("RSI14"),
            "marketcap": fund.get("시가총액") or fund.get("marketCap"),
            "norm": norm,
        })
    return {"items": items, "period": period}


import json as _json

_UNIVERSE = None


def _load_universe():
    global _UNIVERSE
    if _UNIVERSE is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "universe.json")
        try:
            with open(path, encoding="utf-8") as f:
                _UNIVERSE = _json.load(f)
        except Exception:
            _UNIVERSE = {"as_of": None, "rows": []}
    return _UNIVERSE


@app.get("/api/screener")
def screener(market: str = "all", per_max: float = None, ret1m_min: float = None,
             rsi_min: float = None, rsi_max: float = None, sort: str = "marketcap"):
    """사전계산 유니버스에서 조건 필터링(일배치 기준). market: all|KR|US"""
    u = _load_universe()
    rows = list(u.get("rows", []))
    if market in ("KR", "US"):
        rows = [r for r in rows if r.get("market") == market]
    if per_max is not None:
        rows = [r for r in rows if r.get("PER") is not None and r["PER"] <= per_max]
    if ret1m_min is not None:
        rows = [r for r in rows if r.get("return_1m") is not None and r["return_1m"] >= ret1m_min]
    if rsi_min is not None:
        rows = [r for r in rows if r.get("RSI") is not None and r["RSI"] >= rsi_min]
    if rsi_max is not None:
        rows = [r for r in rows if r.get("RSI") is not None and r["RSI"] <= rsi_max]
    key = {"marketcap": "marketcap", "return": "return_1m", "per": "PER", "rsi": "RSI"}.get(sort, "marketcap")
    rows.sort(key=lambda r: (r.get(key) is None, -(r.get(key) or 0) if sort != "per" else (r.get(key) or 1e9)))
    return {"as_of": u.get("as_of"), "count": len(rows), "rows": rows}


@app.get("/api/ranking")
def ranking(by: str = "marketcap", country: str = "all", sector: str = "all"):
    """글로벌 유니버스 랭킹/비교. by: marketcap(USD)|return. country/sector 필터."""
    u = _load_universe()
    rows = [dict(r) for r in u.get("rows", [])]
    if country != "all":
        rows = [r for r in rows if r.get("country") == country]
    if sector != "all":
        rows = [r for r in rows if r.get("sector") == sector]
    if by == "return":
        rows.sort(key=lambda r: (r.get("return_1m") is None, -(r.get("return_1m") or 0)))
    else:
        rows.sort(key=lambda r: (r.get("marketcap_usd") is None, -(r.get("marketcap_usd") or 0)))
    countries = sorted({r.get("country") for r in u.get("rows", []) if r.get("country")})
    sectors = sorted({r.get("sector") for r in u.get("rows", []) if r.get("sector")})
    # 나라별 시총 합계(USD)
    by_country = {}
    for r in u.get("rows", []):
        c = r.get("country"); mc = r.get("marketcap_usd")
        if c and mc:
            by_country[c] = by_country.get(c, 0) + mc
    return {"as_of": u.get("as_of"), "rows": rows, "countries": countries, "sectors": sectors,
            "by_country": sorted(by_country.items(), key=lambda x: -x[1])}


@app.get("/api/quotes")
def quotes(tickers: str):
    """여러 종목의 현재가(포트폴리오 평가용). 최대 30개."""
    out = []
    for q in [s.strip() for s in tickers.split(",") if s.strip()][:30]:
        r = tools.resolve_ticker(q)
        if "error" in r:
            out.append({"query": q, "error": r["error"]})
            continue
        p = tools.get_price(r["ticker"])
        out.append({"query": q, "ticker": r["ticker"], "name": r.get("name"),
                    "last": p.get("last_close"), "currency": p.get("currency"),
                    "return_1m": p.get("return_1m_pct")})
    return {"quotes": out}


@app.get("/api/news_sentiment")
def news_sentiment(query: str):
    """종목 뉴스 헤드라인을 LLM으로 긍정/부정/중립 분류(온디맨드)."""
    import re as _re
    r = tools.resolve_ticker(query)
    if "error" in r:
        return {"error": r["error"]}
    tk = r["ticker"]
    news = (tools.get_naver_news(r.get("name") or tk) if tk.endswith((".KS", ".KQ"))
            else tools.get_news(tk, 6)).get("news", [])
    if not news:
        return {"items": []}
    titles = [n["title"] for n in news]
    prompt = ("다음 뉴스 헤드라인을 투자 관점에서 긍정/부정/중립 중 하나로 분류해 "
              'JSON 배열로만 답하세요. 형식: [{"i":0,"s":"긍정"}]. 헤드라인:\n'
              + "\n".join(f"{i}. {t}" for i, t in enumerate(titles)))
    from agent import quick_complete
    try:
        raw = quick_complete(prompt)
    except Exception as e:
        return {"error": f"감성분석 실패: {e}", "items": []}
    senti = {}
    m = _re.search(r"\[.*\]", raw or "", _re.S)
    if m:
        try:
            for o in _json.loads(m.group(0)):
                senti[o.get("i")] = o.get("s")
        except Exception:
            pass
    items = [{"title": n["title"], "publisher": n.get("publisher"), "link": n.get("link"),
              "sentiment": senti.get(i, "중립")} for i, n in enumerate(news)]
    return {"items": items}


class ChatReq(BaseModel):
    question: str


@app.post("/api/chat")
def chat(req: ChatReq):
    """자유 질문 → 에이전트 답변 + 근거(EVIDENCE)."""
    try:
        answer, evidence = ask(_agent(), req.question)
        return {"answer": answer, "evidence": evidence}
    except Exception as e:
        return {"answer": f"오류가 발생했습니다: {e}", "evidence": []}


# 프로덕션: 빌드된 React 정적 파일 서빙 (frontend/dist 존재 시)
_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="static")
