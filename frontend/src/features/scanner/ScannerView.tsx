'use client';

import { useQuery } from '@tanstack/react-query';

import { Card } from '@/components/ui/Card';
import { getOpportunities, type Opportunity, type Regime } from '@/features/scanner/api';
import { cn } from '@/lib/utils';

function price(value: number): string {
  return value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function RegimeBar({ regime, universe }: { regime: Regime; universe: number }) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-content-muted">
      <span>
        Regime:{' '}
        <span className="font-medium capitalize text-content">
          {regime.primary.replace(/_/g, ' ')}
        </span>
      </span>
      <span>
        Index trend:{' '}
        <span
          className={cn(
            'font-medium capitalize',
            regime.index_trend.includes('up')
              ? 'text-gain'
              : regime.index_trend.includes('down')
                ? 'text-loss'
                : 'text-content',
          )}
        >
          {regime.index_trend.replace(/_/g, ' ')}
        </span>
      </span>
      <span className="tabular">Confidence: {(regime.confidence * 100).toFixed(0)}%</span>
      {regime.overlays.length > 0 ? <span>Overlays: {regime.overlays.join(', ')}</span> : null}
      <span className="tabular">Universe: {universe}</span>
    </div>
  );
}

function ScoreBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-overlay">
        <div
          className={cn(
            'h-full rounded-full',
            pct >= 70 ? 'bg-gain' : pct >= 55 ? 'bg-caution' : 'bg-loss',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="tabular text-xs text-content-muted">{pct.toFixed(0)}</span>
    </div>
  );
}

function OpportunityTable({ rows }: { rows: Opportunity[] }) {
  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[880px] text-sm">
        <thead>
          <tr className="border-b border-surface-border text-left text-xs text-content-muted">
            <th className="px-4 py-3 font-medium">#</th>
            <th className="px-4 py-3 font-medium">Symbol</th>
            <th className="px-4 py-3 font-medium">Strategy</th>
            <th className="px-4 py-3 font-medium">Side</th>
            <th className="px-4 py-3 text-right font-medium">Entry</th>
            <th className="px-4 py-3 text-right font-medium">Stop</th>
            <th className="px-4 py-3 text-right font-medium">Target</th>
            <th className="px-4 py-3 text-right font-medium">R:R</th>
            <th className="px-4 py-3 font-medium">Score</th>
            <th className="px-4 py-3 text-right font-medium">Conf.</th>
            <th className="px-4 py-3 font-medium">Hold</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((o) => (
            <tr
              key={`${o.symbol}-${o.strategy}`}
              className="border-b border-surface-border/50 last:border-0"
            >
              <td className="tabular px-4 py-2.5 text-content-muted">{o.rank}</td>
              <td className="px-4 py-2.5 font-medium text-content">{o.symbol}</td>
              <td className="px-4 py-2.5 text-content-muted">{o.strategy_name}</td>
              <td className="px-4 py-2.5">
                <span className={cn(o.direction === 'long' ? 'text-gain' : 'text-loss')}>
                  {o.direction}
                </span>
              </td>
              <td className="tabular px-4 py-2.5 text-right text-content-muted">
                {price(o.entry)}
              </td>
              <td className="tabular px-4 py-2.5 text-right text-loss">{price(o.stop)}</td>
              <td className="tabular px-4 py-2.5 text-right text-gain">
                {o.targets.length > 0 ? price(o.targets[0] as number) : '—'}
              </td>
              <td className="tabular px-4 py-2.5 text-right text-content-muted">
                {o.risk_reward.toFixed(2)}
              </td>
              <td className="px-4 py-2.5">
                <ScoreBar value={o.composite} />
              </td>
              <td className="tabular px-4 py-2.5 text-right text-content-muted">
                {(o.confidence * 100).toFixed(0)}%
              </td>
              <td className="px-4 py-2.5 text-content-muted">{o.expected_holding}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function ScannerView() {
  const { data, isLoading, isError, error, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['alpha-opportunities'],
    queryFn: () => getOpportunities(20),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return <Card className="text-sm text-content-muted">Scanning the universe…</Card>;
  }
  if (isError) {
    return (
      <Card className="text-sm text-loss">
        Could not run the scan: {error instanceof Error ? error.message : 'unknown error'}
      </Card>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <RegimeBar regime={data.regime} universe={data.universe_size} />
        <span className="text-xs text-content-faint">
          {isFetching ? 'Refreshing…' : `Updated ${new Date(dataUpdatedAt).toLocaleTimeString()}`}
        </span>
      </div>

      {data.warnings.length > 0 ? (
        <Card className="border-caution/30 bg-caution/5 text-xs text-caution">
          {data.warnings.map((w) => (
            <div key={w}>⚠ {w}</div>
          ))}
        </Card>
      ) : null}

      {data.no_trade ? (
        <Card className="border-caution/30 bg-caution/5">
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-caution/40 bg-caution/10 px-2 py-0.5 text-xs font-semibold text-caution">
              NO-TRADE
            </span>
            <span className="text-sm font-medium text-content">Standing aside</span>
          </div>
          <p className="mt-2 text-sm text-content-muted">
            {data.no_trade_reason ?? 'No candidate cleared the quality bar.'}
          </p>
          <p className="mt-1 text-xs text-content-faint">
            Scanned {data.universe_size} instruments · {data.rejected} rejected. The engine never
            forces trades — this is a real verdict, not an empty page.
          </p>
        </Card>
      ) : data.top.length === 0 ? (
        <Card className="text-sm text-content-muted">
          <p className="font-medium text-content">No qualifying setups right now.</p>
          <p className="mt-1">
            The scanner ran across {data.universe_size} instruments and nothing cleared the quality
            bar. This refreshes automatically as new candles form.
          </p>
        </Card>
      ) : (
        <OpportunityTable rows={data.top} />
      )}
    </div>
  );
}
