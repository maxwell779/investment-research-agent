import { useState, useEffect } from 'react'
import { fetchDashboard } from './api'
import Dashboard from './Dashboard'
import Compare from './Compare'
import Chat from './Chat'

export default function App() {
  const [view, setView] = useState('single')      // single | compare
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')
  const [query, setQuery] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [period, setPeriod] = useState('6mo')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  async function load(q, per) {
    const query2 = (q ?? query).trim()
    if (!query2) return
    setLoading(true); setErr('')
    try {
      const d = await fetchDashboard(query2, per ?? period)
      if (d.error) { setErr(d.error); setData(null) }
      else setData(d)
    } catch (e) { setErr(e.message) }
    setLoading(false)
  }

  function changePeriod(pp) {
    setPeriod(pp)
    if (data) load(data.ticker, pp)
  }

  const dark = theme === 'dark'

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">📈 AI 투자 리서치</div>
        <div className="viewtabs">
          <button className={view === 'single' ? 'active' : ''} onClick={() => setView('single')}>종목 분석</button>
          <button className={view === 'compare' ? 'active' : ''} onClick={() => setView('compare')}>종목 비교</button>
        </div>
        {view === 'single' && (
          <div className="search">
            <input value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && load()}
              placeholder="종목명/심볼 (예: 삼성전자, AAPL, 엔비디아)" />
            <button onClick={() => load()} disabled={loading}>{loading ? '조회 중…' : '조회'}</button>
          </div>
        )}
        <button className="theme-btn" onClick={() => setTheme(dark ? 'light' : 'dark')} title="테마 전환">
          {dark ? '☀' : '☾'}
        </button>
      </header>

      <main className="layout">
        <section className="dash">
          {view === 'single' ? (
            <>
              {view === 'single' && (
                <div className="examples" style={{ marginBottom: 14 }}>
                  {['삼성전자', 'SK하이닉스', 'AAPL', 'NVDA', '테슬라'].map(s => (
                    <button key={s} onClick={() => { setQuery(s); load(s) }}>{s}</button>
                  ))}
                </div>
              )}
              {err && <div className="card error">⚠️ {err}</div>}
              {!data && !err && <div className="card empty">종목을 검색하면 시세·기술적 지표·재무·애널리스트 컨센서스·뉴스를 한눈에. (실시간 무료 데이터)</div>}
              {data && <Dashboard data={data} period={period} onPeriod={changePeriod} dark={dark} />}
            </>
          ) : (
            <Compare dark={dark} />
          )}
        </section>
        <aside className="side">
          <Chat ticker={data?.name} />
        </aside>
      </main>
    </div>
  )
}
