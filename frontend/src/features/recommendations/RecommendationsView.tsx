'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import { Card, CardHeader } from '@/components/ui/Card';
import {
  getCommitteeReview,
  getInstruments,
  getOpportunities,
  type CommitteeDecision,
  type CommitteeReview,
  type Opportunity,
} from '@/features/recommendations/api';
import { cn } from '@/lib/utils';

/* ------------------------------- helpers ---------------------------------- */

const REFRESH_MS = 30000;

function price(value: number): string {
  return value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function riskOf(o: Opportunity): number {
  return Math.abs(o.entry - o.stop);
}

function rewardOf(o: Opportunity): number | null {
  const t = o.targets[0];
  return t == null ? null : Math.abs(t - o.entry);
}

function labelize(value: string): string {
  return value.replace(/_/g, ' ');
}

type Rec = CommitteeDecision['recommendation'];

const REC_STYLES: Record<Rec, string> = {
  strong_buy: 'border-gain/40 bg-gain/10 text-gain',
  buy: 'border-gain/30 bg-gain/10 text-gain',
  hold: 'border-caution/40 bg-caution/10 text-caution',
  sell: 'border-loss/30 bg-loss/10 text-loss',
  strong_sell: 'border-loss/40 bg-loss/10 text-loss',
  reject: 'border-surface-border bg-surface-overlay text-content-muted',
};

function RecBadge({ rec }: { rec: Rec }) {
  return (
    <span
      className={cn(
        'inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide',
        REC_STYLES[rec],
      )}
    >
      {labelize(rec)}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-overlay">
        <div
          className={cn(
            'h-full rounded-full',
            pct >= 70 ? 'bg-gain' : pct >= 55 ? 'bg-caution' : 'bg-loss',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="tabular text-xs text-content-muted">{pct.toFixed(0)}%</span>
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-content-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-[9rem] appearance-none rounded-md border border-surface-border bg-surface px-3 py-1.5 text-sm text-content outline-none focus:border-accent"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/* ---------------------------- recommendation card ------------------------- */

function Level({ label, value, tone }: { label: string; value: string; tone?: 'gain' | 'loss' }) {
  return (
    <div className="rounded-md border border-surface-border bg-surface p-3">
      <div className="text-xs text-content-faint">{label}</div>
      <div
        className={cn(
          'tabular mt-0.5 text-sm font-semibold text-content',
          tone === 'gain' && 'text-gain',
          tone === 'loss' && 'text-loss',
        )}
      >
        {value}
      </div>
    </div>
  );
}

function ReasonList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className={cn('mb-1 text-xs font-semibold uppercase tracking-wide', tone)}>{title}</p>
      <ul className="space-y-1">
        {items.map((it) => (
          <li key={it} className="flex gap-2 text-sm text-content-muted">
            <span className={cn('mt-1.5 h-1 w-1 shrink-0 rounded-full', tone)} />
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RecommendationCard({
  opportunity,
  regimeLabel,
  review,
  isLoading,
}: {
  opportunity: Opportunity;
  regimeLabel: string;
  review: CommitteeReview | undefined;
  isLoading: boolean;
}) {
  const o = opportunity;
  const reward = rewardOf(o);
  const decision = review?.decision;

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-content">{o.symbol}</h2>
            <span className={cn('text-sm', o.direction === 'long' ? 'text-gain' : 'text-loss')}>
              {o.direction.toUpperCase()}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-content-muted">
            {o.strategy_name} · {regimeLabel} regime · rank #{o.rank}
          </p>
        </div>
        <div className="text-right">
          {decision ? (
            <RecBadge rec={decision.recommendation} />
          ) : (
            <span className="text-xs text-content-faint">
              {isLoading ? 'Convening committee…' : 'Committee standing by'}
            </span>
          )}
          {decision ? (
            <div className="tabular mt-1 text-xs text-content-muted">
              Conviction {(decision.conviction * 100).toFixed(0)}% · Consensus{' '}
              {decision.consensus >= 0 ? '+' : ''}
              {decision.consensus.toFixed(2)}
            </div>
          ) : null}
        </div>
      </div>

      {/* Trade levels */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Level label="Entry" value={price(o.entry)} />
        <Level label="Stop" value={price(o.stop)} tone="loss" />
        <Level
          label="Target"
          value={o.targets[0] != null ? price(o.targets[0]) : '—'}
          tone="gain"
        />
        <Level label="Risk / unit" value={price(riskOf(o))} tone="loss" />
        <Level label="Reward / unit" value={reward != null ? price(reward) : '—'} tone="gain" />
        <Level label="Risk : Reward" value={`1 : ${o.risk_reward.toFixed(2)}`} />
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-content-muted">
        <span>
          Regime: <span className="capitalize text-content">{labelize(regimeLabel)}</span>
        </span>
        <span>
          Strategy: <span className="text-content">{o.strategy_name}</span>
        </span>
        <span>
          Expected hold: <span className="text-content">{o.expected_holding}</span>
        </span>
        <span className="tabular">Composite {o.composite.toFixed(0)}</span>
        <span className="tabular">Confidence {(o.confidence * 100).toFixed(0)}%</span>
      </div>

      {/* AI reasoning */}
      <div className="mt-5 border-t border-surface-border pt-4">
        <CardHeader
          title="AI committee reasoning"
          subtitle="Seven specialist agents + CIO synthesis"
        />
        {isLoading && !review ? (
          <p className="text-sm text-content-muted">Convening the committee…</p>
        ) : !review ? (
          <p className="text-sm text-content-muted">
            Select an opportunity to convene the committee.
          </p>
        ) : !review.convened || !decision ? (
          <div className="rounded-md border border-caution/30 bg-caution/5 p-3 text-sm text-caution">
            Committee stood aside: {review.reason ?? 'no qualifying deliberation.'}
          </div>
        ) : (
          <div className="space-y-4">
            {decision.rationale ? (
              <p className="text-sm text-content">{decision.rationale}</p>
            ) : null}

            {decision.vetoed && decision.veto_reasons.length > 0 ? (
              <div className="rounded-md border border-loss/30 bg-loss/5 p-3 text-sm text-loss">
                <p className="font-semibold">Veto raised</p>
                <ul className="mt-1 space-y-0.5">
                  {decision.veto_reasons.map((r) => (
                    <li key={r}>• {r}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2">
              <ReasonList title="Bull case" items={decision.bull_case} tone="text-gain" />
              <ReasonList title="Bear case" items={decision.bear_case} tone="text-loss" />
            </div>

            {decision.invalidation ? (
              <p className="text-xs text-content-muted">
                <span className="font-semibold text-content-faint">Invalidation:</span>{' '}
                {decision.invalidation}
              </p>
            ) : null}

            {/* Per-agent vote breakdown */}
            {review.reports && review.reports.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-faint">
                  Committee vote
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {review.reports.map((rep) => {
                    const contribution = decision.confidence_breakdown[rep.role] ?? 0;
                    return (
                      <div
                        key={rep.role}
                        className="flex items-start justify-between gap-2 rounded-md border border-surface-border bg-surface p-2"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium capitalize text-content">
                              {labelize(rep.role)}
                            </span>
                            {rep.veto ? (
                              <span className="rounded bg-loss/10 px-1 text-[10px] font-semibold text-loss">
                                VETO
                              </span>
                            ) : null}
                          </div>
                          <p className="truncate text-xs text-content-muted" title={rep.headline}>
                            {rep.headline}
                          </p>
                        </div>
                        <span
                          className={cn(
                            'tabular shrink-0 text-xs font-medium',
                            contribution > 0
                              ? 'text-gain'
                              : contribution < 0
                                ? 'text-loss'
                                : 'text-content-muted',
                          )}
                        >
                          {contribution >= 0 ? '+' : ''}
                          {contribution.toFixed(2)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </Card>
  );
}

/* --------------------------------- view ----------------------------------- */

const CONFIDENCE_OPTIONS = [
  { value: 'any', label: 'Any confidence' },
  { value: '0.5', label: '≥ 50%' },
  { value: '0.6', label: '≥ 60%' },
  { value: '0.7', label: '≥ 70%' },
  { value: '0.8', label: '≥ 80%' },
];

const DIRECTION_OPTIONS = [
  { value: 'any', label: 'Any direction' },
  { value: 'long', label: 'Long only' },
  { value: 'short', label: 'Short only' },
];

export function RecommendationsView() {
  const opportunitiesQuery = useQuery({
    queryKey: ['recommendations-opportunities'],
    queryFn: () => getOpportunities(30),
    refetchInterval: REFRESH_MS,
  });
  const instrumentsQuery = useQuery({
    queryKey: ['instruments'],
    queryFn: getInstruments,
    staleTime: 5 * 60 * 1000,
  });

  const [strategy, setStrategy] = useState('any');
  const [confidence, setConfidence] = useState('any');
  const [sector, setSector] = useState('any');
  const [direction, setDirection] = useState('any');
  const [selected, setSelected] = useState<string | null>(null);
  // Accumulates committee votes as rows are reviewed (real data, no fabrication).
  const [votes, setVotes] = useState<Record<string, Rec>>({});

  const book = opportunitiesQuery.data;
  const sectorBySymbol = useMemo(() => {
    const map: Record<string, string | null> = {};
    for (const inst of instrumentsQuery.data ?? []) map[inst.symbol] = inst.sector;
    return map;
  }, [instrumentsQuery.data]);

  const allOpportunities = useMemo(() => book?.top ?? [], [book]);

  const strategyOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const o of allOpportunities) seen.set(o.strategy, o.strategy_name);
    return [
      { value: 'any', label: 'All strategies' },
      ...[...seen.entries()].map(([value, label]) => ({ value, label })),
    ];
  }, [allOpportunities]);

  const sectorOptions = useMemo(() => {
    const set = new Set<string>();
    for (const o of allOpportunities) {
      const s = sectorBySymbol[o.symbol];
      if (s) set.add(s);
    }
    return [
      { value: 'any', label: 'All sectors' },
      ...[...set].sort().map((s) => ({ value: s, label: s })),
    ];
  }, [allOpportunities, sectorBySymbol]);

  const filtered = useMemo(() => {
    const minConf = confidence === 'any' ? 0 : Number(confidence);
    return allOpportunities.filter((o) => {
      if (strategy !== 'any' && o.strategy !== strategy) return false;
      if (direction !== 'any' && o.direction !== direction) return false;
      if (o.confidence < minConf) return false;
      if (sector !== 'any' && sectorBySymbol[o.symbol] !== sector) return false;
      return true;
    });
  }, [allOpportunities, strategy, direction, confidence, sector, sectorBySymbol]);

  // Keep a valid selection as filters/data change.
  useEffect(() => {
    if (filtered.length === 0) {
      setSelected(null);
      return;
    }
    if (!selected || !filtered.some((o) => o.symbol === selected)) {
      setSelected(filtered[0]?.symbol ?? null);
    }
  }, [filtered, selected]);

  const reviewQuery = useQuery({
    queryKey: ['committee-review', selected],
    queryFn: () => getCommitteeReview(selected as string),
    enabled: Boolean(selected),
    refetchInterval: REFRESH_MS,
  });

  // Remember each reviewed symbol's vote for the table's Committee Vote column.
  useEffect(() => {
    const d = reviewQuery.data?.decision;
    if (d)
      setVotes((prev) =>
        prev[d.symbol] === d.recommendation ? prev : { ...prev, [d.symbol]: d.recommendation },
      );
  }, [reviewQuery.data]);

  if (opportunitiesQuery.isLoading) {
    return <Card className="text-sm text-content-muted">Loading recommendations…</Card>;
  }
  if (opportunitiesQuery.isError || !book) {
    return (
      <Card className="text-sm text-loss">
        Could not load recommendations:{' '}
        {opportunitiesQuery.error instanceof Error
          ? opportunitiesQuery.error.message
          : 'unknown error'}
      </Card>
    );
  }

  const regimeLabel = book.regime.primary;
  const selectedOpportunity = filtered.find((o) => o.symbol === selected) ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-content-muted">
        <span>
          Regime{' '}
          <span className="font-medium capitalize text-content">{labelize(regimeLabel)}</span> ·
          Universe {book.universe_size} · {book.candidates} candidates
        </span>
        <span className="text-content-faint">
          {opportunitiesQuery.isFetching
            ? 'Refreshing…'
            : `Updated ${new Date(opportunitiesQuery.dataUpdatedAt).toLocaleTimeString()} · auto-refresh 30s`}
        </span>
      </div>

      {book.no_trade ? (
        <Card className="border-caution/30 bg-caution/5">
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-caution/40 bg-caution/10 px-2 py-0.5 text-xs font-semibold text-caution">
              NO-TRADE
            </span>
            <span className="text-sm font-medium text-content">Committee standing aside</span>
          </div>
          <p className="mt-2 text-sm text-content-muted">
            {book.no_trade_reason ?? 'No candidate cleared the quality bar.'}
          </p>
          <p className="mt-1 text-xs text-content-faint">
            Scanned {book.universe_size} instruments · {book.rejected} rejected. The engine never
            forces trades — this is a real verdict, not an empty page.
          </p>
        </Card>
      ) : (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <Select
              label="Strategy"
              value={strategy}
              onChange={setStrategy}
              options={strategyOptions}
            />
            <Select
              label="Confidence"
              value={confidence}
              onChange={setConfidence}
              options={CONFIDENCE_OPTIONS}
            />
            <Select label="Sector" value={sector} onChange={setSector} options={sectorOptions} />
            <Select
              label="Direction"
              value={direction}
              onChange={setDirection}
              options={DIRECTION_OPTIONS}
            />
          </div>

          {filtered.length === 0 ? (
            <Card className="text-sm text-content-muted">
              <p className="font-medium text-content">No opportunities match these filters.</p>
              <p className="mt-1">
                {allOpportunities.length} in the current book — relax the strategy, confidence,
                sector or direction filter to see them.
              </p>
            </Card>
          ) : (
            <>
              {/* Top opportunities */}
              <section>
                <h2 className="mb-3 text-sm font-semibold text-content">
                  Top opportunities ({filtered.length})
                </h2>
                <Card className="overflow-x-auto p-0">
                  <table className="w-full min-w-[760px] text-sm">
                    <thead>
                      <tr className="border-b border-surface-border text-left text-xs text-content-muted">
                        <th className="px-4 py-3 font-medium">#</th>
                        <th className="px-4 py-3 font-medium">Symbol</th>
                        <th className="px-4 py-3 font-medium">Strategy</th>
                        <th className="px-4 py-3 font-medium">Side</th>
                        <th className="px-4 py-3 font-medium">Confidence</th>
                        <th className="px-4 py-3 text-right font-medium">Risk</th>
                        <th className="px-4 py-3 text-right font-medium">Reward</th>
                        <th className="px-4 py-3 font-medium">Committee vote</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((o) => {
                        const reward = rewardOf(o);
                        const vote = votes[o.symbol];
                        const isSel = o.symbol === selected;
                        return (
                          <tr
                            key={`${o.symbol}-${o.strategy}`}
                            onClick={() => setSelected(o.symbol)}
                            className={cn(
                              'cursor-pointer border-b border-surface-border/50 last:border-0',
                              isSel ? 'bg-accent/5' : 'hover:bg-surface-overlay/40',
                            )}
                          >
                            <td className="tabular px-4 py-2.5 text-content-muted">{o.rank}</td>
                            <td className="px-4 py-2.5 font-medium text-content">{o.symbol}</td>
                            <td className="px-4 py-2.5 text-content-muted">{o.strategy_name}</td>
                            <td className="px-4 py-2.5">
                              <span
                                className={cn(o.direction === 'long' ? 'text-gain' : 'text-loss')}
                              >
                                {o.direction}
                              </span>
                            </td>
                            <td className="px-4 py-2.5">
                              <ConfidenceBar value={o.confidence} />
                            </td>
                            <td className="tabular px-4 py-2.5 text-right text-loss">
                              {price(riskOf(o))}
                            </td>
                            <td className="tabular px-4 py-2.5 text-right text-gain">
                              {reward != null ? price(reward) : '—'}
                            </td>
                            <td className="px-4 py-2.5">
                              {vote ? (
                                <RecBadge rec={vote} />
                              ) : isSel && reviewQuery.isFetching ? (
                                <span className="text-xs text-content-faint">Convening…</span>
                              ) : (
                                <span className="text-xs text-accent">Select to review →</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </Card>
              </section>

              {/* Recommendation card */}
              {selectedOpportunity ? (
                <section>
                  <h2 className="mb-3 text-sm font-semibold text-content">Recommendation</h2>
                  <RecommendationCard
                    opportunity={selectedOpportunity}
                    regimeLabel={regimeLabel}
                    review={reviewQuery.data}
                    isLoading={reviewQuery.isLoading}
                  />
                </section>
              ) : null}
            </>
          )}
        </>
      )}
    </div>
  );
}
