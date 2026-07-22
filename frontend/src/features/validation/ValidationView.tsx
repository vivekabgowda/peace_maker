'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import {
  getValidationRun,
  listValidationRuns,
  runMonteCarlo,
  runValidation,
  type MonteCarlo,
  type StrategyValidation,
  type WalkForward,
} from '@/features/validation/api';
import { ApiRequestError } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';

function errMessage(e: unknown): string {
  if (e instanceof ApiRequestError) return e.message;
  if (e instanceof Error) return e.message;
  return 'Request failed';
}

function pct(x: number): string {
  return `${(x * 100).toFixed(0)}%`;
}

function Tile({
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

/* ----------------------------- walk-forward -------------------------------- */

function FoldBars({ wf }: { wf: WalkForward }) {
  if (wf.folds.length === 0) {
    return <p className="text-xs text-content-faint">Not enough trades to fold.</p>;
  }
  const maxAbs = Math.max(...wf.folds.map((f) => Math.abs(f.net_expectancy_r)), 0.01);
  return (
    <div className="flex items-end gap-2">
      {wf.folds.map((f) => {
        const h = (Math.abs(f.net_expectancy_r) / maxAbs) * 48;
        const pos = f.net_expectancy_r >= 0;
        return (
          <div
            key={f.index}
            className="flex flex-col items-center gap-1"
            title={`Fold ${f.index + 1}: ${f.net_expectancy_r.toFixed(3)}R net, ${f.n_trades} trades`}
          >
            <div className="flex h-12 items-end">
              <div
                className={cn('w-6 rounded-sm', pos ? 'bg-gain/70' : 'bg-loss/70')}
                style={{ height: `${Math.max(h, 3)}px` }}
              />
            </div>
            <span className="tabular text-[10px] text-content-faint">
              {f.net_expectancy_r.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------ monte carlo -------------------------------- */

function MonteCarloPanel({ strategy }: { strategy: string }) {
  const [data, setData] = useState<MonteCarlo | null>(null);
  const run = useMutation({
    mutationFn: (method: 'resample' | 'shuffle') => runMonteCarlo(strategy, method),
    onSuccess: setData,
  });

  const isAdmin = useAuthStore((s) => s.user?.role) === 'admin';

  return (
    <Card>
      <CardHeader
        title="Monte Carlo"
        subtitle={`Resampled net-of-cost equity paths for ${strategy} (worst-case drawdown & return distribution).`}
      />
      {!isAdmin ? (
        <p className="text-sm text-content-muted">
          Running a simulation requires an admin account.
        </p>
      ) : (
        <div className="flex items-center gap-2">
          <Button onClick={() => run.mutate('resample')} disabled={run.isPending}>
            {run.isPending ? 'Simulating…' : 'Run (resample)'}
          </Button>
          <Button
            variant="secondary"
            onClick={() => run.mutate('shuffle')}
            disabled={run.isPending}
          >
            Shuffle
          </Button>
          {run.isError ? <span className="text-xs text-loss">{errMessage(run.error)}</span> : null}
        </div>
      )}
      {data ? (
        data.n_trades === 0 ? (
          <p className="mt-3 text-sm text-content-muted">
            No trades to simulate for this strategy.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Tile
                label="P(loss)"
                value={pct(data.prob_loss)}
                tone={data.prob_loss > 0.5 ? 'loss' : undefined}
              />
              <Tile
                label="Return p50 (R)"
                value={data.final_return.p50.toFixed(2)}
                tone={data.final_return.p50 >= 0 ? 'gain' : 'loss'}
              />
              <Tile
                label="Return p05 / p95"
                value={`${data.final_return.p05.toFixed(1)} / ${data.final_return.p95.toFixed(1)}`}
              />
              <Tile label="Max DD p95 (R)" value={data.max_drawdown.p95.toFixed(2)} tone="loss" />
            </div>
            <p className="text-xs text-content-faint">
              {data.simulations.toLocaleString()} simulations · {data.n_trades} trades ·{' '}
              {data.method} · worst drawdown {data.max_drawdown.worst.toFixed(2)}R · {data.units}
            </p>
          </div>
        )
      ) : null}
    </Card>
  );
}

/* -------------------------------- strategies ------------------------------- */

function verdictBadge(s: StrategyValidation) {
  if (s.significant_after_correction)
    return (
      <span className="rounded-full border border-gain/40 bg-gain/10 px-2 py-0.5 text-xs font-medium text-gain">
        survives
      </span>
    );
  if (s.trades < 30)
    return (
      <span className="rounded-full border border-surface-border bg-surface-overlay px-2 py-0.5 text-xs text-content-muted">
        insufficient
      </span>
    );
  return (
    <span className="rounded-full border border-loss/30 bg-loss/10 px-2 py-0.5 text-xs font-medium text-loss">
      no edge
    </span>
  );
}

function StrategyTable({
  strategies,
  selected,
  onSelect,
}: {
  strategies: StrategyValidation[];
  selected: string | null;
  onSelect: (k: string) => void;
}) {
  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[820px] text-sm">
        <thead>
          <tr className="border-b border-surface-border text-left text-xs text-content-muted">
            <th className="px-4 py-3 font-medium">Strategy</th>
            <th className="px-4 py-3 text-right font-medium">Trades</th>
            <th className="px-4 py-3 text-right font-medium">Gross R</th>
            <th className="px-4 py-3 text-right font-medium">Net R</th>
            <th className="px-4 py-3 text-right font-medium">Cost drag</th>
            <th className="px-4 py-3 text-right font-medium">Net PF</th>
            <th className="px-4 py-3 text-right font-medium">Deflated Sharpe</th>
            <th className="px-4 py-3 text-right font-medium">q-value</th>
            <th className="px-4 py-3 font-medium">Verdict</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s) => {
            const wf = s.walk_forward;
            const isSel = s.strategy === selected;
            return (
              <tr
                key={s.strategy}
                onClick={() => onSelect(s.strategy)}
                className={cn(
                  'cursor-pointer border-b border-surface-border/50 last:border-0',
                  isSel ? 'bg-accent/5' : 'hover:bg-surface-overlay/40',
                )}
              >
                <td className="px-4 py-2.5 font-medium text-content">{s.strategy}</td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">{s.trades}</td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {wf.gross_expectancy_r.toFixed(3)}
                </td>
                <td
                  className={cn(
                    'tabular px-4 py-2.5 text-right font-medium',
                    wf.net_expectancy_r >= 0 ? 'text-gain' : 'text-loss',
                  )}
                >
                  {wf.net_expectancy_r.toFixed(3)}
                </td>
                <td className="tabular px-4 py-2.5 text-right text-loss">
                  -{wf.cost_drag_r.toFixed(3)}
                </td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {wf.net_profit_factor.toFixed(2)}
                </td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {(wf.sharpe.dsr * 100).toFixed(0)}%
                </td>
                <td className="tabular px-4 py-2.5 text-right text-content-muted">
                  {s.q_value.toFixed(3)}
                </td>
                <td className="px-4 py-2.5">{verdictBadge(s)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

/* --------------------------------- view ------------------------------------ */

export function ValidationView() {
  const qc = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.role) === 'admin';
  const runsQuery = useQuery({ queryKey: ['validation-runs'], queryFn: listValidationRuns });
  const [runId, setRunId] = useState<number | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);

  // Default to the most recent run.
  useEffect(() => {
    if (runId === null && runsQuery.data && runsQuery.data.length > 0) {
      setRunId(runsQuery.data[0]!.id);
    }
  }, [runsQuery.data, runId]);

  const detailQuery = useQuery({
    queryKey: ['validation-run', runId],
    queryFn: () => getValidationRun(runId as number),
    enabled: runId !== null,
  });

  const runMutation = useMutation({
    mutationFn: () => runValidation(400, 4),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ['validation-runs'] });
      qc.setQueryData(['validation-run', run.id], run);
      setRunId(run.id);
      setSelectedStrategy(null);
    },
  });

  const detail = detailQuery.data;
  const strategies = useMemo(() => detail?.strategies ?? [], [detail]);

  // Keep a valid selected strategy.
  useEffect(() => {
    if (strategies.length > 0 && !strategies.some((s) => s.strategy === selectedStrategy)) {
      setSelectedStrategy(strategies[0]!.strategy);
    }
  }, [strategies, selectedStrategy]);

  const selected = strategies.find((s) => s.strategy === selectedStrategy) ?? null;

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-content-muted">Run</span>
          <select
            value={runId ?? ''}
            onChange={(e) => {
              setRunId(Number(e.target.value));
              setSelectedStrategy(null);
            }}
            disabled={!runsQuery.data || runsQuery.data.length === 0}
            className="appearance-none rounded-md border border-surface-border bg-surface px-3 py-1.5 text-sm text-content outline-none focus:border-accent disabled:opacity-50"
          >
            {(runsQuery.data ?? []).map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} · {new Date(r.created_at).toLocaleString('en-IN')} · {r.survivors.length}{' '}
                survivor(s)
              </option>
            ))}
            {(runsQuery.data ?? []).length === 0 ? <option value="">No runs yet</option> : null}
          </select>
        </div>
        {isAdmin ? (
          <div className="flex items-center gap-2">
            <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
              {runMutation.isPending ? 'Validating…' : 'Run validation'}
            </Button>
            {runMutation.isError ? (
              <span className="text-xs text-loss">{errMessage(runMutation.error)}</span>
            ) : null}
          </div>
        ) : (
          <span className="text-xs text-content-faint">
            Running a validation requires an admin account.
          </span>
        )}
      </div>

      {runsQuery.isLoading ? (
        <Card className="text-sm text-content-muted">Loading validation runs…</Card>
      ) : (runsQuery.data ?? []).length === 0 ? (
        <Card className="text-sm text-content-muted">
          <p className="font-medium text-content">No validation runs yet.</p>
          <p className="mt-1">
            A validation run backtests every strategy on stored candles, applies realistic Indian
            costs and slippage, evaluates each out-of-sample, and corrects for multiple testing —
            reporting which strategies (if any) show a statistically significant, cost-surviving
            edge. {isAdmin ? 'Click “Run validation” to generate one.' : 'Ask an admin to run one.'}
          </p>
        </Card>
      ) : detailQuery.isLoading ? (
        <Card className="text-sm text-content-muted">Loading run…</Card>
      ) : detail ? (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Tile label="Strategies evaluated" value={String(detail.strategies_evaluated)} />
            <Tile
              label="Survivors"
              value={String(detail.survivors.length)}
              sub={
                detail.survivors.length ? detail.survivors.join(', ') : 'none survived correction'
              }
              tone={detail.survivors.length ? 'gain' : 'loss'}
            />
            <Tile
              label="Round-trip cost"
              value={`${detail.roundtrip_cost_bps.toFixed(1)} bps`}
              sub={detail.segment}
            />
            <Tile
              label="Reference notional"
              value={`₹${detail.reference_notional.toLocaleString('en-IN')}`}
            />
          </div>

          <section>
            <h2 className="mb-3 text-sm font-semibold text-content">Per-strategy validation</h2>
            <StrategyTable
              strategies={strategies}
              selected={selectedStrategy}
              onSelect={setSelectedStrategy}
            />
            <p className="mt-2 text-xs text-content-faint">
              Net R is expectancy after costs; deflated Sharpe is the probability the edge is real
              given the number of strategies tried; q-value is the Benjamini–Hochberg-adjusted
              significance. A strategy “survives” only if it clears correction.
            </p>
          </section>

          {selected ? (
            <section className="space-y-4">
              <h2 className="text-sm font-semibold text-content">{selected.strategy} — detail</h2>
              <Card>
                <CardHeader
                  title="Out-of-sample walk-forward"
                  subtitle="Net expectancy (R) per temporal fold — a real edge persists across folds"
                />
                <FoldBars wf={selected.walk_forward} />
                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-content-muted">
                  <span>
                    OOS consistency:{' '}
                    <span className="text-content">
                      {pct(selected.walk_forward.oos_consistency)}
                    </span>
                  </span>
                  <span className="tabular">
                    Expectancy 95% CI: {selected.walk_forward.expectancy_ci.low.toFixed(3)} …{' '}
                    {selected.walk_forward.expectancy_ci.high.toFixed(3)}
                    {selected.walk_forward.expectancy_ci.significant
                      ? ' (significant)'
                      : ' (spans zero)'}
                  </span>
                  <span className="tabular">
                    PSR: {(selected.walk_forward.sharpe.psr * 100).toFixed(0)}%
                  </span>
                  <span className="tabular">
                    Deflated Sharpe: {(selected.walk_forward.sharpe.dsr * 100).toFixed(0)}%
                  </span>
                </div>
              </Card>
              <MonteCarloPanel strategy={selected.strategy} />
            </section>
          ) : null}
        </>
      ) : detailQuery.isError ? (
        <Card className="text-sm text-loss">
          Could not load run: {errMessage(detailQuery.error)}
        </Card>
      ) : null}
    </div>
  );
}
