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
        "price": tools.get_price(tk),
        "technicals": tools.get_technicals(tk),
        "fundamentals": (tools.get_kr_fundamentals(tk) if is_kr else tools.get_financials(tk)),
        "financial_trend": tools.get_financial_trend(tk),
        "analyst": tools.get_analyst(tk),
        "calendar": tools.get_calendar(tk),
        "history": tools.get_history(tk, period),
        "news": tools.get_news(tk, 6),
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
