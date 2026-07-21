import { apiFetch } from '@/lib/api/client';
import type { JournalEntry } from '@/features/journal/api';

export interface Candle {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Instrument {
  id: number;
  symbol: string;
  exchange: string;
  instrument_type: string;
  sector: string | null;
  in_fno: boolean;
}

export const getInstruments = () =>
  apiFetch<{ data: Instrument[] }>('/market/instruments', { auth: true }).then((r) => r.data);

export const getCandles = (symbol: string, tf: string, limit = 500) =>
  apiFetch<{ data: Candle[] }>(
    `/market/candles/${encodeURIComponent(symbol)}?tf=${tf}&limit=${limit}`,
    { auth: true },
  ).then((r) => r.data);

/** Closed paper trades for one symbol — used to draw entry/exit markers. */
export const getSymbolTrades = (symbol: string) =>
  apiFetch<{ count: number; entries: JournalEntry[] }>(
    `/journal/entries?symbol=${encodeURIComponent(symbol)}&limit=500`,
    { auth: true },
  ).then((r) => r.entries);
