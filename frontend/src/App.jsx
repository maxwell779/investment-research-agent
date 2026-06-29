import { useState } from 'react'
import { fetchDashboard } from './api'
import PriceChart from './PriceChart'
import Chat from './Chat'

const CUR = { KRW: '원', USD: '$' }

function fmtPrice(v, cur) {
  if (v == null) return '—'
  const n = Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
  return cur === 'USD' ? `$${n}` : `${n}원`
}
function fmtBig(v, cur) {
  if (v == null) return '—'
  if (typeof v === 'string') return v // 네이버 시총("1,867조") 등 이미 포맷됨
  const a = Math.abs(v)
  if (cur === 'KRW' || cur == null) {
    if (a >= 1e12) return `${(v / 1e12).toFixed(1)}조`
    if (a >= 1e8) return `${(v / 1e8).toFixed(0)}억`
  }
  if (a >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (a >= 1e6) return `$${(v / 1e6).toFixed(0)}M`
  return Number(v).toLocaleString()
}
function Pct({ v }) {
  if (v == null) return <span className="muted">—</span>
  const cls = v > 0 ? 'up' : v < 0 ? 'down' : 'flat'
  const arrow = v > 0 ? '▲' : v < 0 ? '▼' : '–' // 색+형태 병행(색각 접근성)
  return <span className={cls}>{arrow} {v > 0 ? '+' : ''}{v}%</span>
}

function Metric({ label, children, sub }) {
  return (
    <div className="metric">
      <div className="m-label">{label}</div>
      <div className="m-value">{children}</div>
      {sub && <div className="m-sub">{sub}</div>}
    </div>
  )
}

function FinancialTrend({ trend, cur }) {
  const rev = trend?.revenue
  if (!rev || rev.length === 0) return <p className="muted">재무 추세 데이터가 없습니다 (해당 종목 미제공).</p>
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
                <div className="bar" style={{ height: `${Math.max(4, ((p.value || 0) / max) * 90)}px` }} />
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

export default function App() {
  const [query, setQuery] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState('차트')

  async function search(q) {
    const query2 = (q ?? query).trim()
    if (!query2) return
    setLoading(true); setErr(''); setData(null)
    try {
      const d = await fetchDashboard(query2)
      if (d.error) setErr(d.error)
      else { setData(d); setTab('차트') }
    } catch (e) { setErr(e.message) }
    setLoading(false)
  }

  const p = data?.price || {}
  const t = data?.technicals || {}
  const f = data?.fundamentals || {}
  const cur = p.currency

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">📈 AI 투자 리서치 에이전트</div>
        <div className="search">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && search()}
            placeholder="종목명 또는 심볼 (예: 삼성전자, AAPL, 엔비디아)"
          />
          <button onClick={() => search()} disabled={loading}>{loading ? '조회 중…' : '조회'}</button>
        </div>
        <div className="examples">
          {['삼성전자', 'SK하이닉스', 'AAPL', 'NVDA'].map(s => (
            <button key={s} onClick={() => { setQuery(s); search(s) }}>{s}</button>
          ))}
        </div>
      </header>

      <main className="layout">
        <section className="dash">
          {err && <div className="card error">⚠️ {err}</div>}
          {!data && !err && <div className="card empty">종목을 검색하면 시세·기술적 지표·재무·뉴스를 한눈에 보여줍니다. (데이터는 실시간 무료 소스)</div>}

          {data && (
            <>
              <div className="card header-card">
                <div>
                  <div className="h-name">{data.name} <span className="h-tk">{data.ticker} · {data.market}</span></div>
                  <div className="h-price">{fmtPrice(p.last_close, cur)} <Pct v={p.return_1m_pct} /> <span className="muted">(1개월)</span></div>
                </div>
                <div className="h-asof muted">기준일 {p.as_of || '—'}</div>
              </div>

              <div className="metrics">
                <Metric label="1주 / 3개월 / 1년"><Pct v={p.return_1w_pct} /> / <Pct v={p.return_3m_pct} /> / <Pct v={p.return_1y_pct} /></Metric>
                <Metric label="52주 위치" sub={`${fmtPrice(p.week52_low, cur)} ~ ${fmtPrice(p.week52_high, cur)}`}>{p.week52_position_pct != null ? `${p.week52_position_pct}%` : '—'}</Metric>
                <Metric label="RSI(14)" sub={t.RSI_state}>{t.RSI14 ?? '—'}</Metric>
                <Metric label="이평 신호" sub={t.vs_MA20}>{t.cross_signal || '—'}</Metric>
                <Metric label="PER / PBR">{f.PER ?? '—'} / {f.PBR ?? '—'}</Metric>
                <Metric label="시가총액">{fmtBig(f.시가총액 ?? f.marketCap, cur)}</Metric>
              </div>

              <div className="card">
                <div className="tabs">
                  {['차트', '기술적', '재무', '뉴스'].map(x => (
                    <button key={x} className={tab === x ? 'active' : ''} onClick={() => setTab(x)}>{x}</button>
                  ))}
                </div>
                <div className="tab-body">
                  {tab === '차트' && (data.history?.candles?.length
                    ? <PriceChart candles={data.history.candles} />
                    : <p className="muted">차트 데이터가 없습니다.</p>)}
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
                  {tab === '재무' && <FinancialTrend trend={data.financial_trend} cur={cur} />}
                  {tab === '뉴스' && (
                    <ul className="news">
                      {(data.news?.news || []).map((n, i) => (
                        <li key={i}><a href={n.link} target="_blank" rel="noreferrer">{n.title}</a> <span className="muted">— {n.publisher}</span></li>
                      ))}
                      {(!data.news?.news || data.news.news.length === 0) && <li className="muted">뉴스가 없습니다.</li>}
                    </ul>
                  )}
                </div>
              </div>
              <div className="disclaimer muted">※ 정보 제공용이며 투자 조언이 아닙니다. 데이터: yfinance·네이버 금융(무료, 지연·오차 가능).</div>
            </>
          )}
        </section>

        <aside className="side">
          <Chat ticker={data?.name} />
        </aside>
      </main>
    </div>
  )
}
