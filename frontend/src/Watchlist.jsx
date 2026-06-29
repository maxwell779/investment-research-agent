import { useState, useEffect } from 'react'
import { fmtPrice, Pct } from './ui'
import { getStocks, getSectors, toggleStock, toggleSector } from './bookmarks'

export default function Watchlist({ onPick }) {
  const [stocks, setStocks] = useState(getStocks())
  const [sectors, setSectors] = useState(getSectors())
  const [quotes, setQuotes] = useState({})

  useEffect(() => {
    const tks = stocks.map(s => s.ticker)
    if (!tks.length) { setQuotes({}); return }
    fetch(`/api/quotes?tickers=${encodeURIComponent(tks.join(','))}`)
      .then(r => r.json()).then(d => {
        const m = {}; (d.quotes || []).forEach(q => { if (!q.error) m[q.ticker] = q }); setQuotes(m)
      }).catch(() => {})
  }, [stocks])

  return (
    <div>
      <div className="card">
        <h3 style={{ margin: '0 0 6px' }}>⭐ 관심 종목·섹터 <span className="muted" style={{ fontSize: '.8rem', fontWeight: 500 }}>(브라우저 저장)</span></h3>
        {sectors.length > 0 && (
          <div className="examples" style={{ marginTop: 10 }}>
            {sectors.map(s => (
              <button key={s} onClick={() => { toggleSector(s); setSectors(getSectors()) }}>★ {s} ✕</button>
            ))}
          </div>
        )}
      </div>

      {stocks.length === 0 ? (
        <div className="card empty">종목 분석/랭킹 화면에서 ★를 눌러 관심 종목을 추가하세요.</div>
      ) : (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table className="cmp-table">
            <thead><tr><th></th><th>종목</th><th>현재가</th><th>1개월</th><th></th></tr></thead>
            <tbody>
              {stocks.map((s) => {
                const q = quotes[s.ticker]
                return (
                  <tr key={s.ticker}>
                    <td><button className="star" onClick={() => { toggleStock(s.ticker, s.name); setStocks(getStocks()) }}>★</button></td>
                    <td><button className="namelink" onClick={() => onPick && onPick(s.name || s.ticker)}><b>{s.name}</b></button><div className="muted" style={{ fontSize: '.72rem' }}>{s.ticker}</div></td>
                    <td>{q ? fmtPrice(q.last, q.currency) : '…'}</td>
                    <td><Pct v={q?.return_1m} /></td>
                    <td><button className="namelink muted" onClick={() => onPick && onPick(s.name || s.ticker)}>분석 →</button></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
