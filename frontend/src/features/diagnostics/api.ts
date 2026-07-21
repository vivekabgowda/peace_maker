const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? '/api/v1';

export interface ServiceStatus {
  name: string;
  kind: string;
  healthy: boolean;
  detail: string;
  latency_ms: number | null;
  meta: Record<string, unknown>;
}

export interface Diagnostics {
  status: 'healthy' | 'degraded';
  version: string;
  environment: string;
  timestamp: string;
  market_provider: string;
  broker_connected: boolean;
  services: ServiceStatus[];
  pipeline: {
    provider?: string;
    market_status?: string | null;
    live_symbols?: number;
    freshest_quote_age_seconds?: number | null;
  };
}

/**
 * Fetch the system diagnostics. Unauthenticated, and — unlike the standard API
 * client — it parses the JSON body even on 503 (a "degraded" diagnostics report
 * is still a valid, useful body), throwing only on a genuine network/parse error
 * so the page can distinguish "backend degraded" from "backend unreachable".
 */
export async function getDiagnostics(): Promise<Diagnostics> {
  const response = await fetch(`${BASE_URL}/health/diagnostics`, {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  });
  const payload = (await response.json().catch(() => null)) as Diagnostics | null;
  if (!payload || !Array.isArray(payload.services)) {
    throw new Error(
      `Diagnostics endpoint returned an unexpected response (HTTP ${response.status})`,
    );
  }
  return payload;
}
