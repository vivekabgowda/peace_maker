import { getInstruments, type Instrument } from '@/features/charts/api';
import { getOpportunities, type Opportunity, type OpportunityBook } from '@/features/scanner/api';
import { apiFetch } from '@/lib/api/client';

/** The CIO's final verdict for one deliberation. */
export interface CommitteeDecision {
  symbol: string;
  recommendation: 'strong_buy' | 'buy' | 'hold' | 'sell' | 'strong_sell' | 'reject';
  direction: 'long' | 'short' | 'none';
  conviction: number; // 0..1
  consensus: number; // -1..1 signed weighted vote
  confidence_breakdown: Record<string, number>; // per-agent signed contribution
  bull_case: string[];
  bear_case: string[];
  invalidation: string;
  risk: Record<string, number>;
  position: Record<string, number>;
  expected_holding: string;
  alternatives: { symbol: string; strategy: string; composite: number; rejection_reason: string }[];
  rationale: string;
  vetoed: boolean;
  veto_reasons: string[];
}

export interface AgentFinding {
  polarity: 'bull' | 'bear' | 'neutral';
  citation: string;
  detail: string;
  weight: number;
}

export interface AgentReport {
  role: string;
  stance: string;
  confidence: number;
  headline: string;
  veto: boolean;
  veto_reason: string | null;
  findings: AgentFinding[];
  metrics: Record<string, number>;
}

export interface CommitteeReview {
  convened: boolean;
  reason?: string;
  regime?: { primary: string; is_hostile: boolean };
  decision?: CommitteeDecision;
  reports?: AgentReport[];
  elapsed_ms?: number;
}

/** Convene the AI committee on a specific symbol from the current book. */
export const getCommitteeReview = (symbol: string) =>
  apiFetch<CommitteeReview>(`/committee/review?symbol=${encodeURIComponent(symbol)}`, {
    auth: true,
  });

// Re-exported so the view imports from one place.
export { getInstruments, getOpportunities };
export type { Instrument, Opportunity, OpportunityBook };
