# -*- coding: utf-8 -*-
"""
reports/ 폴더의 리포트 PDF를 RAG DB에 색인한다.
파일명에 종목코드/명을 넣으면 자동 매핑: 예) `005930_삼성전자_2026Q1.pdf`, `AAPL_apple.pdf`
또는 reports/<티커>/ 하위 폴더로 정리해도 됨: reports/005930.KS/xxx.pdf

⚠️ 본인이 합법적으로 보유한 리포트만 넣으세요(저작권). 화면엔 요약+출처만 노출됩니다.
실행: python ingest_reports.py
"""
import os
import glob
from dotenv import load_dotenv

load_dotenv()
import tools
import rag
import report_crawler

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, "reports")


def resolve(name_hint):
    """파일명/폴더명에서 티커 추정. 6자리 코드는 KRX 접미사(.KS/.KQ) 부여."""
    base = name_hint.split("_")[0].split("(")[0].strip()
    if base.isdigit() and len(base) == 6:
        cm = report_crawler._code_map().get(base)
        if cm:
            return cm[0]
    r = tools.resolve_ticker(base)
    return r.get("ticker") if "error" not in r else None


def main():
    if not os.path.isdir(REPORTS):
        os.makedirs(REPORTS)
        print(f"reports/ 폴더를 만들었습니다. PDF를 넣고 다시 실행하세요: {REPORTS}")
        return
    # 크롤러가 관리하는 reports/miraeasset/ 는 제외(이미 report_crawler가 정확히 색인)
    pdfs = [p for p in glob.glob(os.path.join(REPORTS, "**", "*.pdf"), recursive=True)
            if "miraeasset" not in os.path.relpath(p, REPORTS).replace("\\", "/").split("/")]
    if not pdfs:
        print("reports/ 에 PDF가 없습니다. (예: reports/005930_삼성전자_리포트.pdf)")
        return
    total = 0
    for p in pdfs:
        rel = os.path.relpath(p, REPORTS)
        parent = os.path.dirname(rel)
        hint = parent if parent else os.path.basename(p)  # 하위폴더명 우선, 없으면 파일명
        tk = resolve(hint)
        if not tk:
            print(f"  [건너뜀] 티커 인식 실패: {rel}")
            continue
        res = rag.ingest_pdf(p, tk)
        if res.get("error"):
            print(f"  [실패] {rel}: {res['error']}")
        else:
            total += res["chunks"]
            print(f"  [색인] {rel} → {tk} · {res['chunks']}청크")
    print(f"\n완료: {total}청크 색인. 이제 앱의 '📚 리서치' 탭에서 검색됩니다.")


if __name__ == "__main__":
    main()
