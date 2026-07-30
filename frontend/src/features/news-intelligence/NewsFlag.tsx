import { cn } from '@/lib/utils';

import type { JournalNews } from './api';

/** Journal cell: the news that preceded entry and whether it supported the move. */
export function NewsFlag({ info }: { info?: JournalNews }) {
  if (!info) {
    return <span className="text-xs text-content-faint">—</span>;
  }
  const { news_score: score, supported } = info;
  const scoreTone = score > 10 ? 'text-gain' : score < -10 ? 'text-loss' : 'text-content-muted';
  const label = supported === true ? 'supported' : supported === false ? 'contradicted' : 'neutral';
  const labelTone =
    supported === true ? 'text-gain' : supported === false ? 'text-loss' : 'text-content-faint';
  const title = `News at entry: ${info.sentiment.replace(/_/g, ' ')} (${score >= 0 ? '+' : ''}${score}), ${info.verification_status} — ${label} the trade`;

  return (
    <span className="inline-flex items-center gap-1.5" title={title}>
      <span className={cn('tabular text-xs font-semibold', scoreTone)}>
        {score >= 0 ? `+${score}` : score}
      </span>
      <span className={cn('text-[10px] uppercase tracking-wide', labelTone)}>{label}</span>
    </span>
  );
}
