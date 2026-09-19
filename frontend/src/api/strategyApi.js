import axiosClient from './axiosClient'

export const createStrategy = (payload) =>
  axiosClient.post('/strategies/', payload)

export const getStrategies = () =>
  axiosClient.get('/strategies/')

export const getStrategy = (id) =>
  axiosClient.get(`/strategies/${id}`)

export const updateStrategy = (id, payload) =>
  axiosClient.patch(`/strategies/${id}`, payload)

export const activateStrategy = (id) =>
  axiosClient.post(`/strategies/${id}/activate`)

export const pauseStrategy = (id) =>
  axiosClient.post(`/strategies/${id}/pause`)

export const deleteStrategy = (id) =>
  axiosClient.delete(`/strategies/${id}`)

export const getStrategyTemplates = () =>
  axiosClient.get('/strategies/templates')