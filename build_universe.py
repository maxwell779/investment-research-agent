# -*- coding: utf-8 -*-
"""
스크리너/랭킹용 유니버스 사전계산(배치). 9개국 대형주의 지표 + 시총(USD 환산)을 모아 universe.json 저장.
실시간 전체 스캔은 무료 데이터로 불가 → 일배치로 갱신, 화면엔 '기준일' 표기.
실행: python build_universe.py   (수 분 소요, yfinance만 사용)
"""
import json
import os
import datetime
import yfinance as yf
import tools

# (티커, 표시명, 국가)
UNIVERSE = [
    # 한국
    ("005930.KS", "삼성전자", "KR"), ("000660.KS", "SK하이닉스", "KR"), ("373220.KS", "LG에너지솔루션", "KR"),
    ("207940.KS", "삼성바이오로직스", "KR"), ("005380.KS", "현대차", "KR"), ("000270.KS", "기아", "KR"),
    ("035420.KS", "NAVER", "KR"), ("035720.KS", "카카오", "KR"), ("068270.KS", "셀트리온", "KR"),
    ("005490.KS", "POSCO홀딩스", "KR"), ("105560.KS", "KB금융", "KR"), ("051910.KS", "LG화학", "KR"),
    ("006400.KS", "삼성SDI", "KR"), ("012330.KS", "현대모비스", "KR"),
    # 미국
    ("AAPL", "Apple", "US"), ("MSFT", "Microsoft", "US"), ("NVDA", "NVIDIA", "US"), ("GOOGL", "Alphabet", "US"),
    ("AMZN", "Amazon", "US"), ("META", "Meta", "US"), ("TSLA", "Tesla", "US"), ("AVGO", "Broadcom", "US"),
    ("AMD", "AMD", "US"), ("JPM", "JPMorgan", "US"), ("V", "Visa", "US"), ("WMT", "Walmart", "US"),
    ("LLY", "Eli Lilly", "US"), ("JNJ", "J&J", "US"),
    # 일본
    ("7203.T", "토요타", "JP"), ("6758.T", "소니", "JP"), ("9984.T", "소프트뱅크", "JP"),
    ("8306.T", "미쓰비시UFJ", "JP"), ("6861.T", "키엔스", "JP"),
    # 대만
    ("2330.TW", "TSMC", "TW"), ("2317.TW", "폭스콘", "TW"),
    # 중국/홍콩
    ("0700.HK", "텐센트", "CN"), ("9988.HK", "알리바바", "CN"), ("1810.HK", "샤오미", "CN"), ("3690.HK", "메이투안", "CN"),
    # 유럽
    ("ASML.AS", "ASML", "EU"), ("MC.PA", "LVMH", "EU"), ("SAP.DE", "SAP", "EU"), ("SIE.DE", "Siemens", "EU"),
    # 인도
    ("RELIANCE.NS", "Reliance", "IN"), ("TCS.NS", "TCS", "IN"), ("INFY.NS", "Infosys", "IN"),
    # 영국
    ("AZN.L", "AstraZeneca", "UK"), ("SHEL.L", "Shell", "UK"), ("HSBA.L", "HSBC", "UK"),
]

_FX = {}


def fx_to_usd(cur):
    """해당 통화 1단위 = ? USD."""
    if cur in (None, "USD"):
        return 1.0
    if cur in _FX:
        return _FX[cur]
    rate = None
    for sym in [f"{cur}USD=X", f"{cur}=X"]:
        try:
            h = yf.Ticker(sym).history(period="5d")
            if not h.empty:
                v = float(h["Close"].iloc[-1])
                rate = v if sym.endswith("USD=X") else (1.0 / v if v else None)
                if rate:
                    break
        except Exception:
            pass
    _FX[cur] = rate
    return rate


def build():
    rows = []
    for tk, name, country in UNIVERSE:
        try:
            p = tools.get_price(tk)
            if "error" in p:
                print("skip", tk, p.get("error")); continue
            t = tools.get_technicals(tk)
            info = yf.Ticker(tk).info or {}
            is_kr = tk.endswith((".KS", ".KQ"))
            if is_kr:
                fnd = tools.get_kr_fundamentals(tk)
                per, pbr = fnd.get("PER"), fnd.get("PBR")
            else:
                per, pbr = info.get("trailingPE"), info.get("priceToBook")
            mc = info.get("marketCap")
            cur = info.get("currency")
            fx = fx_to_usd(cur)
            mc_usd = int(mc * fx) if (mc and fx) else None
            rows.append({
                "ticker": tk, "name": name, "country": country,
                "currency": p.get("currency"), "last": p.get("last_close"),
                "return_1m": p.get("return_1m_pct"), "return_3m": p.get("return_3m_pct"),
                "PER": round(per, 2) if isinstance(per, (int, float)) else None,
                "PBR": round(pbr, 2) if isinstance(pbr, (int, float)) else None,
                "RSI": t.get("RSI14"),
                "marketcap": mc, "marketcap_usd": mc_usd,
                "sector": info.get("sector"),
            })
            print("ok", tk, name, "mc$", mc_usd)
        except Exception as e:
            print("err", tk, str(e)[:60])
    out = {"as_of": datetime.date.today().isoformat(), "count": len(rows), "rows": rows}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "universe.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    print(f"\n저장: {path} · {len(rows)}종목")


if __name__ == "__main__":
    build()
