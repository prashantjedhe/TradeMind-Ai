import axiosClient from './axiosClient'

export const createOrder = (payload) =>
  axiosClient.post('/orders/', payload)

export const manualExit = (ticker) =>
  axiosClient.post('/orders/manual-exit', { ticker })

export const getOrders = () =>
  axiosClient.get('/orders/')

export const getTradeProposals = () =>
  axiosClient.get('/orders/proposals')

export const confirmTradeProposal = (proposalId) =>
  axiosClient.post(`/orders/proposals/${proposalId}/confirm`)

export const getPortfolioSummary = () =>
  axiosClient.get('/portfolio/summary')
