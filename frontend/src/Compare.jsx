import { useState, useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'
import { fmtPrice, fmtBig, Pct } from './ui'

const COLORS = ['#00c39a', '#f59e0b', '#8b5cf6', '#ef4444']

function NormChart({ items, dark }) {
  const ref = useRef(null)
  useEffect(() => {
    const valid = (items || []).filter(i => i.norm && i.norm.length)
    if (!ref.current || !valid.length) return
    const T = dark
      ? { bg: '#0f172a', text: '#cbd5e1', grid: '#1e293b', border: '#334155' }
      : { bg: '#ffffff', text: '#475569', grid: '#f1f5f9', border: '#e2e8f0' }
    const chart = createChart(ref.current, {
      height: 340, width: ref.current.clientWidth,
      layout: { background: { color: T.bg }, textColor: T.text, fontFamily: 'inherit' },
      grid: { vertLines: { color: T.grid }, horzLines: { color: T.grid } },
      rightPriceScale: { borderColor: T.border }, timeScale: { borderColor: T.border }, crosshair: { mode: 0 },
    })
    valid.forEach((it, idx) => {
      const s = chart.addLineSeries({ color: COLORS[idx % COLORS.length], lineWidth: 2, priceLineVisible: false })
      s.setData(it.norm.map(p => ({ time: p.t, value: p.v })))
    })
    chart.timeScale().fitContent()
    const onR = () => chart.applyOptions({ width: ref.current.clientWidth })
    window.addEventListener('resize', onR)
    return () => { window.removeEventListener('resize', onR); chart.remove() }
  }, [items, dark])
  return <div ref={ref} />
}

export default function Compare({ dark }) {
  const [input, setInput] = useState('삼성전자, SK하이닉스')
  const [items, setItems] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function run(q) {
    const v = (q ?? input).trim()
    if (!v) return
    setLoading(true); setErr('')
    try {
      const r = await fetch(`/api/compare?tickers=${encodeURIComponent(v)}`)
      const d = await r.json()
      setItems(d.items || [])
    } catch (e) { setErr(e.message) }
    setLoading(false)
  }

  const ok = (items || []).filter(i => !i.error)

  return (
    <div>
      <div className="card">
        <div className="search">
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
            placeholder="쉼표로 2~4개 (예: 삼성전자, SK하이닉스, AAPL)" />
          <button onClick={() => run()} disabled={loading}>{loading ? '비교 중…' : '비교'}</button>
        </div>
        {err && <p className="error">⚠️ {err}</p>}
      </div>

      {ok.length > 0 && (
        <>
          <div className="card">
            <div className="cmp-legend">
              {ok.map((it, i) => <span key={i}><i style={{ background: COLORS[i % COLORS.length] }} />{it.name}</span>)}
              <span className="muted">· 시작일=100 정규화</span>
            </div>
            <NormChart items={ok} dark={dark} />
          </div>
          <div className="card" style={{ overflowX: 'auto' }}>
            <table className="cmp-table">
              <thead><tr><th>종목</th><th>현재가</th><th>1개월</th><th>3개월</th><th>1년</th><th>PER</th><th>PBR</th><th>RSI</th><th>시총</th></tr></thead>
              <tbody>
                {ok.map((it, i) => (
                  <tr key={i}>
                    <td><b>{it.name}</b><div className="muted" style={{ fontSize: '.74rem' }}>{it.ticker}</div></td>
                    <td>{fmtPrice(it.last, it.currency)}</td>
                    <td><Pct v={it.return_1m} /></td>
                    <td><Pct v={it.return_3m} /></td>
                    <td><Pct v={it.return_1y} /></td>
                    <td>{it.PER ?? '—'}</td>
                    <td>{it.PBR ?? '—'}</td>
                    <td>{it.RSI ?? '—'}</td>
                    <td>{fmtBig(it.marketcap, it.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {items && (items.some(i => i.error)) && (
        <div className="card muted">일부 종목을 찾지 못함: {items.filter(i => i.error).map(i => i.query).join(', ')}</div>
      )}
      {!items && <div className="card empty">비교할 종목을 입력하세요 (정규화 가격 추이 + 핵심 지표 비교).</div>}
    </div>
  )
}
