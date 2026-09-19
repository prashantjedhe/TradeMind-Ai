import axiosClient from './axiosClient'

export const createOrder = (payload) =>
  axiosClient.post('/orders/', payload)

export const getOrders = () =>
  axiosClient.get('/orders/')

export const getPortfolioSummary = () =>
  axiosClient.get('/portfolio/summary')
