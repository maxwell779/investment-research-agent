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
        "history": tools.get_history(tk, period),
        "news": tools.get_news(tk, 6),
    }
    _DASH_CACHE[key] = (time.time(), result)
    return result


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
