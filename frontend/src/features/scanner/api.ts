import { apiFetch } from '@/lib/api/client';

export interface Opportunity {
  rank: number;
  symbol: string;
  strategy: string;
  strategy_name: string;
  direction: 'long' | 'short' | 'none';
  entry: number;
  stop: number;
  targets: number[];
  risk_reward: number;
  expected_holding: string;
  composite: number;
  confidence: number;
  tags: string[];
}

export interface Regime {
  primary: string;
  overlays: string[];
  confidence: number;
  index_trend: string;
}

export interface OpportunityBook {
  generated_at: string;
  regime: Regime;
  no_trade: boolean;
  no_trade_reason: string | null;
  universe_size: number;
  candidates: number;
  rejected: number;
  top: Opportunity[];
  warnings: string[];
}

export const getOpportunities = (top = 20) =>
  apiFetch<OpportunityBook>(`/alpha/opportunities?top=${top}`, { auth: true });
