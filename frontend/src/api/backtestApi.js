import axiosClient from './axiosClient'

export const runStrategyBacktest = (strategy, years = 2) =>
  axiosClient.post('/backtest/run', null, {
    params: {
      strategy_id: strategy.id,
      ticker: strategy.ticker,
      timeframe: strategy.timeframe,
      years,
    },
  })

export const runDraftStrategyBacktest = (strategy, years = 2) =>
  axiosClient.post('/backtest/run', {
    ticker: strategy.ticker,
    timeframe: strategy.timeframe,
    years,
    root_condition: strategy.root_condition,
    action: strategy.action,
  })

export const runStrategyWalkForward = (strategy) =>
  axiosClient.post('/backtest/walk-forward', null, {
    params: {
      strategy_id: strategy.id,
      ticker: strategy.ticker,
      timeframe: strategy.timeframe,
    },
  })
