// 공통 포맷/표시 헬퍼
export const fmtPrice = (v, cur) =>
  v == null ? '—' : (cur === 'USD'
    ? `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
    : `${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}원`)

export function fmtBig(v, cur) {
  if (v == null) return '—'
  if (typeof v === 'string') return v
  const a = Math.abs(v)
  if (cur === 'KRW' || cur == null) {
    if (a >= 1e12) return `${(v / 1e12).toFixed(1)}조`
    if (a >= 1e8) return `${(v / 1e8).toFixed(0)}억`
  }
  if (a >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (a >= 1e6) return `$${(v / 1e6).toFixed(0)}M`
  return Number(v).toLocaleString()
}

// 등락: 색 + 화살표(▲▼) 병행 (색각 접근성)
export function Pct({ v }) {
  if (v == null) return <span className="muted">—</span>
  const cls = v > 0 ? 'up' : v < 0 ? 'down' : 'flat'
  const arrow = v > 0 ? '▲' : v < 0 ? '▼' : '–'
  return <span className={cls}>{arrow} {v > 0 ? '+' : ''}{v}%</span>
}

export function Metric({ label, children, sub }) {
  return (
    <div className="metric">
      <div className="m-label">{label}</div>
      <div className="m-value">{children}</div>
      {sub && <div className="m-sub">{sub}</div>}
    </div>
  )
}
