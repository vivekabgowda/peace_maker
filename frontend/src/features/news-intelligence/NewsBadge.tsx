'use client';

import { useQuery } from '@tanstack/react-query';

import { cn } from '@/lib/utils';

import { getNewsAssessment } from './api';

/** Compact per-symbol news score chip for tables (Scanner, watchlists). */
export function NewsBadge({ symbol }: { symbol: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['news-assessment', symbol],
    queryFn: () => getNewsAssessment(symbol),
    staleTime: 60000,
    refetchInterval: 60000,
  });

  if (isLoading) {
    return <span className="text-xs text-content-faint">…</span>;
  }
  if (!data || data.article_count === 0) {
    return <span className="text-xs text-content-faint">—</span>;
  }

  const score = data.news_score;
  const tone = score > 10 ? 'text-gain' : score < -10 ? 'text-loss' : 'text-content-muted';
  const tooltip = [
    `${data.sentiment.replace(/_/g, ' ')} · ${data.confidence_pct}% conf · ${data.verification_status}`,
    ...data.primary_reasons,
  ].join('\n');

  return (
    <span className="inline-flex items-center gap-1" title={tooltip}>
      <span className={cn('tabular text-xs font-semibold', tone)}>
        {score > 0 ? `+${score}` : score}
      </span>
      {data.verification_status === 'verified' ? (
        <span className="text-[10px] text-gain" aria-label="verified">
          ✓
        </span>
      ) : data.verification_status === 'pending' ? (
        <span className="text-[10px] text-content-faint" aria-label="pending verification">
          ?
        </span>
      ) : null}
    </span>
  );
}
