import { apiFetch } from '@/lib/api/client';

export interface Quote {
  symbol: string;
  ltp: number | string;
  change_pct: number | null;
  volume?: number;
  instrument_type?: string;
}

export interface Breadth {
  advances: number;
  declines: number;
  unchanged: number;
}

export interface SectorStrength {
  sector: string;
  avg_change_pct: number;
  count: number;
}

export interface MarketStatus {
  status: string;
  freshness_seconds: Record<string, number | null>;
}

export const getIndices = () =>
  apiFetch<{ data: Quote[] }>('/market/indices', { auth: true }).then((r) => r.data);

export const getQuotes = () =>
  apiFetch<{ data: Quote[] }>('/market/quotes', { auth: true }).then((r) => r.data);

export const getMarketStatus = () => apiFetch<MarketStatus>('/market/status', { auth: true });

export const getBreadth = () =>
  apiFetch<{ breadth: Breadth; sectors: SectorStrength[] }>('/market/breadth', { auth: true });
