---
title: AI 투자 리서치 에이전트
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 📈 AI 투자 리서치 에이전트 (React + FastAPI + LLM)

> **종목 대시보드**(시세·기술적 지표·재무 추세·뉴스 + 캔들차트)와 **AI 리서치 챗**을 한 화면에. LLM 에이전트가 스스로 도구를 골라 실제 데이터를 모아 **모든 수치에 출처를 달고**, 데이터가 없으면 지어내지 않고 "찾지 못했다"고 답합니다. 한국·해외 주식 모두 지원.

**스택**: **React(Vite)** + **FastAPI** · LLM 멀티 프로바이더(**GitHub Models** gpt-4o-mini / **Gemini**) function-calling · `yfinance`·네이버 금융·`FinanceDataReader`(무료) · `lightweight-charts` · Docker(HF Spaces)

🤗 **라이브 데모**: `https://<your-space>.hf.space` (배포 후 — 아래 참고)

---

## 화면 구성
- **종목 대시보드** (LLM 미사용 → 즉시·쿼터 0): 종목 검색 → 헤더 카드 + 지표 카드(기간수익률·52주 위치·RSI·이평신호·PER/PBR·시총) + **캔들차트(MA20/60 + 거래량)** + 탭(차트/기술적/재무/뉴스)
- **AI 리서치 챗**: 자유 질문/비교 → 에이전트가 도구로 데이터를 모아 **출처(EVIDENCE)와 함께** 답변

## 차별화 (그냥 주식 챗봇과 다른 점)
1. **데이터 대시보드 + AI 분리** — 정형 데이터는 LLM 없이 즉시 렌더(빠름·무료), 자유질문만 에이전트 사용 → 비용·속도 최적화
2. **진짜 tool-use 에이전트** — `resolve_ticker → get_price / get_technicals / get_financial_trend / get_financials / get_kr_fundamentals / get_news` 를 질문에 따라 자율 선택·조합. 비교 질문이면 종목별로 호출해 표로 정리
3. **출처 + 환각 억제 + 정직성 평가** — 모든 수치에 도구 근거 표기, `as_of` 없으면 날짜 미언급, 없는 종목 거절. 아래 평가 하니스로 정량 검증

## 정직성 평가 결과
`python eval/run_eval.py` — **GitHub Models(gpt-4o-mini) · 16케이스**

| 지표 | 결과 |
|---|---|
| 출처적중률(citation) | **100% (12/12)** |
| 수치정확도(±2%) | **100% (12/12)** |
| 거절률(존재X 종목) | **100% (4/4)** |

> 시세·밸류에이션·기술적·재무 12케이스 모두 출처에 근거한 정확한 수치, 가짜 종목 4건 전부 정직하게 거절. `eval/run_eval.py`로 재현 가능.

## 아키텍처
```
React(Vite) ──HTTP──▶ FastAPI ──▶ tools.py(무료 데이터)  +  agent(LLM, function-calling)
  ├ 대시보드            ├ GET  /api/dashboard?query=  (시세·기술·재무·차트·뉴스, LLM 0, 60s 캐시)
  └ AI 챗              └ POST /api/chat              (에이전트 → 답변 + EVIDENCE)
```

## 실행 방법 (로컬 — 백엔드 + 프론트 동시)
```bash
# 1) 백엔드
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env  → 키 입력
uvicorn api:app --reload --port 8000

# 2) 프론트 (새 터미널)
cd frontend
npm install
npm run dev                 # http://localhost:5173 (api 는 8000으로 프록시)
```
프로덕션처럼 한 번에 보려면: `cd frontend && npm run build` 후 `uvicorn api:app --port 8000` → http://localhost:8000 (FastAPI가 빌드된 React + API를 함께 서빙)

### LLM 프로바이더 (`.env`의 `LLM_PROVIDER`)
| 값 | 백엔드 | 키 | 비고 |
|---|---|---|---|
| `github` | GitHub Models(gpt-4o-mini) | https://github.com/settings/personal-access-tokens → **Account permissions › Models: Read-only** → `GITHUB_TOKEN` | 무료, 한도 넉넉(권장) |
| `gemini` | Google Gemini | https://aistudio.google.com/apikey → `GEMINI_API_KEY` | 무료, 일 20/분 5요청 |

## 배포 (Hugging Face Spaces · Docker)
1. New Space → **SDK: Docker → Blank**
2. 파일 업로드/푸시 (**`.env` 제외**, `node_modules`·`dist` 제외)
3. Space **Settings → Secrets** 에 `LLM_PROVIDER`, `GITHUB_TOKEN`(또는 `GEMINI_API_KEY`) 추가
4. 빌드(멀티스테이지: React 빌드 → FastAPI 서빙) 후 **직접 주소 `https://<user>-<space>.hf.space`** 로 접속

## 파일 구조
```
investment-research-agent/
├─ api.py            # FastAPI: /api/dashboard(캐시), /api/chat + React 정적 서빙
├─ agent.py          # 프로바이더 디스패치 + Gemini 루프(503/429 폴백)
├─ llm_github.py     # GitHub Models(OpenAI 호환) tool-call 루프
├─ prompts.py        # 정직성 시스템 지침(공유)
├─ tools.py          # 데이터 도구 7종 + 차트용 get_history + EVIDENCE 로깅
├─ eval/run_eval.py  # 정직성 평가(출처/수치/거절) — 16케이스
├─ app.py            # (선택) 간단 Streamlit 버전
├─ frontend/         # React(Vite): App/PriceChart/Chat + styles
├─ Dockerfile        # React 빌드 → FastAPI 서빙(HF Spaces)
└─ requirements.txt · .env.example · .gitignore
```

## 로드맵
- [x] 1주차 — RAG/에이전트 MVP(도구·function-calling·출처)
- [x] 2주차 — 한국 PER/PBR·종목비교·날짜환각 제거·정직성 평가·멀티 프로바이더
- [x] 3주차 — **React+FastAPI 풀스택**: 대시보드·캔들차트·기술적/재무 도구·16케이스 평가·캐싱
- [ ] 다음 — 웹 뉴스 검색 도구·포트폴리오(다종목)·답변 스트리밍·HF 배포

## ⚠️ 면책
학습·정보 제공용 데모이며 **투자 조언이 아닙니다.** 데이터(yfinance·네이버 금융)는 지연·오차가 있을 수 있습니다.
