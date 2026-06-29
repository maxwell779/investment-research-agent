import { useState, useEffect } from 'react'
import { Pct } from './ui'

export default function Home() {
  const [data, setData] = useState(null)
  useEffect(() => { fetch('/api/market').then(r => r.json()).then(setData).catch(() => {}) }, [])

  return (
    <div>
      <div className="card">
        <h3 style={{ margin: '0 0 14px' }}>📊 시장 현황 <span className="muted" style={{ fontSize: '.8rem', fontWeight: 500 }}>주요 지수·환율</span></h3>
        <div className="idx-grid">
          {(data?.indices || []).map(i => (
            <div key={i.symbol} className="idx">
              <div className="idx-name">{i.name}</div>
              <div className="idx-val">{i.last != null ? i.last.toLocaleString() : '—'}</div>
              <div className="idx-chg"><Pct v={i.change_pct} /></div>
            </div>
          ))}
          {!data && <div className="muted">로딩…</div>}
        </div>
      </div>

      <div className="card">
        <h3 style={{ margin: '0 0 12px' }}>📰 시장 주요 뉴스 <span className="muted" style={{ fontSize: '.8rem', fontWeight: 500 }}>네이버 뉴스</span></h3>
        <ul className="news">
          {(data?.news || []).map((n, i) => (
            <li key={i}><a href={n.link} target="_blank" rel="noreferrer">{n.title}</a> <span className="muted">— {n.publisher}</span></li>
          ))}
          {data && (!data.news || data.news.length === 0) && <li className="muted">뉴스를 불러오지 못했습니다.</li>}
        </ul>
      </div>
      <div className="disclaimer muted">※ 지수·환율·뉴스는 실시간 무료 데이터(지연 가능). 투자 조언 아님.</div>
    </div>
  )
}
