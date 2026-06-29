# -*- coding: utf-8 -*-
"""
리포트/뉴스 RAG — 종목별로 뉴스·애널리스트·재무·개요를 수집해 임베딩 후 SQLite에 저장하고,
질문과 코사인 유사도로 검색한 근거만으로 LLM이 한국어 종합을 생성한다(출처 인용).

- 임베딩: GitHub Models text-embedding-3-small (무료, torch 불필요)
- 벡터 저장/검색: SQLite + numpy 코사인 (경량 벡터 검색)
- 생성: agent.quick_complete (프로바이더 자동)
- 합법성: 전문 재배포 ❌ — 제목·요약·지표 등 메타/짧은 텍스트 + 출처 링크만 저장.
"""
import os
import sqlite3
import time
import requests
import numpy as np
from openai import OpenAI
import tools
from agent import quick_complete

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag.db")
EMB_MODEL = os.environ.get("EMB_MODEL", "openai/text-embedding-3-small")
EMB_BASE = os.environ.get("GITHUB_MODELS_BASE", "https://models.github.ai/inference")


def _client():
    return OpenAI(base_url=EMB_BASE, api_key=os.environ["GITHUB_TOKEN"])


def _conn():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS docs(
        ticker TEXT, source TEXT, title TEXT, text TEXT, link TEXT, date TEXT, emb BLOB, ts REAL, kind TEXT)""")
    try:
        c.execute("ALTER TABLE docs ADD COLUMN kind TEXT DEFAULT 'auto'")  # 기존 DB 호환
    except Exception:
        pass
    return c


def embed(texts):
    r = _client().embeddings.create(model=EMB_MODEL, input=texts)
    return [np.array(d.embedding, dtype=np.float32) for d in r.data]


def _gather_docs(ticker, name):
    """종목 관련 문서 수집(뉴스·애널리스트·등급변경·재무·개요). 짧은 텍스트/메타만."""
    is_kr = ticker.endswith((".KS", ".KQ"))
    docs = []
    news = (tools.get_naver_news(name) if is_kr else tools.get_news(ticker, 8)).get("news", [])
    for n in news:
        if n.get("title"):
            docs.append({"source": "뉴스·" + (n.get("publisher") or ""), "title": n["title"],
                         "text": n["title"], "link": n.get("link"), "date": n.get("date", "")})
    a = tools.get_analyst(ticker)
    if not a.get("error"):
        docs.append({"source": "애널리스트 컨센서스", "title": "컨센서스",
                     "text": f"목표주가 평균 {a.get('target_mean')}, 투자의견 {a.get('recommendation_kr')}, "
                             f"상승여력 {a.get('upside_pct')}%, 애널리스트 {a.get('num_analysts')}명",
                     "link": None, "date": ""})
    for it in (tools.get_recommendations(ticker).get("items") or [])[:6]:
        docs.append({"source": "등급변경·" + (it.get("firm") or ""), "title": "등급변경",
                     "text": f"{it.get('firm')}: {it.get('from')}→{it.get('to')} ({it.get('action')})",
                     "link": None, "date": it.get("date", "")})
    fin = tools.get_dart_financials(ticker) if is_kr else tools.get_financial_trend(ticker, "annual")
    if not fin.get("error"):
        docs.append({"source": "재무" + ("·DART" if fin.get("source") == "DART" else ""), "title": "재무추세",
                     "text": f"매출 성장률 {fin.get('revenue_yoy_pct')}%, 영업이익 {fin.get('operating_income_yoy_pct')}%, "
                             f"순이익 {fin.get('net_income_yoy_pct')}%", "link": None, "date": ""})
    pf = tools.get_profile(ticker)
    if not pf.get("error") and pf.get("summary"):
        docs.append({"source": "기업개요", "title": "사업", "text": pf["summary"][:800],
                     "link": pf.get("website"), "date": ""})
    if is_kr:
        for fl in (tools.get_dart_filings(ticker).get("filings") or [])[:5]:
            docs.append({"source": "DART 공시", "title": fl.get("title"),
                         "text": f"{fl.get('corp')} {fl.get('title')} ({fl.get('date')}) — 공개 법정공시",
                         "link": fl.get("link"), "date": fl.get("date", "")})
    return docs


def ingest(ticker, name):
    """자동 코퍼스(뉴스·애널·재무·개요·공시) 갱신. PDF/리포트(kind='report')는 보존."""
    docs = _gather_docs(ticker, name)
    if not docs:
        return 0
    embs = embed([d["text"] for d in docs])
    c = _conn()
    c.execute("DELETE FROM docs WHERE ticker=? AND (kind='auto' OR kind IS NULL)", (ticker,))
    for d, e in zip(docs, embs):
        c.execute("INSERT INTO docs(ticker,source,title,text,link,date,emb,ts,kind) VALUES(?,?,?,?,?,?,?,?,'auto')",
                  (ticker, d["source"], d["title"], d["text"], d["link"], d["date"], e.tobytes(), time.time()))
    c.commit()
    c.close()
    return len(docs)


def _chunks(text, size=900):
    text = " ".join((text or "").split())
    return [text[i:i + size] for i in range(0, len(text), size)] if text else []


def ingest_pdf(path, ticker, source=None):
    """리포트 PDF(사용자 보유분)를 텍스트 추출→청킹→임베딩→저장(kind='report', 영속).
    화면엔 요약+출처만 노출(전문 재배포 아님)."""
    from pypdf import PdfReader
    src = source or ("리포트·" + os.path.basename(path))
    try:
        reader = PdfReader(path)
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        return {"error": f"PDF 읽기 실패: {e}", "chunks": 0}
    chunks = _chunks(text)[:40]  # 비용/용량 제한
    if not chunks:
        return {"error": "PDF에서 텍스트를 추출하지 못했습니다(스캔본일 수 있음).", "chunks": 0}
    embs = embed(chunks)
    c = _conn()
    fn = os.path.basename(path)
    c.execute("DELETE FROM docs WHERE ticker=? AND kind='report' AND title=?", (ticker, fn))  # 동일 파일 갱신
    for ch, e in zip(chunks, embs):
        c.execute("INSERT INTO docs(ticker,source,title,text,link,date,emb,ts,kind) VALUES(?,?,?,?,?,?,?,?,'report')",
                  (ticker, src, fn, ch, None, "", e.tobytes(), time.time()))
    c.commit()
    c.close()
    return {"chunks": len(chunks), "file": fn}


def _has_dart_report(ticker):
    c = _conn()
    n = c.execute("SELECT COUNT(*) FROM docs WHERE ticker=? AND source LIKE 'DART 사업보고서%'", (ticker,)).fetchone()[0]
    c.close()
    return n > 0


def ingest_dart_report(ticker, name=""):
    """DART 사업보고서(또는 최신 정기보고서) 본문에서 부문별 매출·사업내용 등 핵심 청크를 RAG에 색인.
    합법: 공개 법정공시. 화면엔 발췌+DART 원문 링크."""
    import io as _io
    import zipfile as _zip
    import datetime as _dt
    if not ticker.endswith((".KS", ".KQ")):
        return {"error": "한국 종목 전용"}
    key = os.environ.get("DART_API_KEY")
    corp = tools._dart_corp_map().get(ticker.split(".")[0]) if key else None
    if not corp:
        return {"error": "corp_code/키 없음"}
    try:
        bgn = (_dt.date.today() - _dt.timedelta(days=500)).strftime("%Y%m%d")
        lst = requests.get("https://opendart.fss.or.kr/api/list.json",
                           params={"crtfc_key": key, "corp_code": corp, "bgn_de": bgn, "pblntf_ty": "A", "page_count": "20"},
                           timeout=15).json()
        rcept = None
        for it in lst.get("list", []):
            if "사업보고서" in (it.get("report_nm") or ""):
                rcept = it.get("rcept_no"); break
        if not rcept:
            for it in lst.get("list", []):
                if "보고서" in (it.get("report_nm") or ""):
                    rcept = it.get("rcept_no"); break
        if not rcept:
            return {"error": "보고서 없음"}
        doc = requests.get("https://opendart.fss.or.kr/api/document.xml",
                           params={"crtfc_key": key, "rcept_no": rcept}, timeout=60).content
        zf = _zip.ZipFile(_io.BytesIO(doc))
        raw = " ".join(zf.read(n).decode("utf-8", "ignore") for n in zf.namelist())
        import re as _re
        text = _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", raw))
        chunks = _chunks(text, 1000)
        kws = ["부문", "매출", "영업이익", "사업의 내용", "주요 제품", "리스크", "경쟁", "점유율", "연구개발", "수주"]
        top = sorted(chunks, key=lambda ch: -sum(ch.count(k) for k in kws))[:25]
        top = [ch for ch in top if sum(ch.count(k) for k in kws) > 0]
        if not top:
            return {"error": "핵심 본문 추출 실패"}
        embs = embed(top)
        link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}"
        c = _conn()
        c.execute("DELETE FROM docs WHERE ticker=? AND source LIKE 'DART 사업보고서%'", (ticker,))
        for ch, e in zip(top, embs):
            c.execute("INSERT INTO docs(ticker,source,title,text,link,date,emb,ts,kind) VALUES(?,?,?,?,?,?,?,?,'report')",
                      (ticker, "DART 사업보고서", "사업보고서 본문", ch, link, "", e.tobytes(), time.time()))
        c.commit()
        c.close()
        return {"chunks": len(top), "rcept": rcept}
    except Exception as e:
        return {"error": f"DART 사업보고서 색인 실패: {e}"}


def _fresh(ticker, ttl=3600):
    c = _conn()
    row = c.execute("SELECT MAX(ts) FROM docs WHERE ticker=? AND (kind='auto' OR kind IS NULL)", (ticker,)).fetchone()
    c.close()
    return bool(row and row[0] and (time.time() - row[0] < ttl))


def _retrieve(ticker, question, k=6):
    c = _conn()
    rows = c.execute("SELECT source,title,text,link,date,emb FROM docs WHERE ticker=?", (ticker,)).fetchall()
    c.close()
    if not rows:
        return []
    qe = embed([question])[0]
    qn = qe / (np.linalg.norm(qe) + 1e-9)
    scored = []
    for src, title, text, link, date, emb in rows:
        v = np.frombuffer(emb, dtype=np.float32)
        sim = float(np.dot(qn, v / (np.linalg.norm(v) + 1e-9)))
        scored.append((sim, {"source": src, "title": title, "text": text, "link": link, "date": date}))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:k]]


def research(ticker, name, question=""):
    """종목 코퍼스를 (필요시) 갱신·검색해 출처 인용 종합을 생성한다."""
    if not _fresh(ticker):
        ingest(ticker, name)
    if ticker.endswith((".KS", ".KQ")) and not _has_dart_report(ticker):
        try:
            ingest_dart_report(ticker, name)  # 사업보고서 본문(부문별 매출 등) 1회 색인
        except Exception:
            pass
    q = question or f"{name} 투자 관점 종합 분석"
    hits = _retrieve(ticker, q, 6)
    if not hits:
        return {"answer": "관련 자료를 찾지 못했습니다.", "sources": []}
    ctx = "\n".join(f"[{i + 1}] ({h['source']}) {h['text']}" for i, h in enumerate(hits))
    prompt = (f"아래는 '{name}' 관련 수집 자료(뉴스·애널리스트·재무·개요)입니다. **이 자료만 근거로** "
              f"한국어 투자 관점 종합을 5~7줄로 작성하고, 각 핵심 문장 끝에 근거 번호 [n]을 표기하세요. "
              f"자료에 없는 내용은 지어내지 마세요. 끝에 '※ 투자 조언 아님'을 붙이세요.\n\n자료:\n{ctx}\n\n질문: {q}")
    try:
        ans = quick_complete(prompt)
    except Exception as e:
        ans = f"종합 생성 오류: {e}"
    return {"answer": ans, "sources": hits}
