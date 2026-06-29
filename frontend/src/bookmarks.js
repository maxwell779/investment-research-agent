// 북마크(즐겨찾기) — 종목·섹터. 브라우저 localStorage에만 저장.
const SK = 'bm_stocks_v1', SECK = 'bm_sectors_v1'
const get = (k) => { try { return JSON.parse(localStorage.getItem(k)) || [] } catch { return [] } }
const set = (k, v) => localStorage.setItem(k, JSON.stringify(v))

export const getStocks = () => get(SK)
export const getSectors = () => get(SECK)
export const isStock = (tk) => get(SK).some(x => x.ticker === tk)
export const isSector = (s) => get(SECK).includes(s)

export function toggleStock(ticker, name) {
  const a = get(SK); const i = a.findIndex(x => x.ticker === ticker)
  if (i >= 0) a.splice(i, 1); else a.push({ ticker, name })
  set(SK, a); return a
}
export function toggleSector(s) {
  const a = get(SECK); const i = a.indexOf(s)
  if (i >= 0) a.splice(i, 1); else a.push(s)
  set(SECK, a); return a
}
