import { apiFetch } from '@/lib/api/client';

export interface JournalEntry {
  id: number;
  symbol: string;
  direction: 'long' | 'short';
  quantity: number;
  strategy_key: string | null;
  source: string;
  entry_price: number;
  entry_ts: string;
  exit_price: number;
  exit_ts: string;
  exit_reason: string | null;
  gross_pnl: number;
  fees: number;
  net_pnl: number;
  r_multiple: number;
  holding_seconds: number;
  outcome: 'win' | 'loss' | 'breakeven';
  notes: string | null;
  tags: string[];
}

export interface JournalResponse {
  count: number;
  entries: JournalEntry[];
}

export const getJournalEntries = (limit = 200) =>
  apiFetch<JournalResponse>(`/journal/entries?limit=${limit}`, { auth: true });
