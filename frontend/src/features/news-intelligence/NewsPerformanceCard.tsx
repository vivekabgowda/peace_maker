'use client';

import { useQuery } from '@tanstack/react-query';

import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/utils';

import { getNewsPerformance } from './api';

function sentimentLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function rTone(r: number): string {
  return r > 0 ? 'text-gain' : r < 0 ? 'text-loss' : 'text-content-muted';
}

export function NewsPerformanceCard() {
  const query = useQuery({
    queryKey: ['news-performance'],
    queryFn: getNewsPerformance,
    refetchInterval: 30000,
  });

  const data = query.data;
  const sentiments = Object.entries(data?.by_sentiment ?? {});

  return (
    <Card className="p-0">
      <div className="border-b border-surface-border px-5 py-4">
        <h2 className="text-sm font-semibold text-content">News Intelligence — calibration</h2>
        <p className="mt-0.5 text-xs text-content-muted">
          Did the news that preceded entry predict the move? (advisory, read-only)
        </p>
      </div>

      {query.isLoading ? (
        <p className="px-5 py-4 text-sm text-content-muted">Loading news performance…</p>
      ) : !data || data.trades_with_news === 0 ? (
        <p className="px-5 py-4 text-sm text-content-muted">
          No closed trades with a preceding news assessment yet. Once trades close against symbols
          that had trusted news, accuracy and return-after-news appear here.
        </p>
      ) : (
        <div className="space-y-4 px-5 py-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div>
              <div className="text-xs text-content-faint">Directional accuracy</div>
              <div className="tabular mt-0.5 text-lg font-semibold text-content">
                {(data.accuracy * 100).toFixed(0)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-content-faint">Trades with news</div>
              <div className="tabular mt-0.5 text-lg font-semibold text-content">
                {data.trades_with_news}
              </div>
            </div>
            <div>
              <div className="text-xs text-content-faint">Avg R after +ve news</div>
              <div
                className={cn(
                  'tabular mt-0.5 text-lg font-semibold',
                  rTone(data.avg_r_after_positive_news),
                )}
              >
                {data.avg_r_after_positive_news.toFixed(2)}R
              </div>
            </div>
            <div>
              <div className="text-xs text-content-faint">Avg R after -ve news</div>
              <div
                className={cn(
                  'tabular mt-0.5 text-lg font-semibold',
                  rTone(data.avg_r_after_negative_news),
                )}
              >
                {data.avg_r_after_negative_news.toFixed(2)}R
              </div>
            </div>
          </div>

          {sentiments.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-sm">
                <thead>
                  <tr className="border-b border-surface-border text-left text-xs text-content-muted">
                    <th className="py-2 font-medium">Sentiment</th>
                    <th className="py-2 text-right font-medium">Trades</th>
                    <th className="py-2 text-right font-medium">Win%</th>
                    <th className="py-2 text-right font-medium">Avg R</th>
                  </tr>
                </thead>
                <tbody>
                  {sentiments.map(([key, b]) => (
                    <tr key={key} className="border-b border-surface-border/50 last:border-0">
                      <td className="py-2 font-medium text-content">{sentimentLabel(key)}</td>
                      <td className="tabular py-2 text-right text-content-muted">{b.trades}</td>
                      <td className="tabular py-2 text-right text-content-muted">
                        {(b.win_rate * 100).toFixed(0)}%
                      </td>
                      <td className={cn('tabular py-2 text-right font-medium', rTone(b.avg_r))}>
                        {b.avg_r.toFixed(2)}R
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}
