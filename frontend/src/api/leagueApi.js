import axiosClient from './axiosClient'

export const getActiveLeagues = () =>
  axiosClient.get('/league/')

export const getAllLeagues = () =>
  axiosClient.get('/league/all')

export const getMyLeagues = () =>
  axiosClient.get('/league/my')

export const getMyBadges = () =>
  axiosClient.get('/league/badges/me')

export const getLeagueLeaderboard = (leagueId) =>
  axiosClient.get(`/league/${leagueId}/leaderboard`)

export const joinLeague = (leagueId) =>
  axiosClient.post(`/league/${leagueId}/join`)

export const createLeague = (payload) =>
  axiosClient.post('/league/', payload)

export const finalizeLeague = (leagueId) =>
  axiosClient.post(`/league/${leagueId}/finalize`)
