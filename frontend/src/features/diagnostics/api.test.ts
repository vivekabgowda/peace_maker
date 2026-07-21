import { afterEach, describe, expect, it, vi } from 'vitest';

import { getDiagnostics } from '@/features/diagnostics/api';

const HEALTHY = {
  status: 'healthy',
  version: '0.1.0',
  environment: 'local',
  timestamp: '2026-07-21T00:00:00Z',
  market_provider: 'simulated',
  broker_connected: false,
  services: [
    { name: 'database', kind: 'sqlite', healthy: true, detail: 'ok', latency_ms: 1, meta: {} },
  ],
  pipeline: { provider: 'simulated', live_symbols: 3 },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe('getDiagnostics', () => {
  it('parses a healthy report', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ status: 200, json: () => Promise.resolve(HEALTHY) }),
    );
    const report = await getDiagnostics();
    expect(report.status).toBe('healthy');
    expect(report.broker_connected).toBe(false);
    expect(report.services[0]?.name).toBe('database');
  });

  it('still parses the body on a 503 degraded response', async () => {
    const degraded = { ...HEALTHY, status: 'degraded' };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ status: 503, json: () => Promise.resolve(degraded) }),
    );
    const report = await getDiagnostics();
    expect(report.status).toBe('degraded');
  });

  it('throws when the body is not a valid diagnostics payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ status: 502, json: () => Promise.resolve(null) }),
    );
    await expect(getDiagnostics()).rejects.toThrow(/unexpected response/);
  });
});
