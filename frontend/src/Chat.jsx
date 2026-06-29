import { useState, useEffect, useRef } from 'react'
import { chat } from './api'

export default function Chat({ ticker }) {
  const [msgs, setMsgs] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, loading])

  async function send(q) {
    const question = (q ?? input).trim()
    if (!question || loading) return
    setMsgs(m => [...m, { role: 'user', content: question }])
    setInput('')
    setLoading(true)
    try {
      const r = await chat(question)
      setMsgs(m => [...m, { role: 'assistant', content: r.answer, evidence: r.evidence || [] }])
    } catch (e) {
      setMsgs(m => [...m, { role: 'assistant', content: '오류: ' + e.message, evidence: [] }])
    }
    setLoading(false)
  }

  const suggestions = ticker
    ? [`${ticker} 지금 투자 매력 분석해줘`, `${ticker} 기술적 지표 어때?`, `${ticker} 재무 성장 추세는?`]
    : ['삼성전자 지금 어때?', '애플 vs 마이크로소프트 비교해줘', '엔비디아 기술적 지표 분석해줘']

  return (
    <div className="chat card">
      <div className="chat-head">🤖 AI 리서치 <span className="muted">— 도구로 실제 데이터를 모아 출처와 함께 답합니다</span></div>
      <div className="chat-body">
        {msgs.length === 0 && (
          <div className="suggest">
            {suggestions.map((s, i) => (
              <button key={i} onClick={() => send(s)} disabled={loading}>{s}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <div className="bubble-content">{m.content}</div>
            {m.evidence && m.evidence.length > 0 && (
              <div className="evidence">
                {m.evidence.map((e, j) => (
                  <div key={j} className="src">
                    🔎 <b>{e.tool}</b> · {e.source}: {e.output}
                    {e.link && <> — <a href={e.link} target="_blank" rel="noreferrer">기사</a></>}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="bubble assistant"><div className="bubble-content typing">데이터 조회 중…</div></div>}
        <div ref={endRef} />
      </div>
      <div className="chat-input">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="질문을 입력하세요 (예: '삼성전자 vs SK하이닉스 비교')"
          disabled={loading}
        />
        <button onClick={() => send()} disabled={loading}>전송</button>
      </div>
    </div>
  )
}
