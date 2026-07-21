import { apiFetch } from '@/lib/api/client';

export interface PerformanceMetrics {
  total_trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  win_rate: number;
  gross_profit: number;
  gross_loss: number;
  net_pnl: number;
  profit_factor: number;
  expectancy: number;
  expectancy_r: number;
  avg_win: number;
  avg_loss: number;
  payoff_ratio: number;
  best_trade: number;
  worst_trade: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  sharpe: number;
  avg_holding_seconds: number;
  return_pct: number;
  starting_equity: number;
  ending_equity: number;
  equity_curve: number[];
}

export interface EquityCurve {
  starting_equity: number;
  ending_equity: number;
  points: number[];
}

export interface StrategyBreakdown {
  strategies: Record<string, PerformanceMetrics>;
}

export const getAnalyticsSummary = () =>
  apiFetch<PerformanceMetrics>('/analytics/summary', { auth: true });

export const getEquityCurve = () =>
  apiFetch<EquityCurve>('/analytics/equity-curve', { auth: true });

export const getByStrategy = () =>
  apiFetch<StrategyBreakdown>('/analytics/by-strategy', { auth: true });
