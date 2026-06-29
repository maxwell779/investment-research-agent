import { useState, useEffect } from 'react'
import PriceChart from './PriceChart'
import { fmtPrice, fmtBig, Pct, Metric } from './ui'
import { isStock, toggleStock } from './bookmarks'

const PERIODS = ['1mo', '3mo', '6mo', '1y', '5y']
const PLABEL = { '1mo': '1개월', '3mo': '3개월', '6mo': '6개월', '1y': '1년', '5y': '5년' }

function ScoreCard({ s }) {
  if (!s) return null
  const color = s.score >= 68 ? 'var(--up)' : s.score >= 45 ? '#f59e0b' : 'var(--down)'
  const maxC = 25
  return (
    <div className="card score-card">
      <div className="score-main">
        <div>
          <div className="m-label">투자매력 점수 <span className="muted">(규칙 기반)</span></div>
          <div className="score-num" style={{ color }}>{s.score}<span style={{ fontSize: '1rem', color: 'var(--muted)' }}>/100</span> <span className="score-label" style={{ color }}>{s.label}</span></div>
        </div>
      </div>
      <div className="score-bars">
        {Object.entries(s.breakdown || {}).map(([k, v]) => (
          <div key={k} className="score-bar">
            <span className="sb-name">{k}</span>
            <div className="sb-track"><div className="sb-fill" style={{ width: `${(v / maxC) * 100}%` }} /></div>
            <span className="sb-val">{v}</span>
          </div>
        ))}
      </div>
      <p className="muted" style={{ fontSize: '.74rem', marginTop: 8 }}>※ 모멘텀·추세·밸류·애널리스트 4요소(각 25점) 단순 합산. 정보 제공용 · 투자 조언 아님.</p>
    </div>
  )
}

function FinancialTrend({ trend, trendQ, cur }) {
  const [freq, setFreq] = useState('annual')
  const t = freq === 'quarter' ? trendQ : trend
  const rev = t?.revenue
  return (
    <div>
      <div className="period" style={{ marginBottom: 12, width: 'fit-content' }}>
        <button className={freq === 'annual' ? 'active' : ''} onClick={() => setFreq('annual')}>연간</button>
        <button className={freq === 'quarter' ? 'active' : ''} onClick={() => setFreq('quarter')}>분기</button>
        {t?.source === 'DART' && <span className="muted" style={{ fontSize: '.74rem', marginLeft: 8 }}>· DART 전자공시</span>}
      </div>
      {(!rev || rev.length === 0) ? <p className="muted">재무 데이터가 없습니다 (해당 종목/주기 미제공).</p> : <FinBars trend={t} cur={cur} />}
    </div>
  )
}

