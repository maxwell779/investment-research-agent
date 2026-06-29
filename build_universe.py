# -*- coding: utf-8 -*-
"""
스크리너용 유니버스 사전계산(배치). 큐레이션된 한국+미국 대형주의 지표를 모아 universe.json 저장.
실시간 전체 스캔은 무료 데이터로 불가 → 일배치로 갱신하고 화면엔 '기준일' 표기.
실행: python build_universe.py   (수 분 소요, yfinance만 사용)
"""
import json
import os
import datetime
import yfinance as yf
import tools

# (티커, 표시명, 시장)
UNIVERSE = [
    # 한국
    ("005930.KS", "삼성전자", "KR"), ("000660.KS", "SK하이닉스", "KR"),
    ("373220.KS", "LG에너지솔루션", "KR"), ("207940.KS", "삼성바이오로직스", "KR"),
    ("005380.KS", "현대차", "KR"), ("000270.KS", "기아", "KR"),
    ("035420.KS", "NAVER", "KR"), ("035720.KS", "카카오", "KR"),
    ("068270.KS", "셀트리온", "KR"), ("005490.KS", "POSCO홀딩스", "KR"),
    ("105560.KS", "KB금융", "KR"), ("055550.KS", "신한지주", "KR"),
    ("051910.KS", "LG화학", "KR"), ("006400.KS", "삼성SDI", "KR"),
    ("012330.KS", "현대모비스", "KR"),
    # 미국
    ("AAPL", "Apple", "US"), ("MSFT", "Microsoft", "US"), ("NVDA", "NVIDIA", "US"),
    ("GOOGL", "Alphabet", "US"), ("AMZN", "Amazon", "US"), ("META", "Meta", "US"),
    ("TSLA", "Tesla", "US"), ("AVGO", "Broadcom", "US"), ("AMD", "AMD", "US"),
    ("NFLX", "Netflix", "US"), ("JPM", "JPMorgan", "US"), ("V", "Visa", "US"),
    ("WMT", "Walmart", "US"), ("KO", "Coca-Cola", "US"), ("DIS", "Disney", "US"),
    ("INTC", "Intel", "US"), ("BA", "Boeing", "US"), ("UBER", "Uber", "US"),
    ("COIN", "Coinbase", "US"), ("PLTR", "Palantir", "US"),
]


def build():
    rows = []
    for tk, name, mkt in UNIVERSE:
        try:
            p = tools.get_price(tk)
            t = tools.get_technicals(tk)
            info = yf.Ticker(tk).info or {}
            is_kr = tk.endswith((".KS", ".KQ"))
            if is_kr:
                f = tools.get_kr_fundamentals(tk)
                per, pbr = f.get("PER"), f.get("PBR")
            else:
                per, pbr = info.get("trailingPE"), info.get("priceToBook")
            if "error" in p:
                print("skip", tk, p.get("error")); continue
            rows.append({
                "ticker": tk, "name": name, "market": mkt,
                "currency": p.get("currency"), "last": p.get("last_close"),
                "return_1m": p.get("return_1m_pct"), "return_3m": p.get("return_3m_pct"),
                "PER": round(per, 2) if isinstance(per, (int, float)) else None,
                "PBR": round(pbr, 2) if isinstance(pbr, (int, float)) else None,
                "RSI": t.get("RSI14"),
                "marketcap": info.get("marketCap"),
                "sector": info.get("sector"),
            })
            print("ok", tk, p.get("last_close"))
        except Exception as e:
            print("err", tk, str(e)[:60])
    out = {"as_of": datetime.date.today().isoformat(), "count": len(rows), "rows": rows}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "universe.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    print(f"\n저장: {path} · {len(rows)}종목")


if __name__ == "__main__":
    build()
