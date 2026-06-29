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
import tools
from prompts import SYSTEM

# 일시적 과부하(503)에 대비해 여러 무료 모델로 순차 폴백
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]


def build_agent():
    """LLM_PROVIDER(gemini|github)에 따라 백엔드를 만들어 (provider, obj)를 반환한다."""
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    if provider == "github":
        import llm_github
        return ("github", llm_github.build_client())
    # 기본: Gemini
    from google import genai
    from google.genai import types
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY가 없습니다. .env를 만들고 키를 넣으세요(.env.example 참고).")
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(system_instruction=SYSTEM, tools=tools.TOOLS)
    return ("gemini", (client, config))


def ask(agent, question: str):
    """질문 1건을 처리하고 (답변텍스트, 근거리스트)를 반환한다.

    GitHub Models는 llm_github로 위임. Gemini는 503 등 일시 오류 시 모델을 바꿔 재시도한다.
    """
    provider, obj = agent
    if provider == "github":
        import llm_github
        return llm_github.ask(obj, question)
    from google.genai import errors as genai_errors
    client, config = obj
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
