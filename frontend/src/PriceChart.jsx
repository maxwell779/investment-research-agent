import { useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'

// 캔들 + 이동평균(20/60) + 거래량. 한국 관례(상승=빨강, 하락=파랑).
export default function PriceChart({ candles }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!ref.current || !candles || candles.length === 0) return
    const el = ref.current
    const chart = createChart(el, {
      height: 380,
      width: el.clientWidth,
      layout: { background: { color: '#ffffff' }, textColor: '#475569', fontFamily: 'inherit' },
      grid: { vertLines: { color: '#f1f5f9' }, horzLines: { color: '#f1f5f9' } },
      rightPriceScale: { borderColor: '#e2e8f0' },
      timeScale: { borderColor: '#e2e8f0', timeVisible: false },
      crosshair: { mode: 0 },
    })
    const candle = chart.addCandlestickSeries({
      upColor: '#ef4444', downColor: '#3b82f6', borderVisible: false,
      wickUpColor: '#ef4444', wickDownColor: '#3b82f6',
    })
    candle.setData(candles.map(c => ({ time: c.t, open: c.o, high: c.h, low: c.l, close: c.c })))

    const ma20 = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false })
    ma20.setData(candles.filter(c => c.ma20 != null).map(c => ({ time: c.t, value: c.ma20 })))
    const ma60 = chart.addLineSeries({ color: '#8b5cf6', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false })
    ma60.setData(candles.filter(c => c.ma60 != null).map(c => ({ time: c.t, value: c.ma60 })))

    const vol = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '' })
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    vol.setData(candles.map(c => ({ time: c.t, value: c.v, color: c.c >= c.o ? '#fecaca' : '#bfdbfe' })))

    chart.timeScale().fitContent()
    const onResize = () => chart.applyOptions({ width: el.clientWidth })
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.remove() }
  }, [candles])

  return (
    <div>
      <div ref={ref} />
      <div className="legend">
        <span><i style={{ background: '#f59e0b' }} />MA20</span>
        <span><i style={{ background: '#8b5cf6' }} />MA60</span>
        <span className="muted">상승=빨강 · 하락=파랑 (한국 관례)</span>
      </div>
    </div>
  )
}
