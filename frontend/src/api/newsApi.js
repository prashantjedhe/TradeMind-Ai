import axiosClient from './axiosClient'

export const getLatestNews = (ticker, limit = 10) =>
  axiosClient.get('/news/latest', { params: { ticker, limit } })

export const getNewsSentiment = (ticker, window = '1h') =>
  axiosClient.get('/news/sentiment', { params: { ticker, window } })

export const getNewsSignal = (ticker) =>
  axiosClient.get('/news/signal', { params: { ticker } })

export const getNewsEvaluation = (ticker, days = 30) =>
  axiosClient.get('/news/evaluation', { params: { ticker, days } })

export const getMarketBrief = () =>
  axiosClient.get('/news/market-brief')

export const confirmMarketTrade = (proposal_id, signal_id) =>
  axiosClient.post('/news/market-brief/confirm', { proposal_id, signal_id })

export const getNewsAlerts = () =>
  axiosClient.get('/news/alerts')

export const postAdvisor = (
  strategy_id = null,
  note = '',
  ticker = null,
  headline = null,
  sector = null,
  sentiment_score = null,
  sentiment_label = null,
  article_url = null,
) => axiosClient.post('/news/advisor', {
  strategy_id,
  note,
  ticker,
  headline,
  sector,
  sentiment_score,
  sentiment_label,
  article_url,
})

export const postJournal = (strategy_id = null, days = 7) =>
  axiosClient.post('/news/journal', { strategy_id, days })

export const getJournal = () =>
  axiosClient.get('/news/journal')

export const exitOnNews = (ticker) =>
  axiosClient.post('/orders/exit-on-news', { ticker })
