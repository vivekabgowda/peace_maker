import { apiFetch } from '@/lib/api/client';

export interface SharpeStats {
  sharpe: number;
  skew: number;
  kurtosis: number;
  n_obs: number;
  stdev: number;
  psr: number;
  dsr: number;
  n_trials: number;
}

export interface ConfidenceInterval {
  point: number;
  low: number;
  high: number;
  level: number;
  significant: boolean;
}

export interface WalkForward {
  n_trades: number;
  gross_expectancy_r: number;
  net_expectancy_r: number;
  net_profit_factor: number;
  cost_drag_r: number;
  roundtrip_cost_bps: number;
  expectancy_ci: ConfidenceInterval;
  sharpe: SharpeStats;
  folds: { index: number; n_trades: number; net_expectancy_r: number; win_rate: number }[];
  oos_consistency: number;
  verdict_significant: boolean;
}

export interface StrategyValidation {
  strategy: string;
  trades: number;
  is_proven: boolean;
  walk_forward: WalkForward;
  p_value: number;
  significant_after_correction: boolean;
  q_value: number;
}

export interface ValidationRun {
  id: number;
  created_at: string;
  kind?: string;
  roundtrip_cost_bps: number;
  segment: string;
  reference_notional: number;
  strategies_evaluated: number;
  survivors: string[];
  strategies: StrategyValidation[];
}

export interface ValidationRunSummary {
  id: number;
  kind: string;
  created_at: string;
  strategies_evaluated: number | null;
  survivors: string[];
}

export interface MonteCarlo {
  strategy: string;
  roundtrip_cost_bps: number;
  units: string;
  n_trades: number;
  simulations: number;
  method: string;
  final_return: { p05: number; p50: number; p95: number; mean: number };
  max_drawdown: { p50: number; p95: number; worst: number };
  prob_loss: number;
}

export const listValidationRuns = () =>
  apiFetch<{ runs: ValidationRunSummary[] }>('/validation/runs', { auth: true }).then(
    (r) => r.runs,
  );

export const getValidationRun = (id: number) =>
  apiFetch<ValidationRun>(`/validation/runs/${id}`, { auth: true });

export const runValidation = (history = 400, folds = 4) =>
  apiFetch<ValidationRun>(`/validation/run?history=${history}&folds=${folds}`, {
    method: 'POST',
    auth: true,
    timeoutMs: 120000,
  });

export const runMonteCarlo = (strategy: string, method: 'resample' | 'shuffle' = 'resample') =>
  apiFetch<MonteCarlo>(
    `/validation/monte-carlo?strategy=${encodeURIComponent(strategy)}&method=${method}`,
    { method: 'POST', auth: true, timeoutMs: 120000 },
  );
