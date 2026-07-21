'use client';

import { useQuery } from '@tanstack/react-query';

import { Card } from '@/components/ui/Card';
import { getJournalEntries, type JournalEntry } from '@/features/journal/api';
import { cn, formatINR } from '@/lib/utils';

function holdingLabel(seconds: number): string {
  if (seconds <= 0) return '—';
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

function price(value: number): string {
  return value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function OutcomeBadge({ outcome }: { outcome: JournalEntry['outcome'] }) {
  const styles: Record<JournalEntry['outcome'], string> = {
    win: 'border-gain/30 bg-gain/10 text-gain',
    loss: 'border-loss/30 bg-loss/10 text-loss',
    breakeven: 'border-surface-border bg-surface-overlay text-content-muted',
  };
  return (
    <span className={cn('rounded-full border px-2 py-0.5 text-xs font-medium', styles[outcome])}>
      {outcome}
    </span>
  );
}

function StatTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'gain' | 'loss';
}) {
  return (
    <Card>
      <div className="text-xs text-content-faint">{label}</div>
      <div
        className={cn(
          'tabular mt-1 text-lg font-semibold',
          tone === 'gain' && 'text-gain',
          tone === 'loss' && 'text-loss',
        )}
      >
        {value}
      </div>
    </Card>
  );
}

export function JournalView() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['journal-entries'],
    queryFn: () => getJournalEntries(200),
    refetchInterval: 20000,
  });

  if (isLoading) {
    return <Card className="text-sm text-content-muted">Loading trade journal…</Card>;
  }
  if (isError) {
    return (
      <Card className="text-sm text-loss">
        Could not load the journal: {error instanceof Error ? error.message : 'unknown error'}
      </Card>
    );
  }

  const entries = data?.entries ?? [];

  if (entries.length === 0) {
    return (
      <Card className="text-sm text-content-muted">
        <p className="font-medium text-content">No closed trades yet.</p>
        <p className="mt-1">
          The journal records every closed paper trade. Submit a paper order and close it (or let a
          stop/target hit) and it will appear here — win, loss, R-multiple and all.
        </p>
      </Card>
    );
  }

  const wins = entries.filter((e) => e.outcome === 'win').length;
  const netPnl = entries.reduce((sum, e) => sum + e.net_pnl, 0);
  const avgR = entries.reduce((sum, e) => sum + e.r_multiple, 0) / entries.length;
  const winRate = (wins / entries.length) * 100;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Closed trades" value={String(entries.length)} />
        <StatTile label="Win rate" value={`${winRate.toFixed(0)}%`} />
        <StatTile
          label="Net P&L"
          value={formatINR(netPnl)}
          tone={netPnl > 0 ? 'gain' : netPnl < 0 ? 'loss' : undefined}
        />
        <StatTile
          label="Avg R"
          value={avgR.toFixed(2)}
          tone={avgR > 0 ? 'gain' : avgR < 0 ? 'loss' : undefined}
        />
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="border-b border-surface-border text-left text-xs text-content-muted">
              <th className="px-4 py-3 font-medium">Symbol</th>
              <th className="px-4 py-3 font-medium">Side</th>
              <th className="px-4 py-3 text-right font-medium">Qty</th>
              <th className="px-4 py-3 text-right font-medium">Entry</th>
              <th className="px-4 py-3 text-right font-medium">Exit</th>
              <th className="px-4 py-3 text-right font-medium">Net P&L</th>
              <th className="px-4 py-3 text-right font-medium">R</th>
              <th className="px-4 py-3 font-medium">Outcome</th>
              <th className="px-4 py-3 font-medium">Exit</th>
              <th className="px-4 py-3 text-right font-medium">Held</th>
              <th className="px-4 py-3 font-medium">Strategy</th>
              <th className="px-4 py-3 font-medium">Closed</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-surface-border/50 last:border-0">
                <td className="px-4 py-2.5 font-medium text-content">{e.symbol}</td>
                <td className="px-4 py-2.5">
                  <span className={cn(e.direction === 'long' ? 'text-gain' : 'text-loss')}>
                    {e.direction}
                  </span>
                </td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">{e.quantity}</td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {price(e.entry_price)}
                </td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {price(e.exit_price)}
                </td>
                <td
                  className={cn(
                    'tabular px-4 py-2.5 text-right font-medium',
                    e.net_pnl > 0
                      ? 'text-gain'
                      : e.net_pnl < 0
                        ? 'text-loss'
                        : 'text-content-muted',
                  )}
                >
                  {formatINR(e.net_pnl)}
                </td>
                <td
                  className={cn(
                    'tabular px-4 py-2.5 text-right',
                    e.r_multiple > 0
                      ? 'text-gain'
                      : e.r_multiple < 0
                        ? 'text-loss'
                        : 'text-content-muted',
                  )}
                >
                  {e.r_multiple.toFixed(2)}
                </td>
                <td className="px-4 py-2.5">
                  <OutcomeBadge outcome={e.outcome} />
                </td>
                <td className="px-4 py-2.5 text-content-muted">{e.exit_reason ?? '—'}</td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {holdingLabel(e.holding_seconds)}
                </td>
                <td className="px-4 py-2.5 text-content-muted">{e.strategy_key ?? '—'}</td>
                <td className="px-4 py-2.5 text-content-muted">
                  {new Date(e.exit_ts).toLocaleString('en-IN', {
                    day: '2-digit',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
