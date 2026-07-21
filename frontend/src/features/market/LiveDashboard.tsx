'use client';

import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo, useState } from 'react';

import { Card, CardHeader } from '@/components/ui/Card';
import { getBreadth, getIndices, getMarketStatus, type Quote } from '@/features/market/api';
import { useMarketSocket, type WsMessage } from '@/lib/ws/useMarketSocket';
import { cn, formatPct } from '@/lib/utils';

const INDEX_ORDER = ['NIFTY', 'BANKNIFTY', 'SENSEX', 'INDIAVIX'];

function toNum(v: number | string | undefined): number | null {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return n === undefined || Number.isNaN(n) ? null : n;
}

export function LiveDashboard() {
  const [liveLtp, setLiveLtp] = useState<Record<string, number>>({});

  const indicesQuery = useQuery({
    queryKey: ['indices'],
    queryFn: getIndices,
    refetchInterval: 15000,
  });
  const statusQuery = useQuery({
    queryKey: ['mstatus'],
    queryFn: getMarketStatus,
    refetchInterval: 10000,
  });
  const breadthQuery = useQuery({
    queryKey: ['breadth'],
    queryFn: getBreadth,
    refetchInterval: 15000,
  });

  const onMessage = useCallback((msg: WsMessage) => {
    if (msg.event === 'quote' && msg.data && typeof msg.data === 'object') {
      const d = msg.data as { symbol: string; ltp: string };
      const ltp = parseFloat(d.ltp);
      if (!Number.isNaN(ltp)) setLiveLtp((prev) => ({ ...prev, [d.symbol]: ltp }));
    }
  }, []);

  const { state, lastMessageAt } = useMarketSocket(['indices', 'quotes', 'breadth'], onMessage);

  const indices = useMemo(() => {
    const base = indicesQuery.data ?? [];
    const bySymbol = new Map(base.map((q) => [q.symbol, q]));
    return INDEX_ORDER.map((sym) => bySymbol.get(sym)).filter(Boolean) as Quote[];
  }, [indicesQuery.data]);

  const freshness = lastMessageAt ? Math.round((Date.now() - lastMessageAt) / 1000) : null;

  return (
    <div className="space-y-6">
      {/* Connection / freshness bar */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-content-muted">
        <span className="inline-flex items-center gap-1.5">
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              state === 'open' ? 'bg-gain' : state === 'connecting' ? 'bg-caution' : 'bg-loss',
            )}
          />
          Live feed: {state}
        </span>
        <span>Market: {statusQuery.data?.status ?? '—'}</span>
        <span>Data age: {freshness !== null ? `${freshness}s` : '—'}</span>
        {state !== 'open' ? (
          <span className="text-caution">
            Showing last-known values — reconnecting to the live feed…
          </span>
        ) : null}
      </div>

      {/* Index tiles */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {indices.length === 0 ? (
          <Card className="col-span-full text-sm text-content-muted">
            Market quiet — no live index data yet. Enable the feed (BKN_MARKET_FEED_ENABLED) to
            stream quotes.
          </Card>
        ) : (
          indices.map((q) => {
            const live = liveLtp[q.symbol] ?? toNum(q.ltp);
            const change = q.change_pct;
            return (
              <Card key={q.symbol}>
                <div className="text-xs text-content-faint">{q.symbol}</div>
                <div className="tabular mt-1 text-lg font-semibold">
                  {live !== null ? live.toLocaleString('en-IN') : '—'}
                </div>
                {change !== null ? (
                  <div className={cn('tabular text-xs', change >= 0 ? 'text-gain' : 'text-loss')}>
                    {formatPct(change)}
                  </div>
                ) : null}
              </Card>
            );
          })
        )}
      </div>

      {/* Breadth + sectors */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Market Breadth" subtitle="Advances vs declines" />
          <BreadthBar breadth={breadthQuery.data?.breadth} />
        </Card>
        <Card>
          <CardHeader title="Sector Strength" subtitle="Avg % change by sector" />
          <div className="space-y-1.5">
            {(breadthQuery.data?.sectors ?? []).slice(0, 6).map((s) => (
              <div key={s.sector} className="flex items-center justify-between text-sm">
                <span className="text-content-muted">{s.sector}</span>
                <span className={cn('tabular', s.avg_change_pct >= 0 ? 'text-gain' : 'text-loss')}>
                  {formatPct(s.avg_change_pct)}
                </span>
              </div>
            ))}
            {(breadthQuery.data?.sectors ?? []).length === 0 ? (
              <p className="text-sm text-content-muted">No sector data yet.</p>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  );
}

function BreadthBar({
  breadth,
}: {
  breadth?: { advances: number; declines: number; unchanged: number };
}) {
  const a = breadth?.advances ?? 0;
  const d = breadth?.declines ?? 0;
  const total = Math.max(1, a + d + (breadth?.unchanged ?? 0));
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded">
        <div className="bg-gain" style={{ width: `${(a / total) * 100}%` }} />
        <div
          className="bg-surface-border"
          style={{ width: `${((breadth?.unchanged ?? 0) / total) * 100}%` }}
        />
        <div className="bg-loss" style={{ width: `${(d / total) * 100}%` }} />
      </div>
      <div className="mt-2 flex justify-between text-xs">
        <span className="text-gain">{a} advancing</span>
        <span className="text-loss">{d} declining</span>
      </div>
    </div>
  );
}
