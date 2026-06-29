import { useState, useEffect } from 'react'
import { fmtBig, Pct } from './ui'
import { isStock, toggleStock, isSector, toggleSector } from './bookmarks'

export default function Ranking() {
  const [data, setData] = useState(null)
  const [by, setBy] = useState('marketcap')
  const [country, setCountry] = useState('all')
  const [sector, setSector] = useState('all')
  const [, force] = useState(0)

  async function run() {
    const qs = new URLSearchParams({ by, country, sector })
    try { const r = await fetch(`/api/ranking?${qs}`); setData(await r.json()) } catch { /* */ }
  }
  useEffect(() => { run() }, [by, country, sector])

  const rows = data?.rows || []
  const maxMc = Math.max(...(data?.by_country || []).map(([, v]) => v), 1)

  return (
    <div>
      <div className="card">
        <h3 style={{ margin: '0 0 14px' }}>🌐 글로벌 랭킹·비교 <span className="muted" style={{ fontSize: '.8rem', fontWeight: 500 }}>시총 USD 환산 · 일배치 {data?.as_of ? `(${data.as_of})` : ''}</span></h3>
        <div className="scr-filters">
          <label>정렬
            <select value={by} onChange={e => setBy(e.target.value)}>
              <option value="marketcap">시가총액(USD)↓</option><option value="return">1개월 등락↓</option>
            </select>
          </label>
          <label>국가
            <select value={country} onChange={e => setCountry(e.target.value)}>
              <option value="all">전체</option>
              {(data?.countries || []).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label>섹터
            <select value={sector} onChange={e => setSector(e.target.value)}>
              <option value="all">전체</option>
              {(data?.sectors || []).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>
      </div>

      {country === 'all' && sector === 'all' && (data?.by_country?.length > 0) && (
        <div className="card">
          <div className="m-label" style={{ marginBottom: 10 }}>국가별 시가총액 합계 (USD, 유니버스 기준)</div>
          {data.by_country.map(([c, v]) => (
            <div key={c} className="bc-row">
              <span className="bc-name">{c}</span>
              <div className="bc-bar-wrap"><div className="bc-bar" style={{ width: `${(v / maxMc) * 100}%` }} /></div>
              <span className="bc-val">{fmtBig(v, 'USD')}</span>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ overflowX: 'auto' }}>
        <table className="cmp-table">
          <thead><tr><th></th><th>#</th><th>종목</th><th>국가</th><th>섹터</th><th>1개월</th><th>PER</th><th>시총(USD)</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.ticker}>
                <td><button className="star" onClick={() => { toggleStock(r.ticker, r.name); force(x => x + 1) }}>{isStock(r.ticker) ? '★' : '☆'}</button></td>
                <td className="muted">{i + 1}</td>
                <td><b>{r.name}</b><div className="muted" style={{ fontSize: '.72rem' }}>{r.ticker}</div></td>
                <td>{r.country}</td>
                <td className="muted" style={{ fontSize: '.8rem' }}>
                  {r.sector ? <button className="seclink" onClick={() => { toggleSector(r.sector); force(x => x + 1) }} title="섹터 즐겨찾기">{isSector(r.sector) ? '★ ' : ''}{r.sector}</button> : '—'}
                </td>
                <td><Pct v={r.return_1m} /></td>
                <td>{r.PER ?? '—'}</td>
                <td>{fmtBig(r.marketcap_usd, 'USD')}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan="8" className="muted" style={{ textAlign: 'center', padding: 30 }}>유니버스 로딩 중… (build_universe.py 실행 필요)</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="disclaimer muted">※ 큐레이션된 글로벌 대형주 유니버스의 일배치 데이터 · 시총은 환율 환산 USD. 투자 조언 아님.</div>
    </div>
  )
}
