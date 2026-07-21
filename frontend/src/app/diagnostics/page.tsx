'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { getDiagnostics, type Diagnostics, type ServiceStatus } from '@/features/diagnostics/api';
import { cn } from '@/lib/utils';

const POLL_MS = 5000;

function StatusDot({ healthy }: { healthy: boolean | null }) {
  return (
    <span
      className={cn(
        'inline-block h-2.5 w-2.5 rounded-full',
        healthy === null ? 'bg-amber-400' : healthy ? 'bg-emerald-500' : 'bg-rose-500',
      )}
      aria-hidden
    />
  );
}

function ServiceCard({ service }: { service: ServiceStatus }) {
  return (
    <div className="rounded-md border border-surface-border bg-surface-raised p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusDot healthy={service.healthy} />
          <span className="text-sm font-semibold capitalize text-content">
            {service.name.replace(/_/g, ' ')}
          </span>
        </div>
        {service.latency_ms !== null ? (
          <span className="text-xs tabular-nums text-content-muted">{service.latency_ms} ms</span>
        ) : null}
      </div>
      <p className="mt-1 text-xs text-content-muted">{service.kind}</p>
      <p className="mt-2 text-xs text-content">{service.detail}</p>
    </div>
  );
}

export default function DiagnosticsPage() {
  const [data, setData] = useState<Diagnostics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastFetchAt, setLastFetchAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await getDiagnostics();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backend unreachable');
    } finally {
      setLoading(false);
      setLastFetchAt(Date.now());
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const backendReachable = error === null && data !== null;
  const overallHealthy = backendReachable && data?.status === 'healthy';

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-10">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-content">System Diagnostics</h1>
          <p className="mt-1 text-sm text-content-muted">
            Local bring-up status for every BKN AI Capital service.
          </p>
        </div>
        <Link href="/dashboard" className="text-xs text-content-muted hover:text-content">
          ← Back to app
        </Link>
      </div>

      {/* Overall banner */}
      <div
        className={cn(
          'mb-6 flex items-center justify-between rounded-md border p-4',
          overallHealthy
            ? 'border-emerald-500/30 bg-emerald-500/10'
            : backendReachable
              ? 'border-amber-500/30 bg-amber-500/10'
              : 'border-rose-500/30 bg-rose-500/10',
        )}
      >
        <div className="flex items-center gap-3">
          <StatusDot healthy={backendReachable ? (overallHealthy ? true : false) : null} />
          <div>
            <p className="text-sm font-semibold text-content">
              {loading && !data
                ? 'Checking services…'
                : !backendReachable
                  ? 'Backend unreachable'
                  : overallHealthy
                    ? 'All core services healthy'
                    : 'Degraded — a core service is down'}
            </p>
            {error ? <p className="mt-0.5 text-xs text-rose-400">{error}</p> : null}
          </div>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded border border-surface-border px-3 py-1 text-xs text-content-muted hover:text-content"
        >
          Refresh
        </button>
      </div>

      {/* Frontend -> Backend connectivity (this page proves it when data loads) */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-surface-border bg-surface-raised p-4">
          <div className="flex items-center gap-2">
            <StatusDot healthy={backendReachable} />
            <span className="text-sm font-semibold text-content">Frontend → Backend</span>
          </div>
          <p className="mt-2 text-xs text-content-muted">
            {backendReachable
              ? 'The frontend reached the backend API and parsed a valid response.'
              : 'The frontend could not reach the backend API (check the backend container).'}
          </p>
        </div>
        <div className="rounded-md border border-surface-border bg-surface-raised p-4">
          <div className="flex items-center gap-2">
            <StatusDot healthy={backendReachable ? !data?.broker_connected : null} />
            <span className="text-sm font-semibold text-content">Live broker</span>
          </div>
          <p className="mt-2 text-xs text-content-muted">
            Not connected — by design. This environment runs on simulated market data
            {data ? ` (provider: ${data.market_provider})` : ''}.
          </p>
        </div>
      </div>

      {/* Services grid */}
      <h2 className="mb-3 text-sm font-semibold text-content">Services</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {(data?.services ?? []).map((s) => (
          <ServiceCard key={s.name} service={s} />
        ))}
      </div>

      {/* Pipeline (proves mock market data end-to-end) */}
      {data ? (
        <div className="mt-6 rounded-md border border-surface-border bg-surface-raised p-4">
          <h2 className="mb-3 text-sm font-semibold text-content">Market-data pipeline</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
            <div>
              <dt className="text-content-muted">Provider</dt>
              <dd className="text-content">{data.pipeline.provider ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-content-muted">Session</dt>
              <dd className="text-content">{data.pipeline.market_status ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-content-muted">Live symbols</dt>
              <dd className="tabular-nums text-content">{data.pipeline.live_symbols ?? 0}</dd>
            </div>
            <div>
              <dt className="text-content-muted">Freshest quote</dt>
              <dd className="tabular-nums text-content">
                {data.pipeline.freshest_quote_age_seconds != null
                  ? `${data.pipeline.freshest_quote_age_seconds}s ago`
                  : '—'}
              </dd>
            </div>
          </dl>
        </div>
      ) : null}

      {/* Footer */}
      {data ? (
        <p className="mt-6 text-xs text-content-muted">
          v{data.version} · env {data.environment} · updated{' '}
          {lastFetchAt ? new Date(lastFetchAt).toLocaleTimeString() : '—'} · auto-refresh 5s
        </p>
      ) : null}
    </main>
  );
}
