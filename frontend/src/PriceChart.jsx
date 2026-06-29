import { useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'

// 캔들 + 거래량 + (옵션)MA20/60 + RSI(14) 서브차트. 한국 관례(상승=빨강, 하락=파랑).
export default function PriceChart({ candles, showMA = true, dark = false }) {
  const ref = useRef(null)
  const rsiRef = useRef(null)

  useEffect(() => {
    if (!ref.current || !candles || candles.length === 0) return
    const T = dark
      ? { bg: '#0f172a', text: '#cbd5e1', grid: '#1e293b', border: '#334155' }
      : { bg: '#ffffff', text: '#475569', grid: '#f1f5f9', border: '#e2e8f0' }
    const common = {
      layout: { background: { color: T.bg }, textColor: T.text, fontFamily: 'inherit' },
      grid: { vertLines: { color: T.grid }, horzLines: { color: T.grid } },
      rightPriceScale: { borderColor: T.border },
      timeScale: { borderColor: T.border, timeVisible: false },
      crosshair: { mode: 0 },
    }
    const chart = createChart(ref.current, { height: 360, width: ref.current.clientWidth, ...common })
    const candle = chart.addCandlestickSeries({
      upColor: '#f04452', downColor: '#3182f6', borderVisible: false,
      wickUpColor: '#f04452', wickDownColor: '#3182f6',
    })
    candle.setData(candles.map(c => ({ time: c.t, open: c.o, high: c.h, low: c.l, close: c.c })))
    if (showMA) {
      const ma20 = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false })
      ma20.setData(candles.filter(c => c.ma20 != null).map(c => ({ time: c.t, value: c.ma20 })))
      const ma60 = chart.addLineSeries({ color: '#8b5cf6', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false })
      ma60.setData(candles.filter(c => c.ma60 != null).map(c => ({ time: c.t, value: c.ma60 })))
    }
    const vol = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '' })
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })
    vol.setData(candles.map(c => ({
      time: c.t, value: c.v,
      color: c.c >= c.o ? (dark ? '#7f1d2e' : '#fecaca') : (dark ? '#1e3a5f' : '#bfdbfe'),
    })))
    chart.timeScale().fitContent()

    let rsiChart
    const rsiData = candles.filter(c => c.rsi != null).map(c => ({ time: c.t, value: c.rsi }))
    if (rsiRef.current && rsiData.length) {
      rsiChart = createChart(rsiRef.current, { height: 110, width: rsiRef.current.clientWidth, ...common })
      const rs = rsiChart.addLineSeries({ color: '#0ea5a4', lineWidth: 1.5, priceLineVisible: false })
      rs.setData(rsiData)
      rs.createPriceLine({ price: 70, color: '#f04452', lineStyle: 2, lineWidth: 1, title: '70' })
      rs.createPriceLine({ price: 30, color: '#3182f6', lineStyle: 2, lineWidth: 1, title: '30' })
      rsiChart.timeScale().fitContent()
    }

    const onResize = () => {
      chart.applyOptions({ width: ref.current.clientWidth })
      if (rsiChart && rsiRef.current) rsiChart.applyOptions({ width: rsiRef.current.clientWidth })
    }
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.remove(); if (rsiChart) rsiChart.remove() }
  }, [candles, showMA, dark])

  return (
    <div>
      <div ref={ref} />
      <div className="legend">
        <span><i style={{ background: '#f59e0b' }} />MA20</span>
        <span><i style={{ background: '#8b5cf6' }} />MA60</span>
        <span className="muted">상승=빨강 · 하락=파랑 (한국 관례)</span>
      </div>
      <div className="rsi-label muted">RSI(14) · 70 과매수 / 30 과매도</div>
      <div ref={rsiRef} />
    </div>
  )
}
