import axiosClient from './axiosClient'

export const registerUser = (payload) =>
  axiosClient.post('/auth/register', payload)

export const loginUser = (payload) =>
  axiosClient.post('/auth/login', payload)

export const getCurrentUser = () =>
  axiosClient.get('/auth/me')

export const logoutUser = () =>
  axiosClient.post('/auth/logout')
