import { useState, useEffect } from 'react'
import { fmtPrice, Pct } from './ui'

const KEY = 'portfolio_v1'
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || [] } catch { return [] } }
const save = (h) => localStorage.setItem(KEY, JSON.stringify(h))

export default function Portfolio() {
  const [holds, setHolds] = useState(load)
  const [quotes, setQuotes] = useState({})       // ticker -> {last,currency,name}
  const [form, setForm] = useState({ q: '', qty: '', avg: '' })
  const [busy, setBusy] = useState(false)

  useEffect(() => { save(holds); refresh() }, [holds])

  async function refresh() {
    const qs = holds.map(h => h.ticker).filter(Boolean)
    if (!qs.length) { setQuotes({}); return }
    try {
      const r = await fetch(`/api/quotes?tickers=${encodeURIComponent(qs.join(','))}`)
      const d = await r.json()
      const m = {}; (d.quotes || []).forEach(x => { if (!x.error) m[x.ticker] = x })
      setQuotes(m)
    } catch { /* noop */ }
  }

  async function add() {
    const q = form.q.trim(), qty = parseFloat(form.qty), avg = parseFloat(form.avg)
    if (!q || !(qty > 0) || !(avg > 0) || busy) return
    setBusy(true)
    try {
      const r = await fetch(`/api/quotes?tickers=${encodeURIComponent(q)}`)
      const d = await r.json()
      const item = (d.quotes || [])[0]
      if (!item || item.error) { alert('종목을 찾지 못했습니다: ' + q); setBusy(false); return }
      setHolds(h => [...h, { ticker: item.ticker, name: item.name, currency: item.currency, qty, avg }])
      setForm({ q: '', qty: '', avg: '' })
    } catch (e) { alert('오류: ' + e.message) }
    setBusy(false)
  }

  const remove = (i) => setHolds(h => h.filter((_, j) => j !== i))

  // 통화별 합계
  const totals = {}
  holds.forEach(h => {
    const cur = h.currency || 'KRW'
    const last = quotes[h.ticker]?.last
    if (last == null) return
    totals[cur] = totals[cur] || { cost: 0, value: 0 }
    totals[cur].cost += h.avg * h.qty
    totals[cur].value += last * h.qty
  })

  return (
    <div>
      <div className="card">
        <h3 style={{ margin: '0 0 14px' }}>💼 내 포트폴리오 <span className="muted" style={{ fontSize: '.8rem', fontWeight: 500 }}>(브라우저에만 저장 · 서버 전송 없음)</span></h3>
        <div className="pf-form">
          <input placeholder="종목(예: 삼성전자/AAPL)" value={form.q} onChange={e => setForm({ ...form, q: e.target.value })} />
          <input placeholder="수량" type="number" value={form.qty} onChange={e => setForm({ ...form, qty: e.target.value })} />
          <input placeholder="평균단가" type="number" value={form.avg} onChange={e => setForm({ ...form, avg: e.target.value })} />
          <button onClick={add} disabled={busy}>{busy ? '추가 중…' : '추가'}</button>
        </div>
      </div>

      {holds.length === 0 ? (
        <div className="card empty">보유 종목을 추가하면 실시간 평가손익을 계산합니다.</div>
      ) : (
        <>
          <div className="card" style={{ overflowX: 'auto' }}>
            <table className="cmp-table">
              <thead><tr><th>종목</th><th>수량</th><th>평단</th><th>현재가</th><th>평가금액</th><th>손익</th><th>수익률</th><th></th></tr></thead>
              <tbody>
                {holds.map((h, i) => {
                  const last = quotes[h.ticker]?.last
                  const cur = h.currency
                  const val = last != null ? last * h.qty : null
                  const pl = last != null ? (last - h.avg) * h.qty : null
                  const ret = last != null ? +(((last / h.avg) - 1) * 100).toFixed(2) : null
                  return (
                    <tr key={i}>
                      <td><b>{h.name}</b><div className="muted" style={{ fontSize: '.74rem' }}>{h.ticker}</div></td>
                      <td>{h.qty}</td>
                      <td>{fmtPrice(h.avg, cur)}</td>
                      <td>{last != null ? fmtPrice(last, cur) : '…'}</td>
                      <td>{val != null ? fmtPrice(val, cur) : '…'}</td>
                      <td className={pl > 0 ? 'up' : pl < 0 ? 'down' : ''}>{pl != null ? fmtPrice(Math.round(pl), cur) : '…'}</td>
                      <td><Pct v={ret} /></td>
                      <td><button className="x" onClick={() => remove(i)}>✕</button></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="card pf-totals">
            {Object.entries(totals).map(([cur, t]) => {
              const pl = t.value - t.cost
              const ret = t.cost ? +((t.value / t.cost - 1) * 100).toFixed(2) : null
              return (
                <div key={cur} className="pf-total">
                  <div className="muted">{cur} 합계</div>
                  <div className="pf-total-val">{fmtPrice(Math.round(t.value), cur)}</div>
                  <div className={pl > 0 ? 'up' : pl < 0 ? 'down' : ''}>{fmtPrice(Math.round(pl), cur)} (<Pct v={ret} />)</div>
                </div>
              )
            })}
          </div>
        </>
      )}
      <div className="disclaimer muted">※ 보유 정보는 브라우저(localStorage)에만 저장됩니다. 정보 제공용 · 투자 조언 아님.</div>
    </div>
  )
}
