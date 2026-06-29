# -*- coding: utf-8 -*-
"""
GitHub Models(무료) 백엔드 — OpenAI 호환 API로 gpt-4o-mini 등을 tool-calling으로 구동.

- 인증: GitHub PAT(Models 권한). https://github.com/settings/tokens 에서 발급 후 .env의 GITHUB_TOKEN.
- 엔드포인트/모델은 env로 교체 가능(기본: models.github.ai/inference, openai/gpt-4o-mini).
- agent.py 와 동일한 인터페이스: build_client() / ask(client, question) → (답변, EVIDENCE)
- tools.py 의 함수를 OpenAI 함수 스키마로 노출하고, 수동 tool-call 루프로 자율 호출한다.
"""
import os
import json
import time
from openai import OpenAI
import tools
from prompts import SYSTEM

BASE_URL = os.environ.get("GITHUB_MODELS_BASE", "https://models.github.ai/inference")
MODEL = os.environ.get("GITHUB_MODEL", "openai/gpt-4o-mini")

# tools.py 함수 → OpenAI 함수 스키마
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "resolve_ticker", "description": "종목명/심볼을 yfinance 티커로 변환(한국명→005930.KS 등).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "종목명(한글) 또는 심볼"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "get_price", "description": "티커의 최근 시세(종가·5일 등락률).",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_financials", "description": "해외 종목 등의 PER/PBR/시총/ROE 등(yfinance).",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_kr_fundamentals", "description": "한국 종목(.KS/.KQ)의 PER/PBR/EPS/BPS/시총(네이버 금융).",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_technicals", "description": "기술적 지표: RSI(14), 이동평균(20/60/120), 정/역배열·골든/데드크로스 신호.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_financial_trend", "description": "최근 연간 매출·영업이익·순이익 추이와 전년대비 성장률.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_analyst", "description": "애널리스트 컨센서스: 목표주가(평균/고/저)·상승여력·투자의견·애널리스트 수.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_calendar", "description": "다음 실적 발표일·배당(배당수익률·배당락일·배당성향).",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_profile", "description": "기업 개요(이 회사가 무엇을 하는지): 섹터·산업·사업요약·직원수·본사국가.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_recommendations", "description": "최근 애널리스트 등급 변경 이력(증권사·상향/하향·등급).",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}}},
    {"type": "function", "function": {
        "name": "get_naver_news", "description": "한국 종목의 한국어 뉴스(네이버 뉴스 API). 한국 종목엔 이걸 우선 사용. query=회사명.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "get_news", "description": "해외 종목 관련 최신 뉴스(영어) 제목/출처/링크.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["ticker"]}}},
]
DISPATCH = {"resolve_ticker": tools.resolve_ticker, "get_profile": tools.get_profile, "get_price": tools.get_price,
            "get_financials": tools.get_financials, "get_kr_fundamentals": tools.get_kr_fundamentals,
            "get_technicals": tools.get_technicals, "get_financial_trend": tools.get_financial_trend,
            "get_analyst": tools.get_analyst, "get_recommendations": tools.get_recommendations,
            "get_calendar": tools.get_calendar,
            "get_naver_news": tools.get_naver_news, "get_news": tools.get_news}


def build_client():
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise RuntimeError("GITHUB_TOKEN이 없습니다. .env에 GitHub Models 토큰을 넣으세요.")
    return OpenAI(base_url=BASE_URL, api_key=tok)


def complete(prompt: str) -> str:
    """도구 없이 단순 1회 완성(감성분석 등)."""
    c = build_client()
    r = c.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0)
    return r.choices[0].message.content or ""


def ask(client, question: str, max_rounds: int = 8):
    """수동 tool-call 루프로 질문을 처리하고 (답변, EVIDENCE)를 반환."""
    tools.EVIDENCE.clear()
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for _ in range(max_rounds):
        try:
            resp = client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto", temperature=0)
        except Exception as e:
            s = str(e)
            if "permission" in s.lower() or "no_access" in s.lower() or "no access" in s.lower():
                raise RuntimeError(
                    "GitHub 토큰에 'Models' 권한이 없습니다. "
                    "GitHub → Settings → Developer settings → Fine-grained tokens → 해당 토큰 → "
                    "Account permissions → 'Models' = Read-only 추가(또는 토큰 재발급) 후 다시 시도하세요. "
                    "([github.com/marketplace/models] 약관 동의도 필요할 수 있습니다.)") from e
            raise
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "(응답 없음)"), list(tools.EVIDENCE)
        # 도구 호출 요청을 대화에 반영
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            fn = DISPATCH.get(tc.function.name)
            try:
                args = json.loads(tc.function.arguments or "{}")
                result = fn(**args) if fn else {"error": f"unknown tool {tc.function.name}"}
            except Exception as e:
                result = {"error": f"도구 실행 오류: {e}"}
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False, default=str)})
    return "(도구 호출 한도를 초과했습니다)", list(tools.EVIDENCE)
