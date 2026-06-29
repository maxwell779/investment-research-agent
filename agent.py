# -*- coding: utf-8 -*-
"""
Gemini function-calling 에이전트 루프 (google-genai 신 SDK).
- 시스템 지침으로 '도구로 실제 데이터를 조회한 뒤에만 답하고, 모든 수치에 출처를 밝히고,
  데이터가 없으면 모른다고 답하라'를 강제한다(= 환각 억제 = 정직성).
- 도구(Python 함수)를 tools 로 넘기면 SDK가 자동 호출(automatic function calling)한다.
  도구가 남긴 EVIDENCE를 답변과 함께 반환해 화면에 출처로 표시한다.
"""
import os
import time
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
import tools

# 일시적 과부하(503)에 대비해 여러 무료 모델로 순차 폴백
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]

SYSTEM = """당신은 한국·해외 주식을 다루는 투자 리서치 어시스턴트입니다. 규칙:
1) 추측 금지. 반드시 제공된 도구로 실제 데이터를 조회한 뒤 답하세요.
   - 한국 종목명이 들어오면 먼저 resolve_ticker로 티커를 구한 뒤 시세/재무/뉴스를 조회하세요.
   - 한국 종목(.KS/.KQ)의 PER/PBR은 get_kr_fundamentals를, 해외 종목은 get_financials를 사용하세요.
2) 답변의 모든 수치(주가·PER·등락률 등)는 도구가 반환한 값만 사용하고, 어떤 도구의 값인지 밝히세요.
3) **날짜 규칙(중요)**: 도구가 'as_of'를 준 경우에만 그 날짜를 인용하세요. as_of가 없는 수치에는 날짜를 절대 지어내거나 붙이지 마세요('기준일 미제공'이면 날짜 언급 금지).
4) 도구가 'error'나 빈 결과를 주면, 지어내지 말고 "해당 데이터를 찾지 못했습니다"라고 정직하게 답하세요.
5) **비교 질문**(예: 'A vs B')이면 두 종목 각각에 대해 도구를 호출해 데이터를 모은 뒤, 표 형태로 핵심 지표를 나란히 비교하세요.
6) 답변은 한국어로, 간결한 요약 + 근거 수치 순으로.
7) 답변 끝에 반드시 줄바꿈 후 "※ 정보 제공용이며 투자 조언이 아닙니다."를 붙이세요.
"""


def build_agent():
    """API 키로 클라이언트를 만들고 (client, config)를 반환한다."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY가 없습니다. .env를 만들고 키를 넣으세요(.env.example 참고).")
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(system_instruction=SYSTEM, tools=tools.TOOLS)
    return client, config


def ask(agent, question: str):
    """질문 1건을 처리하고 (답변텍스트, 근거리스트)를 반환한다.

    503(과부하) 등 일시적 오류는 모델을 바꿔가며 재시도한다.
    """
    client, config = agent
    last_err = None
    for model in MODELS:
        for attempt in range(3):
            tools.EVIDENCE.clear()  # 시도마다 근거 초기화(실패 시 잔여 로그 제거)
            try:
                chat = client.chats.create(model=model, config=config)
                resp = chat.send_message(question)
                return (resp.text or "(응답 없음)"), list(tools.EVIDENCE)
            except genai_errors.ServerError as e:  # 503/500 등 → 점증 백오프 후 재시도
                last_err = e
                time.sleep(2 * (attempt + 1))
            except genai_errors.ClientError as e:   # 429(분당 한도) → 다른 모델로(쿼터 별도)
                last_err = e
                if getattr(e, "code", None) == 429:
                    time.sleep(3.0)
                    break  # 같은 모델 재시도 무의미 → 다음 모델로
                raise      # 400(키 오류) 등은 즉시 표면화
    raise RuntimeError(f"무료 한도(분당 5요청) 소진 또는 일시 과부하입니다. 잠시 후 다시 시도하세요. 마지막 오류: {last_err}")


if __name__ == "__main__":  # 터미널 빠른 테스트: python agent.py "삼성전자 어때?"
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    q = sys.argv[1] if len(sys.argv) > 1 else "삼성전자 지금 어때?"
    agent = build_agent()
    answer, evidence = ask(agent, q)
    print("\n=== 답변 ===\n", answer)
    print("\n=== 근거(EVIDENCE) ===")
    for e in evidence:
        print(" -", e)
