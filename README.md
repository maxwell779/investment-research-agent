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

# 📈 AI 투자 리서치 에이전트

> 종목/질문을 던지면 **Gemini 에이전트가 스스로 도구(시세·재무·뉴스)를 골라 호출**해, **모든 수치에 출처를 단** 투자 리서치 답변을 생성합니다. 한국·해외 주식 모두 지원하고, 데이터가 없으면 지어내지 않고 "찾지 못했다"고 답합니다.

**스택**: Python · **LLM 멀티 프로바이더**(Google **Gemini** / **GitHub Models** gpt-4o-mini) tool-calling · `yfinance`·네이버 금융·`FinanceDataReader`(무료 데이터) · Streamlit · Hugging Face Spaces(Docker)

🤗 **라이브 데모**: `https://<your-space>.hf.space` (배포 후 직접 주소로 — 아래 배포 섹션 참고)

---

## 이 프로젝트가 "그냥 주식 챗봇"과 다른 점 (차별화)
1. **진짜 tool-use 에이전트** — 단일 검색이 아니라, 질문에 따라 `resolve_ticker → get_price / get_financials / get_kr_fundamentals / get_news`를 **에이전트가 자율적으로 선택·조합**해 호출합니다. 비교 질문이면 두 종목 각각 도구를 호출해 표로 정리합니다.
2. **모든 주장에 출처(citation) + 환각 억제** — 답변의 숫자는 도구가 실제 반환한 값만 사용하고, *어떤 도구*의 값인지 화면에 함께 표시합니다. 도구가 `as_of`를 주지 않으면 **날짜를 지어내지 않으며**, 없는 종목엔 "데이터 없음"으로 답합니다.
3. **정직성 평가 하니스** — 출처적중률·수치정확도·거절률을 자동 측정해 공개합니다(아래 표).

## 주요 기능
- 🇰🇷🇺🇸 **한국+해외**: `삼성전자`·`AAPL` 등 종목명/심볼 모두 처리(자동 티커 변환)
- 💹 **시세·재무·뉴스**: 현재가/등락률, PER·PBR·시총·ROE, 최신 뉴스(제목·링크)
- 🆚 **종목 비교**: "삼성전자 vs SK하이닉스" → 핵심 지표 비교 표
- 🇰🇷 **한국 PER/PBR**: yfinance가 비워두는 한국 지표를 **네이버 금융**에서 보강
- 🔎 **출처 표기 + 면책**: 모든 수치에 근거, 답변마다 "투자 조언 아님" 고지

## 아키텍처
```
"삼성전자 vs SK하이닉스" → [Gemini 에이전트 루프 (function-calling)]
                            ├─ resolve_ticker(종목명) → 005930.KS / 000660.KS
                            ├─ get_price(...)            (yfinance)
                            ├─ get_financials(...)       (yfinance, 해외 PER/PBR)
                            ├─ get_kr_fundamentals(...)  (네이버 금융, 한국 PER/PBR)
                            └─ get_news(...)             (yfinance)
                         → 출처 달린 비교 표 + "투자 조언 아님" 고지
                         → [평가 하니스] 출처적중률·수치정확도·거절률
```

## 평가 결과 (정직성 하니스)
`python eval/run_eval.py` 로 측정. ⚠️ 무료 Gemini 한도(모델당 **하루 20 / 분당 5요청**)로 한 번에 전체 측정이 어려워, 아래는 **실행 성공 케이스 기준 부분 실측**입니다. (자동 로그의 0%는 한도 소진(503/429)으로 *호출 실패*한 것이지 정직성 실패가 아님)

| 지표 | 결과 | 비고 |
|---|---|---|
| 출처적중률(citation) | **100%** | 성공한 모든 답변에 도구 근거(EVIDENCE) 포함 |
| 수치정확도(±2%) | **100% (2/2)** | 삼성전자 318,000원·애플 283.78달러 — 독립 조회값과 일치 |
| 거절률(존재X 종목) | **측정 대기** | 일일 한도 소진으로 미실행 → 한도 회복 후 재측정 |

## 실행 방법 (로컬)
```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
python agent.py "삼성전자 지금 어때?"   # 터미널 빠른 테스트
streamlit run app.py                    # 웹 앱
python eval/run_eval.py                  # 정직성 평가 (무료 한도상 케이스 간 대기)
```

### LLM 프로바이더 선택 (`.env`의 `LLM_PROVIDER`)
| 값 | 백엔드 | 키 발급 | 비고 |
|---|---|---|---|
| `gemini` (기본) | Google Gemini | https://aistudio.google.com/apikey → `GEMINI_API_KEY` | 무료. 일 20 / 분 5요청 한도 |
| `github` | GitHub Models(gpt-4o-mini) | https://github.com/settings/tokens (**Models** 권한) → `GITHUB_TOKEN` | 무료. 한도 체계가 달라 Gemini 한도 소진 시 대안 |

> 같은 도구(tools.py)·시스템 지침(prompts.py)을 두 백엔드가 공유합니다. `LLM_PROVIDER`만 바꾸면 전환됩니다.

## 배포 (Hugging Face Spaces · Docker)
1. HF에서 **New Space → SDK: Docker → Blank** 생성
2. 이 폴더 파일 업로드(또는 git push). **`.env`는 올리지 마세요**(키 노출).
3. Space **Settings → Variables and secrets → New secret** 에 `GEMINI_API_KEY` 추가
4. 빌드 후 **직접 주소 `https://<user>-<space>.hf.space`** 로 접속(임베드 iframe보다 매끄러움)

> 무료 Gemini 티어는 **분당 5요청** 제한이 있어, 복잡한 질문을 연달아 하면 잠깐 대기가 필요할 수 있습니다(앱은 모델 폴백으로 흡수).

## 파일 구조
```
investment-research-agent/
├─ app.py            # Streamlit 채팅 UI (출처 표시)
├─ agent.py          # 프로바이더 디스패치 + Gemini 루프(503/429 폴백)
├─ llm_github.py     # GitHub Models(OpenAI 호환) 백엔드 + tool-call 루프
├─ prompts.py        # 정직성 시스템 지침(두 백엔드 공유)
├─ tools.py          # 도구 5종 + 근거(EVIDENCE) 로깅
├─ eval/run_eval.py  # 정직성 평가 하니스 (출처적중률·수치정확도·거절률)
├─ Dockerfile        # HF Spaces(Docker) 배포용
├─ requirements.txt · .env.example · .gitignore
└─ README.md
```

## 로드맵
- [x] **1주차 (MVP)** — 도구 4종 + function-calling + Streamlit 채팅 + 출처 표시
- [x] **2주차 (고도화)** — 한국 PER/PBR(네이버) · 종목 비교 · 날짜 환각 제거 · 평가 하니스 · HF 배포 준비
- [ ] **3주차 (확장)** — 웹 뉴스 검색 도구 · 다중 종목 포트폴리오 · 답변 캐싱 · 평가 케이스 확대

## ⚠️ 면책
학습·정보 제공용 데모이며 **투자 조언이 아닙니다.** 데이터는 yfinance·네이버 금융 등 무료 소스를 사용하며 지연·오차가 있을 수 있습니다.
