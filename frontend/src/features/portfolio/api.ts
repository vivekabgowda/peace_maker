import {
  getAnalyticsSummary,
  getEquityCurve,
  type EquityCurve,
  type PerformanceMetrics,
} from '@/features/analytics/api';
import { apiFetch } from '@/lib/api/client';

/** Paper account snapshot (cash, equity, realized/unrealized P&L). */
export interface PaperAccount {
  account_id: number;
  starting_cash: number;
  cash: number;
  realized_pnl: number;
  unrealized_pnl: number;
  fees_paid: number;
  equity: number;
  return_pct: number;
  open_positions: number;
}

/** One open paper position. `mark_price`/`unrealized_pnl` are present when a
 *  live price is available; otherwise the position is shown at entry. */
export interface PaperPosition {
  id: number;
  symbol: string;
  side: 'buy' | 'sell';
  direction: 'long' | 'short';
  quantity: number;
  entry_price: number;
  mark_price?: number;
  unrealized_pnl?: number;
  stop: number | null;
  target: number | null;
  strategy_key: string | null;
  source: string;
}

export interface DailyReturn {
  date: string;
  net_pnl: number;
}

export const getAccount = () => apiFetch<PaperAccount>('/paper/account', { auth: true });

export const getPositions = () =>
  apiFetch<{ count: number; positions: PaperPosition[] }>('/paper/positions', { auth: true });

export const getDailyReturns = (days = 30) =>
  apiFetch<{ days: DailyReturn[] }>(`/analytics/daily?days=${days}`, { auth: true });

// Re-exported so the Portfolio view has a single import surface.
export { getAnalyticsSummary, getEquityCurve };
export type { EquityCurve, PerformanceMetrics };
