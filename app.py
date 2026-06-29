# -*- coding: utf-8 -*-
"""
AI 투자 리서치 에이전트 — Streamlit 채팅 UI.
사용자가 종목/질문을 입력하면 Gemini 에이전트가 도구로 실제 데이터를 모아
출처를 단 답변을 생성한다.
"""
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="AI 투자 리서치 에이전트", page_icon="📈", layout="centered")

st.markdown("""<style>
html, body, [class*="css"]{font-family:'Pretendard','Malgun Gothic','Apple SD Gothic Neo',sans-serif;}
*,*::before,*::after{animation:none !important;}
html{overflow-y:scroll;}
.src{font-size:.82rem;color:#475569;border-left:3px solid #2563eb;padding:2px 10px;margin:3px 0;background:#f8fafc;}
</style>""", unsafe_allow_html=True)

st.title("📈 AI 투자 리서치 에이전트")
st.caption("한국·해외 주식 · 실제 데이터(yfinance) 기반 · Gemini function-calling · 모든 수치에 출처 표기")

# --- API 키 확인 ---
if not os.environ.get("GEMINI_API_KEY"):
    st.warning("`GEMINI_API_KEY`가 없습니다. `.env.example`를 `.env`로 복사하고 "
               "[Google AI Studio](https://aistudio.google.com/apikey)에서 무료 키를 발급받아 넣으세요.")
    st.stop()

# 모델은 1회만 생성해 재사용
@st.cache_resource(show_spinner=False)
def get_agent():
    from agent import build_agent
    return build_agent()

agent = get_agent()

if "msgs" not in st.session_state:
    st.session_state.msgs = []

# 예시 질문 칩
st.write("예시:")
cols = st.columns(3)
examples = ["삼성전자 지금 어때?", "애플(AAPL) 밸류에이션 평가해줘", "엔비디아 최근 뉴스 정리해줘"]
for c, ex in zip(cols, examples):
    if c.button(ex, use_container_width=True):
        st.session_state.pending = ex

# 이전 대화 렌더
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        for s in m.get("sources", []):
            link = f" — [{s.get('link')}]({s.get('link')})" if s.get("link") else ""
            st.markdown(f"<div class='src'>🔎 <b>{s['tool']}</b> · {s['source']}: {s['output']}{link}</div>",
                        unsafe_allow_html=True)

prompt = st.chat_input("종목이나 질문을 입력하세요 (예: 'TSLA 어때?')") or st.session_state.pop("pending", None)

if prompt:
    st.session_state.msgs.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("에이전트가 데이터를 조회하는 중..."):
            from agent import ask
            try:
                answer, evidence = ask(agent, prompt)
            except Exception as e:
                answer, evidence = f"오류가 발생했습니다: {e}", []
        st.markdown(answer)
        for s in evidence:
            link = f" — [{s.get('link')}]({s.get('link')})" if s.get("link") else ""
            st.markdown(f"<div class='src'>🔎 <b>{s['tool']}</b> · {s['source']}: {s['output']}{link}</div>",
                        unsafe_allow_html=True)
    st.session_state.msgs.append({"role": "assistant", "content": answer, "sources": evidence})
