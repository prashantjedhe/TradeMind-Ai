import axiosClient from './axiosClient'

export const getWatchlist = () =>
  axiosClient.get('/market/watchlist')

export const getMarketPrices = () =>
  axiosClient.get('/market/prices')

export const getFnoUniverse = () =>
  axiosClient.get('/market/fno/universe')

export const getFnoChain = (underlying, expiry) =>
  axiosClient.get('/market/fno/chain', { params: { underlying, expiry } })

export const getFnoQuote = (symbol) =>
  axiosClient.get('/market/fno/quote', { params: { symbol } })