function FinBars({ trend, cur }) {
  const rev = trend?.revenue
  if (!rev || rev.length === 0) return <p className="muted">재무 추세 데이터가 없습니다.</p>
  const max = Math.max(...rev.map(r => r.value || 0)) || 1
  const rows = [
    ['매출', trend.revenue, trend.revenue_yoy_pct],
    ['영업이익', trend.operating_income, trend.operating_income_yoy_pct],
    ['순이익', trend.net_income, trend.net_income_yoy_pct],
  ]
  return (
    <div className="fin">
      {rows.map(([name, series, yoy]) => series && (
        <div key={name} className="fin-row">
          <div className="fin-head"><b>{name}</b> <span>전년대비 <Pct v={yoy} /></span></div>
          <div className="fin-bars">
            {series.slice().reverse().map((p, i) => (
              <div key={i} className="fin-bar">
                <div className="bar" style={{ height: `${Math.max(4, ((p.value || 0) / max) * 95)}px` }} />
                <div className="fin-val">{fmtBig(p.value, cur)}</div>
                <div className="fin-yr">{p.year}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function Profile({ pf, filings }) {
  const [ko, setKo] = useState(null)
  const [kLoad, setKLoad] = useState(false)
  useEffect(() => { setKo(null) }, [pf])
  if (!pf || pf.error) return <p className="muted">기업 개요 데이터가 없습니다.</p>
  async function translate() {
    setKLoad(true)
    try {
      const r = await fetch(`/api/translate?text=${encodeURIComponent(pf.summary || '')}`)
      const d = await r.json(); setKo(d.text || '(번역 실패)')
    } catch { setKo('(번역 오류)') }
    setKLoad(false)
  }
  return (
    <div className="profile">
      <div className="metrics" style={{ marginBottom: 14 }}>
        <Metric label="섹터·산업">{pf.sector_ko || pf.sector || '—'}</Metric>
        <Metric label="산업(상세)">{pf.industry || '—'}</Metric>
        <Metric label="직원수">{pf.employees ? pf.employees.toLocaleString() + '명' : '—'}</Metric>
      </div>
      {pf.summary && (
        <>
          {!ko && <button className="senti-btn" onClick={translate} disabled={kLoad}>{kLoad ? '🇰🇷 번역 중…' : '🇰🇷 한국어 요약'}</button>}
          <p className="biz-summary">{ko || pf.summary}</p>
          {ko && <p className="muted" style={{ fontSize: '.74rem' }}>🤖 AI 한국어 요약 · 원문은 yfinance(영문)</p>}
        </>
      )}
      <div className="muted" style={{ fontSize: '.82rem', marginTop: 8 }}>
        {pf.country && <>본사: {pf.country} </>}
        {pf.website && <>· <a href={pf.website} target="_blank" rel="noreferrer">{pf.website.replace(/^https?:\/\//, '')}</a></>}
      </div>
      {filings && filings.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="m-label" style={{ marginBottom: 6 }}>📑 DART 공시 (공개 법정공시)</div>
          <ul className="news">
            {filings.map((f, i) => (
              <li key={i}><a href={f.link} target="_blank" rel="noreferrer">{f.title}</a> <span className="muted">— {f.date}</span></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Consensus({ a, cal, recs, cur }) {
  const noA = !a || a.error
  const noC = !cal || cal.error
  const recItems = (recs && recs.items) || []
  if (noA && noC && recItems.length === 0) return <p className="muted">컨센서스·일정 데이터가 없습니다 (yfinance 커버리지 제한).</p>
  return (
    <div>
      {!noA && (
        <div className="metrics" style={{ marginBottom: 14 }}>
          <Metric label="투자의견" sub={a.num_analysts ? `애널리스트 ${a.num_analysts}명` : null}>
            <span className={a.upside_pct > 0 ? 'up' : a.upside_pct < 0 ? 'down' : ''}>{a.recommendation_kr || '—'}</span>
          </Metric>
          <Metric label="목표주가(평균)" sub={a.upside_pct != null ? '상승여력' : null}>
            {fmtPrice(a.target_mean, cur)} {a.upside_pct != null && <span style={{ fontSize: '.9rem' }}><Pct v={a.upside_pct} /></span>}
          </Metric>
          <Metric label="목표 범위">{fmtPrice(a.target_low, cur)} ~ {fmtPrice(a.target_high, cur)}</Metric>
        </div>
      )}
      {!noC && (
        <div className="metrics" style={{ marginBottom: 14 }}>
          <Metric label="다음 실적 발표">{cal.next_earnings ? String(cal.next_earnings).slice(0, 10) : '—'}</Metric>
          <Metric label="배당수익률" sub={cal.ex_dividend_date ? `배당락 ${String(cal.ex_dividend_date).slice(0, 10)}` : null}>
            {cal.dividend_yield_pct != null ? `${cal.dividend_yield_pct}%` : '—'}
          </Metric>
          <Metric label="배당성향">{cal.payout_ratio_pct != null ? `${cal.payout_ratio_pct}%` : '—'}</Metric>
        </div>
      )}
      {recItems.length > 0 && (
        <div>
          <div className="m-label" style={{ marginBottom: 8 }}>최근 애널리스트 등급 변경</div>
          <ul className="recs">
            {recItems.map((r, i) => (
              <li key={i}>
                <span className="muted">{r.date}</span> <b>{r.firm}</b>
                <span className={r.action === '상향' ? 'up' : r.action === '하향' ? 'down' : 'muted'}> {r.action}</span>
                <span className="muted"> · {r.from && r.from !== r.to ? `${r.from} → ` : ''}{r.to}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="muted" style={{ fontSize: '.78rem' }}>※ yfinance 집계 공개 데이터(커버리지·시점 제한 가능). 투자 조언 아님.</p>
    </div>
  )
}

function Research({ ticker, name }) {
  const [q, setQ] = useState('')
  const [res, setRes] = useState(null)
  const [load, setLoad] = useState(false)
  useEffect(() => { setRes(null); setQ('') }, [ticker])
  async function run(question) {
    setLoad(true)
    try {
      const r = await fetch(`/api/research?query=${encodeURIComponent(ticker)}&q=${encodeURIComponent(question ?? q)}`)
      setRes(await r.json())
    } catch (e) { setRes({ answer: '오류: ' + e.message, sources: [] }) }
    setLoad(false)
  }
  return (
    <div>
      <p className="muted" style={{ fontSize: '.84rem', marginTop: 0 }}>
        뉴스·애널리스트·재무·DART공시·증권사 리포트(미래에셋)·내 PDF를 <b>벡터DB로 검색</b>해, <b>근거 자료만으로</b> 종합합니다(출처 인용).
      </p>
      <div className="search" style={{ marginBottom: 12 }}>
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && run()}
          placeholder={`${name}에 대해 무엇이든 (비우면 종합 분석)`} />
        <button onClick={() => run()} disabled={load}>{load ? '검색·종합 중…' : '📚 리서치'}</button>
      </div>
      {!res && !load && (
        <div className="examples">
          {['종합 분석', '최근 이슈와 리스크', '애널리스트 의견 요약', '재무는 어때?'].map(s => (
            <button key={s} onClick={() => { setQ(s === '종합 분석' ? '' : s); run(s === '종합 분석' ? '' : s) }}>{s}</button>
          ))}
        </div>
      )}
      {res && (
        <div className="card brief" style={{ marginTop: 12 }}>
          <div className="bubble-content" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{res.answer || res.error}</div>
          {(res.sources || []).length > 0 && (
            <div className="evidence">
              {res.sources.map((s, i) => (
                <div key={i} className="src">[{i + 1}] <b>{s.source}</b> {s.text?.slice(0, 80)}{s.link && <> — <a href={s.link} target="_blank" rel="noreferrer">원문</a></>}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Dashboard({ data, period, onPeriod, dark }) {
  const [tab, setTab] = useState('차트')
  const [showMA, setShowMA] = useState(true)
  const [senti, setSenti] = useState(null)
  const [sLoad, setSLoad] = useState(false)
  const p = data.price || {}, t = data.technicals || {}, f = data.fundamentals || {}, cur = p.currency

  const [brief, setBrief] = useState(null)
  const [bLoad, setBLoad] = useState(false)
  const [bm, setBm] = useState(isStock(data.ticker))
  useEffect(() => { setSenti(null); setBrief(null); setBm(isStock(data.ticker)) }, [data.ticker])

  async function runBriefing() {
    setBLoad(true)
    try {
      const r = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: `${data.name}(${data.ticker}) 종목을 종합 분석해줘. 시세 추세, 밸류에이션(PER/PBR), 애널리스트 의견·목표주가, 최근 뉴스 이슈를 출처와 함께 5줄 내외로 요약.` }),
      })
      const d = await r.json()
      setBrief(d)
    } catch (e) { setBrief({ answer: '오류: ' + e.message, evidence: [] }) }
    setBLoad(false)
  }

  async function analyzeSentiment() {
    setSLoad(true)
    try {
      const r = await fetch(`/api/news_sentiment?query=${encodeURIComponent(data.ticker)}`)
      const d = await r.json()
      const m = {}; (d.items || []).forEach(x => { m[x.title] = x.sentiment })
      setSenti(m)
    } catch { /* noop */ }
    setSLoad(false)
  }
  const sCls = s => s === '긍정' ? 's-pos' : s === '부정' ? 's-neg' : 's-neu'

  return (
    <>
      <div className="card header-card">
        <div>
          <div className="h-name">
            <button className="star" onClick={() => { toggleStock(data.ticker, data.name); setBm(isStock(data.ticker)) }} title="관심 종목">{bm ? '★' : '☆'}</button>
            {data.name} <span className="h-tk">{data.ticker} · {data.market}</span>
          </div>
          <div className="h-price">{fmtPrice(p.last_close, cur)} <Pct v={p.return_1m_pct} /> <span className="muted" style={{ fontSize: '.9rem' }}>1개월</span></div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="h-asof muted">기준일 {p.as_of || '—'}</div>
          <button className="senti-btn" style={{ marginTop: 8, marginBottom: 0 }} onClick={runBriefing} disabled={bLoad}>
            {bLoad ? '🤖 분석 중…' : '🤖 AI 종합 브리핑'}
          </button>
        </div>
      </div>
      {brief && (
        <div className="card brief">
          <div className="bubble-content" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>{brief.answer}</div>
          {(brief.evidence || []).length > 0 && (
            <div className="evidence">
              {brief.evidence.map((e, j) => (
                <div key={j} className="src">🔎 <b>{e.tool}</b> · {e.source}: {e.output}{e.link && <> — <a href={e.link} target="_blank" rel="noreferrer">출처</a></>}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="metrics">
        <Metric label="1주 / 3개월 / 1년"><Pct v={p.return_1w_pct} /> / <Pct v={p.return_3m_pct} /> / <Pct v={p.return_1y_pct} /></Metric>
        <Metric label="52주 위치" sub={`${fmtPrice(p.week52_low, cur)} ~ ${fmtPrice(p.week52_high, cur)}`}>{p.week52_position_pct != null ? `${p.week52_position_pct}%` : '—'}</Metric>
        <Metric label="RSI(14)" sub={t.RSI_state}>{t.RSI14 ?? '—'}</Metric>
        <Metric label="이평 신호" sub={t.vs_MA20}>{t.cross_signal || '—'}</Metric>
        <Metric label="PER / PBR">{f.PER ?? '—'} / {f.PBR ?? '—'}</Metric>
        <Metric label="목표주가" sub={data.analyst && !data.analyst.error ? data.analyst.recommendation_kr : null}>
          {data.analyst && !data.analyst.error ? fmtPrice(data.analyst.target_mean, cur) : '—'}
        </Metric>
      </div>

      <ScoreCard s={data.score} />

      <div className="card">
        <div className="tabs">
          {['차트', '📚 리서치', '기업개요', '컨센서스·배당', '기술적', '재무', '뉴스'].map(x => (
            <button key={x} className={tab === x ? 'active' : ''} onClick={() => setTab(x)}>{x}</button>
          ))}
        </div>
        <div className="tab-body">
          {tab === '차트' && (
            <>
              <div className="chart-controls">
                <div className="period">
                  {PERIODS.map(pp => (
                    <button key={pp} className={period === pp ? 'active' : ''} onClick={() => onPeriod(pp)}>{PLABEL[pp]}</button>
                  ))}
                </div>
                <label className="ma-toggle"><input type="checkbox" checked={showMA} onChange={e => setShowMA(e.target.checked)} /> 이동평균</label>
              </div>
              {data.history?.candles?.length
                ? <PriceChart candles={data.history.candles} showMA={showMA} dark={dark} />
                : <p className="muted">차트 데이터가 없습니다.</p>}
            </>
          )}
          {tab === '📚 리서치' && <Research ticker={data.ticker} name={data.name} />}
          {tab === '기업개요' && <Profile pf={data.profile} filings={data.filings} />}
          {tab === '컨센서스·배당' && <Consensus a={data.analyst} cal={data.calendar} recs={data.recommendations} cur={cur} />}
          {tab === '기술적' && (
            <div className="tech-grid">
              <Metric label="RSI(14)" sub={t.RSI_state}>{t.RSI14 ?? '—'}</Metric>
              <Metric label="MA20">{fmtPrice(t.MA20, cur)}</Metric>
              <Metric label="MA60">{fmtPrice(t.MA60, cur)}</Metric>
              <Metric label="MA120">{fmtPrice(t.MA120, cur)}</Metric>
              <Metric label="현재가 vs MA20">{t.vs_MA20 || '—'}</Metric>
              <Metric label="크로스 신호">{t.cross_signal || '—'}</Metric>
            </div>
          )}
          {tab === '재무' && <FinancialTrend trend={data.financial_trend} trendQ={data.financial_trend_q} cur={cur} />}
          {tab === '뉴스' && (
            <>
              {(data.news?.news?.length > 0) && (
                <button className="senti-btn" onClick={analyzeSentiment} disabled={sLoad}>
                  {sLoad ? '🤖 분석 중…' : '🤖 AI 감성 분석'}
                </button>
              )}
              <ul className="news">
                {(data.news?.news || []).map((n, i) => (
                  <li key={i}>
                    {senti && senti[n.title] && <span className={`badge ${sCls(senti[n.title])}`}>{senti[n.title]}</span>}
                    <a href={n.link} target="_blank" rel="noreferrer">{n.title}</a> <span className="muted">— {n.publisher}</span>
                  </li>
                ))}
                {(!data.news?.news || data.news.news.length === 0) && <li className="muted">뉴스가 없습니다.</li>}
              </ul>
            </>
          )}
        </div>
      </div>
      <div className="disclaimer muted">※ 정보 제공용이며 투자 조언이 아닙니다. 데이터: yfinance·네이버 금융(무료, 지연·오차 가능).</div>
    </>
  )
}
