import { useState, useEffect } from 'react'
import { fmtPrice, fmtBig, Pct } from './ui'

export default function Screener() {
  const [f, setF] = useState({ market: 'all', per_max: '', ret1m_min: '', rsi_min: '', rsi_max: '', sort: 'marketcap' })
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)

  async function run() {
    setLoading(true)
    const qs = new URLSearchParams()
    qs.set('market', f.market); qs.set('sort', f.sort)
    for (const k of ['per_max', 'ret1m_min', 'rsi_min', 'rsi_max']) if (f[k] !== '') qs.set(k, f[k])
    try { const r = await fetch(`/api/screener?${qs}`); setRes(await r.json()) }
    catch (e) { setRes({ error: e.message, rows: [] }) }
    setLoading(false)
  }
  useEffect(() => { run() }, [])  // 최초 1회

  const rows = res?.rows || []
  return (
    <div>
      <div className="card">
        <h3 style={{ margin: '0 0 14px' }}>🔎 스크리너 <span className="muted" style={{ fontSize: '.8rem', fontWeight: 500 }}>큐레이션 유니버스 · 일배치 {res?.as_of ? `(${res.as_of})` : ''}</span></h3>
        <div className="scr-filters">
          <label>시장
            <select value={f.market} onChange={e => setF({ ...f, market: e.target.value })}>
              <option value="all">전체</option><option value="KR">한국</option><option value="US">미국</option>
            </select>
          </label>
          <label>PER ≤ <input type="number" value={f.per_max} onChange={e => setF({ ...f, per_max: e.target.value })} placeholder="예 20" /></label>
          <label>1개월 ≥ <input type="number" value={f.ret1m_min} onChange={e => setF({ ...f, ret1m_min: e.target.value })} placeholder="%" /></label>
          <label>RSI <input type="number" value={f.rsi_min} onChange={e => setF({ ...f, rsi_min: e.target.value })} placeholder="min" style={{ width: 56 }} /> ~ <input type="number" value={f.rsi_max} onChange={e => setF({ ...f, rsi_max: e.target.value })} placeholder="max" style={{ width: 56 }} /></label>
          <label>정렬
            <select value={f.sort} onChange={e => setF({ ...f, sort: e.target.value })}>
              <option value="marketcap">시총↓</option><option value="return">1개월↓</option><option value="per">PER↑</option><option value="rsi">RSI↓</option>
            </select>
          </label>
          <button onClick={run} disabled={loading}>{loading ? '필터 중…' : '필터'}</button>
        </div>
      </div>

      <div className="card" style={{ overflowX: 'auto' }}>
        <table className="cmp-table">
          <thead><tr><th>종목</th><th>시장</th><th>현재가</th><th>1개월</th><th>3개월</th><th>PER</th><th>PBR</th><th>RSI</th><th>시총</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td><b>{r.name}</b><div className="muted" style={{ fontSize: '.74rem' }}>{r.ticker}</div></td>
                <td>{r.market}</td>
                <td>{fmtPrice(r.last, r.currency)}</td>
                <td><Pct v={r.return_1m} /></td>
                <td><Pct v={r.return_3m} /></td>
                <td>{r.PER ?? '—'}</td>
                <td>{r.PBR ?? '—'}</td>
                <td>{r.RSI ?? '—'}</td>
                <td>{fmtBig(r.marketcap, r.currency)}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan="9" className="muted" style={{ textAlign: 'center', padding: 30 }}>{loading ? '로딩…' : '조건에 맞는 종목이 없습니다.'}</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="disclaimer muted">※ 큐레이션된 대형주 유니버스의 일배치 데이터입니다(실시간 전체 스캔은 무료 데이터로 제한). 투자 조언 아님.</div>
    </div>
  )
}
