// FastAPI 백엔드 호출 (dev에선 vite proxy, prod에선 동일 오리진)
export async function fetchDashboard(query, period = '6mo') {
  const r = await fetch(`/api/dashboard?query=${encodeURIComponent(query)}&period=${period}`)
  if (!r.ok) throw new Error(`서버 오류 ${r.status}`)
  return r.json()
}

export async function chat(question) {
  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!r.ok) throw new Error(`서버 오류 ${r.status}`)
  return r.json()
}
