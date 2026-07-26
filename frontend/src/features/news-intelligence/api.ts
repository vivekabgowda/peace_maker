import { apiFetch } from '@/lib/api/client';

export interface NewsBucket {
  trades: number;
  win_rate: number;
  avg_r: number;
}

export interface NewsPerformance {
  trades_with_news: number;
  accuracy: number;
  avg_r_after_positive_news: number;
  avg_r_after_negative_news: number;
  positive_news: NewsBucket;
  negative_news: NewsBucket;
  by_sentiment: Record<string, NewsBucket>;
}

export interface NewsEvent {
  event: string;
  event_label: string;
  severity: string;
  headline: string;
  source: string;
  reliability: number;
  session: string;
  impact_timing: string;
}

export interface NewsAssessment {
  symbol: string;
  news_score: number;
  sentiment: string;
  confidence_pct: number;
  source_reliability: number;
  verification_status: string;
  impact_horizon_label: string;
  impact_timing_label: string;
  dominant_session: string | null;
  primary_reasons: string[];
  risk_factors: string[];
  headlines: string[];
  events: NewsEvent[];
  article_count: number;
}

export interface JournalNews {
  news_score: number;
  sentiment: string;
  verification_status: string;
  supported: boolean | null;
}

export const getNewsPerformance = () =>
  apiFetch<NewsPerformance>('/analytics/news-performance', { auth: true });

export const getNewsJournal = () =>
  apiFetch<{ data: Record<string, JournalNews> }>('/analytics/news-journal', {
    auth: true,
  }).then((r) => r.data);

export const getNewsAssessment = (symbol: string) =>
  apiFetch<NewsAssessment>(`/news-intelligence/${encodeURIComponent(symbol)}`, { auth: true });
