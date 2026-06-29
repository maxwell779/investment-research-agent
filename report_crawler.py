# -*- coding: utf-8 -*-
"""
증권사 리서치 크롤러 — robots.txt가 허용하는 미래에셋증권 리서치 게시판만 수집한다.
(한경컨센서스·네이버금융은 robots Disallow → 수집 안 함)

수집: 제목·부제·날짜·PDF링크 (메타). 옵션으로 PDF 다운로드 후 로컬 RAG 색인(ingest_pdf).
⚠️ 저작권: 전문 재배포 ❌. 화면엔 요약+원문 링크만. 개인·학습용 로컬 색인.
실행: python report_crawler.py
"""
import os
import re
import html
import time
import requests
from dotenv import load_dotenv

load_dotenv()
import tools
import rag

HERE = os.path.dirname(os.path.abspath(__file__))
DLDIR = os.path.join(HERE, "reports", "miraeasset")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://securities.miraeasset.com/bbs/board/message/list.do"
# robots 허용 카테고리(시황/산업·테마/ETF). 필요시 추가.
CATEGORIES = {"1521": "시황·전략", "1525": "산업·테마", "1526": "ETF"}

_ROW = re.compile(
    r'<tr[^>]*>\s*<td[^>]*>\s*(20\d{2}-\d{2}-\d{2})\s*</td>.*?'
    r'id="bbsTitle\d+">\s*<b>(.*?)</b>\s*(?:<br\s*/?>(.*?))?</a>.*?'
    r"downConfirm\('(https://securities\.miraeasset\.com/bbs/download/\d+\.pdf[^']*)'",
    re.S)


def crawl_category(cid, pages=1):
    out = []
    for p in range(1, pages + 1):
        try:
            r = requests.get(BASE, params={"categoryId": cid, "pageIndex": str(p)}, headers=UA, timeout=15)
            for date, title, sub, pdf in _ROW.findall(r.text):
                out.append({"broker": "미래에셋", "category": CATEGORIES.get(cid, cid), "date": date,
                            "title": html.unescape(re.sub("<[^>]+>", "", title)).strip(),
                            "subtitle": html.unescape(re.sub("<[^>]+>", "", sub or "")).strip(),
                            "pdf": pdf})
            time.sleep(0.8)  # 예의: 요청 간격
        except Exception as e:
            print("  crawl err", cid, p, str(e)[:60])
    return out


def _name_to_ticker():
    """유니버스 회사명 → 티커(리포트 제목 매칭용, 노이즈 최소화 위해 큐레이션 유니버스만)."""
    import json
    path = os.path.join(HERE, "universe.json")
    m = {}
    try:
        with open(path, encoding="utf-8") as f:
            for r in json.load(f).get("rows", []):
                if r.get("name") and r.get("ticker"):
                    m[r["name"]] = r["ticker"]
    except Exception:
        pass
    return m


_CODE_MAP = None


def _code_map():
    """KRX 종목코드 → yfinance 티커(.KS/.KQ). 리포트 제목의 (123456/...) 매칭용."""
    global _CODE_MAP
    if _CODE_MAP is not None:
        return _CODE_MAP
    _CODE_MAP = {}
    try:
        df = tools._krx_listing()
        code_col = "Code" if "Code" in df.columns else df.columns[0]
        mkt_col = "Market" if "Market" in df.columns else None
        name_col = "Name" if "Name" in df.columns else df.columns[1]
        for _, row in df.iterrows():
            code = str(row[code_col]).zfill(6)
            mkt = str(row[mkt_col]) if mkt_col else ""
            suf = ".KQ" if "KOSDAQ" in mkt.upper() else ".KS"
            _CODE_MAP[code] = (code + suf, str(row[name_col]))
    except Exception:
        pass
    return _CODE_MAP


def tag_ticker(title, name_map):
    # 1) 제목의 종목코드 (458870/...) 우선
    m = re.search(r"\((\d{6})\s*/", title)
    if m:
        cm = _code_map().get(m.group(1))
        if cm:
            return cm[0], cm[1]
        return m.group(1) + ".KS", m.group(1)
    # 2) 유니버스 회사명 매칭
    for nm, tk in name_map.items():
        if nm and nm in title:
            return tk, nm
    return "MARKET", None


def download_pdf(url, title):
    os.makedirs(DLDIR, exist_ok=True)
    fn = re.sub(r'[\\/:*?"<>|]', "_", title)[:60] + ".pdf"
    path = os.path.join(DLDIR, fn)
    if not os.path.exists(path):
        r = requests.get(url, headers=UA, timeout=30)
        with open(path, "wb") as f:
            f.write(r.content)
    return path


def main(pages=1, download=True):
    name_map = _name_to_ticker()
    reports = []
    for cid in CATEGORIES:
        reports += crawl_category(cid, pages)
    print(f"수집 리포트: {len(reports)}건")
    ingested = 0
    for rep in reports:
        full = (rep["title"] + " " + rep["subtitle"]).strip()
        tk, matched = tag_ticker(full, name_map)
        # 메타 1건은 항상 RAG 색인(요약+링크)
        src = f"리포트·{rep['broker']}·{rep['category']}"
        try:
            embs = rag.embed([f"{full} ({rep['broker']} {rep['date']})"])
            c = rag._conn()
            c.execute("DELETE FROM docs WHERE ticker=? AND kind='report' AND title=?", (tk, rep["title"]))
            c.execute("INSERT INTO docs(ticker,source,title,text,link,date,emb,ts,kind) VALUES(?,?,?,?,?,?,?,?,'report')",
                      (tk, src, rep["title"], full, rep["pdf"], rep["date"], embs[0].tobytes(), time.time()))
            c.commit(); c.close()
            ingested += 1
        except Exception as e:
            print("  ingest meta err", str(e)[:60])
        # 종목 매칭된 리포트는 PDF 본문까지 색인(로컬)
        if download and matched:
            try:
                path = download_pdf(rep["pdf"], rep["title"])
                res = rag.ingest_pdf(path, tk, source=src)
                print(f"  [PDF색인] {matched} · {rep['title'][:30]} → {res.get('chunks')}청크")
            except Exception as e:
                print("  pdf err", str(e)[:60])
    print(f"\n완료: 메타 {ingested}건 색인. 종목 매칭 리포트는 PDF 본문도 색인.")


if __name__ == "__main__":
    main(pages=1, download=True)
