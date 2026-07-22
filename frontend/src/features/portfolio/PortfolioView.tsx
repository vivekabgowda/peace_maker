'use client';

import { useQuery } from '@tanstack/react-query';

import { Card, CardHeader } from '@/components/ui/Card';
import {
  getAccount,
  getAnalyticsSummary,
  getDailyReturns,
  getEquityCurve,
  getPositions,
  type DailyReturn,
  type EquityCurve,
  type PaperPosition,
} from '@/features/portfolio/api';
import { cn, formatINR } from '@/lib/utils';

/* ------------------------------- helpers ---------------------------------- */

function price(value: number): string {
  return value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function exposureOf(p: PaperPosition): number {
  return (p.mark_price ?? p.entry_price) * p.quantity;
}

function toneClass(value: number): string {
  return value > 0 ? 'text-gain' : value < 0 ? 'text-loss' : 'text-content-muted';
}

/* -------------------------------- tiles ----------------------------------- */

function StatTile({
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

/* -------------------------------- charts ---------------------------------- */

function EquityCurveChart({ curve }: { curve: EquityCurve }) {
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

function DailyReturnsChart({ days }: { days: DailyReturn[] }) {
  if (days.length === 0) {
    return <p className="text-sm text-content-muted">No closed trades in the last 30 days.</p>;
  }
  const maxAbs = Math.max(...days.map((d) => Math.abs(d.net_pnl)), 1);
  return (
    <div>
      <div className="flex h-40 items-stretch gap-1">
        {days.map((d) => {
          const pct = (Math.abs(d.net_pnl) / maxAbs) * 50; // half-height each side of zero
          const positive = d.net_pnl >= 0;
          return (
            <div
              key={d.date}
              title={`${d.date}: ${formatINR(d.net_pnl)}`}
              className="flex flex-1 flex-col justify-center"
            >
              <div className="flex h-1/2 items-end">
                {positive ? (
                  <div
                    className="w-full rounded-sm bg-gain/70"
                    style={{ height: `${Math.max(pct, d.net_pnl !== 0 ? 3 : 0)}%` }}
                  />
                ) : null}
              </div>
              <div className="flex h-1/2 items-start">
                {!positive ? (
                  <div
                    className="w-full rounded-sm bg-loss/70"
                    style={{ height: `${Math.max(pct, 3)}%` }}
                  />
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-xs text-content-muted">
        <span>{days[0]?.date}</span>
        <span>{days[days.length - 1]?.date}</span>
      </div>
    </div>
  );
}

function AllocationBars({ positions }: { positions: PaperPosition[] }) {
  if (positions.length === 0) {
    return <p className="text-sm text-content-muted">No open positions to allocate.</p>;
  }
  const rows = positions
    .map((p) => ({ symbol: p.symbol, exposure: exposureOf(p), direction: p.direction }))
    .sort((a, b) => b.exposure - a.exposure);
  const total = rows.reduce((sum, r) => sum + r.exposure, 0) || 1;

  return (
    <div className="space-y-3">
      {rows.map((r) => {
        const share = (r.exposure / total) * 100;
        return (
          <div key={r.symbol}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="font-medium text-content">{r.symbol}</span>
              <span className="tabular text-content-muted">
                {formatINR(r.exposure)} · {share.toFixed(1)}%
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-overlay">
              <div
                className={cn(
                  'h-full rounded-full',
                  r.direction === 'long' ? 'bg-accent' : 'bg-caution',
                )}
                style={{ width: `${share}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------ positions --------------------------------- */

function PositionsTable({ positions }: { positions: PaperPosition[] }) {
  if (positions.length === 0) {
    return (
      <Card className="text-sm text-content-muted">
        <p className="font-medium text-content">No open positions.</p>
        <p className="mt-1">
          Positions you open in paper trading appear here with live mark-to-market P&L and exposure.
        </p>
      </Card>
    );
  }
  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-surface-border text-left text-xs text-content-muted">
            <th className="px-4 py-3 font-medium">Symbol</th>
            <th className="px-4 py-3 font-medium">Side</th>
            <th className="px-4 py-3 text-right font-medium">Qty</th>
            <th className="px-4 py-3 text-right font-medium">Entry</th>
            <th className="px-4 py-3 text-right font-medium">Current</th>
            <th className="px-4 py-3 text-right font-medium">P&L</th>
            <th className="px-4 py-3 text-right font-medium">Exposure</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const hasMark = p.mark_price != null;
            const pnl = p.unrealized_pnl ?? 0;
            return (
              <tr key={p.id} className="border-b border-surface-border/50 last:border-0">
                <td className="px-4 py-2.5 font-medium text-content">{p.symbol}</td>
                <td className="px-4 py-2.5">
                  <span className={cn(p.direction === 'long' ? 'text-gain' : 'text-loss')}>
                    {p.direction}
                  </span>
                </td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">{p.quantity}</td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {price(p.entry_price)}
                </td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {hasMark ? price(p.mark_price as number) : '—'}
                </td>
                <td className={cn('tabular px-4 py-2.5 text-right font-medium', toneClass(pnl))}>
                  {hasMark ? formatINR(pnl) : '—'}
                </td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {formatINR(exposureOf(p))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

/* --------------------------------- view ----------------------------------- */

export function PortfolioView() {
  const accountQuery = useQuery({
    queryKey: ['paper-account'],
    queryFn: getAccount,
    refetchInterval: 15000,
  });
  const positionsQuery = useQuery({
    queryKey: ['paper-positions'],
    queryFn: getPositions,
    refetchInterval: 15000,
  });
  const summaryQuery = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: getAnalyticsSummary,
    refetchInterval: 30000,
  });
  const equityQuery = useQuery({
    queryKey: ['analytics-equity'],
    queryFn: getEquityCurve,
    refetchInterval: 30000,
  });
  const dailyQuery = useQuery({
    queryKey: ['analytics-daily', 30],
    queryFn: () => getDailyReturns(30),
    refetchInterval: 30000,
  });

  if (accountQuery.isLoading) {
    return <Card className="text-sm text-content-muted">Loading your portfolio…</Card>;
  }
  if (accountQuery.isError || !accountQuery.data) {
    return (
      <Card className="text-sm text-loss">
        Could not load your portfolio:{' '}
        {accountQuery.error instanceof Error ? accountQuery.error.message : 'unknown error'}
      </Card>
    );
  }

  const account = accountQuery.data;
  const positions = positionsQuery.data?.positions ?? [];
  const summary = summaryQuery.data;
  const totalExposure = positions.reduce((sum, p) => sum + exposureOf(p), 0);
  const exposurePct = account.equity > 0 ? (totalExposure / account.equity) * 100 : 0;
  const hasActivity = positions.length > 0 || (summary?.total_trades ?? 0) > 0;

  return (
    <div className="space-y-6">
      {/* Account summary */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-content">Account summary</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
          <StatTile label="Balance (cash)" value={formatINR(account.cash)} />
          <StatTile
            label="Equity"
            value={formatINR(account.equity)}
            sub={`${account.return_pct >= 0 ? '+' : ''}${account.return_pct.toFixed(2)}%`}
            tone={
              account.equity > account.starting_cash
                ? 'gain'
                : account.equity < account.starting_cash
                  ? 'loss'
                  : undefined
            }
          />
          <StatTile
            label="Unrealized P&L"
            value={formatINR(account.unrealized_pnl)}
            tone={
              account.unrealized_pnl > 0 ? 'gain' : account.unrealized_pnl < 0 ? 'loss' : undefined
            }
          />
          <StatTile
            label="Realized P&L"
            value={formatINR(account.realized_pnl)}
            tone={account.realized_pnl > 0 ? 'gain' : account.realized_pnl < 0 ? 'loss' : undefined}
          />
          <StatTile
            label="Buying power"
            value={formatINR(account.cash)}
            sub="No margin (cash account)"
          />
        </div>
      </section>

      {!hasActivity ? (
        <Card className="text-sm text-content-muted">
          <p className="font-medium text-content">Your portfolio is empty.</p>
          <p className="mt-1">
            You&apos;re starting with {formatINR(account.starting_cash)} of paper capital. Open a
            paper position and your holdings, exposure, equity curve and risk metrics will populate
            here — all simulated against live prices, with no live broker orders.
          </p>
        </Card>
      ) : null}

      {/* Positions */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-content">
          Positions{positions.length ? ` (${positions.length})` : ''}
        </h2>
        <PositionsTable positions={positions} />
      </section>

      {/* Charts */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-content">Charts</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card className="lg:col-span-2">
            <CardHeader
              title="Equity curve"
              subtitle={
                summary
                  ? `Best ${formatINR(summary.best_trade)} · Worst ${formatINR(summary.worst_trade)}`
                  : 'Cumulative equity after each closed trade'
              }
            />
            {equityQuery.data ? (
              <EquityCurveChart curve={equityQuery.data} />
            ) : (
              <p className="text-sm text-content-muted">Loading curve…</p>
            )}
          </Card>
          <Card>
            <CardHeader title="Daily returns" subtitle="Net P&L per day (last 30 days)" />
            {dailyQuery.data ? (
              <DailyReturnsChart days={dailyQuery.data.days} />
            ) : (
              <p className="text-sm text-content-muted">Loading daily returns…</p>
            )}
          </Card>
          <Card>
            <CardHeader title="Allocation" subtitle="Open exposure by symbol" />
            <AllocationBars positions={positions} />
          </Card>
        </div>
      </section>

      {/* Risk */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-content">Risk</h2>
        {summary && summary.total_trades > 0 ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
            <StatTile
              label="Max drawdown"
              value={formatINR(summary.max_drawdown)}
              sub={`${summary.max_drawdown_pct.toFixed(2)}%`}
              tone={summary.max_drawdown > 0 ? 'loss' : undefined}
            />
            <StatTile
              label="Exposure %"
              value={`${exposurePct.toFixed(1)}%`}
              sub={`${formatINR(totalExposure)} of equity`}
            />
            <StatTile label="Win rate" value={`${(summary.win_rate * 100).toFixed(0)}%`} />
            <StatTile label="Sharpe (daily)" value={summary.sharpe.toFixed(2)} />
            <StatTile label="Profit factor" value={summary.profit_factor.toFixed(2)} />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
            <StatTile
              label="Exposure %"
              value={`${exposurePct.toFixed(1)}%`}
              sub={`${formatINR(totalExposure)} of equity`}
            />
            <Card className="col-span-2 flex items-center text-sm text-content-muted md:col-span-2 lg:col-span-4">
              Drawdown, win rate, Sharpe and profit factor appear once you have closed trades.
            </Card>
          </div>
        )}
      </section>
    </div>
  );
}
