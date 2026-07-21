'use client';

import { useQuery } from '@tanstack/react-query';

import { Card, CardHeader } from '@/components/ui/Card';
import {
  getAnalyticsSummary,
  getByStrategy,
  getEquityCurve,
  type EquityCurve,
} from '@/features/analytics/api';
import { cn, formatINR } from '@/lib/utils';

function holdingLabel(seconds: number): string {
  if (seconds <= 0) return '—';
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: 'gain' | 'loss';
}) {
  return (
    <Card>
      <div className="text-xs text-content-faint">{label}</div>
      <div
        className={cn(
          'tabular mt-1 text-lg font-semibold text-content',
          tone === 'gain' && 'text-gain',
          tone === 'loss' && 'text-loss',
        )}
      >
        {value}
      </div>
      {sub ? <div className="tabular mt-0.5 text-xs text-content-muted">{sub}</div> : null}
    </Card>
  );
}

function EquityChart({ curve }: { curve: EquityCurve }) {
  const points = curve.points;
  if (points.length < 2) {
    return (
      <p className="text-sm text-content-muted">Not enough closed trades to plot a curve yet.</p>
    );
  }
  const W = 100;
  const H = 40;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const stepX = W / (points.length - 1);
  const coords = points.map((v, i) => {
    const x = i * stepX;
    const y = H - ((v - min) / span) * H;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  const line = coords.join(' ');
  const area = `0,${H} ${line} ${W},${H}`;
  const up = curve.ending_equity >= curve.starting_equity;

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="h-40 w-full"
        role="img"
        aria-label="Equity curve"
      >
        <polygon points={area} className={up ? 'fill-gain/10' : 'fill-loss/10'} />
        <polyline
          points={line}
          fill="none"
          strokeWidth={0.8}
          vectorEffect="non-scaling-stroke"
          className={up ? 'stroke-gain' : 'stroke-loss'}
        />
      </svg>
      <div className="mt-2 flex justify-between text-xs text-content-muted">
        <span className="tabular">Start {formatINR(curve.starting_equity)}</span>
        <span className={cn('tabular font-medium', up ? 'text-gain' : 'text-loss')}>
          End {formatINR(curve.ending_equity)}
        </span>
      </div>
    </div>
  );
}

export function AnalyticsView() {
  const summaryQuery = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: getAnalyticsSummary,
    refetchInterval: 20000,
  });
  const equityQuery = useQuery({
    queryKey: ['analytics-equity'],
    queryFn: getEquityCurve,
    refetchInterval: 20000,
  });
  const strategyQuery = useQuery({
    queryKey: ['analytics-by-strategy'],
    queryFn: getByStrategy,
    refetchInterval: 30000,
  });

  if (summaryQuery.isLoading) {
    return <Card className="text-sm text-content-muted">Loading performance analytics…</Card>;
  }
  if (summaryQuery.isError) {
    return (
      <Card className="text-sm text-loss">
        Could not load analytics:{' '}
        {summaryQuery.error instanceof Error ? summaryQuery.error.message : 'unknown error'}
      </Card>
    );
  }

  const m = summaryQuery.data;
  if (!m || m.total_trades === 0) {
    return (
      <Card className="text-sm text-content-muted">
        <p className="font-medium text-content">No performance data yet.</p>
        <p className="mt-1">
          Analytics are computed from closed paper trades. Once you close a position, win rate,
          expectancy, drawdown, the equity curve, and per-strategy attribution appear here.
        </p>
      </Card>
    );
  }

  const strategies = Object.entries(strategyQuery.data?.strategies ?? {});

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric
          label="Net P&L"
          value={formatINR(m.net_pnl)}
          sub={`${m.return_pct >= 0 ? '+' : ''}${m.return_pct.toFixed(2)}% return`}
          tone={m.net_pnl > 0 ? 'gain' : m.net_pnl < 0 ? 'loss' : undefined}
        />
        <Metric
          label="Win rate"
          value={`${(m.win_rate * 100).toFixed(0)}%`}
          sub={`${m.wins}W / ${m.losses}L / ${m.breakeven}BE`}
        />
        <Metric
          label="Profit factor"
          value={m.profit_factor.toFixed(2)}
          sub={`${m.total_trades} trades`}
        />
        <Metric
          label="Expectancy"
          value={formatINR(m.expectancy)}
          sub={`${m.expectancy_r.toFixed(2)}R / trade`}
          tone={m.expectancy > 0 ? 'gain' : m.expectancy < 0 ? 'loss' : undefined}
        />
        <Metric
          label="Max drawdown"
          value={formatINR(m.max_drawdown)}
          sub={`${m.max_drawdown_pct.toFixed(2)}%`}
          tone={m.max_drawdown > 0 ? 'loss' : undefined}
        />
        <Metric label="Sharpe (daily)" value={m.sharpe.toFixed(2)} />
        <Metric
          label="Avg win / loss"
          value={`${formatINR(m.avg_win)}`}
          sub={`loss ${formatINR(m.avg_loss)} · payoff ${m.payoff_ratio.toFixed(2)}`}
        />
        <Metric label="Avg holding" value={holdingLabel(m.avg_holding_seconds)} />
      </div>

      <Card>
        <CardHeader
          title="Equity curve"
          subtitle={`Best ${formatINR(m.best_trade)} · Worst ${formatINR(m.worst_trade)}`}
        />
        {equityQuery.data ? (
          <EquityChart curve={equityQuery.data} />
        ) : (
          <p className="text-sm text-content-muted">Loading curve…</p>
        )}
      </Card>

      <Card className="overflow-x-auto p-0">
        <div className="border-b border-surface-border px-5 py-4">
          <h2 className="text-sm font-semibold text-content">By strategy</h2>
          <p className="mt-0.5 text-xs text-content-muted">Performance attribution per strategy</p>
        </div>
        {strategies.length === 0 ? (
          <p className="px-5 py-4 text-sm text-content-muted">No per-strategy data yet.</p>
        ) : (
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-surface-border text-left text-xs text-content-muted">
                <th className="px-4 py-3 font-medium">Strategy</th>
                <th className="px-4 py-3 text-right font-medium">Trades</th>
                <th className="px-4 py-3 text-right font-medium">Win%</th>
                <th className="px-4 py-3 text-right font-medium">Net P&L</th>
                <th className="px-4 py-3 text-right font-medium">PF</th>
                <th className="px-4 py-3 text-right font-medium">Exp. R</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map(([name, s]) => (
                <tr key={name} className="border-b border-surface-border/50 last:border-0">
                  <td className="px-4 py-2.5 font-medium text-content">{name}</td>
                  <td className="tabular px-4 py-2.5 text-right text-content-muted">
                    {s.total_trades}
                  </td>
                  <td className="tabular px-4 py-2.5 text-right text-content-muted">
                    {(s.win_rate * 100).toFixed(0)}%
                  </td>
                  <td
                    className={cn(
                      'tabular px-4 py-2.5 text-right font-medium',
                      s.net_pnl > 0
                        ? 'text-gain'
                        : s.net_pnl < 0
                          ? 'text-loss'
                          : 'text-content-muted',
                    )}
                  >
                    {formatINR(s.net_pnl)}
                  </td>
                  <td className="tabular px-4 py-2.5 text-right text-content-muted">
                    {s.profit_factor.toFixed(2)}
                  </td>
                  <td
                    className={cn(
                      'tabular px-4 py-2.5 text-right',
                      s.expectancy_r > 0
                        ? 'text-gain'
                        : s.expectancy_r < 0
                          ? 'text-loss'
                          : 'text-content-muted',
                    )}
                  >
                    {s.expectancy_r.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
