import { useAuthStore } from '@/stores/authStore';
import type { ApiError } from '@/types';

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? '/api/v1';

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  auth?: boolean;
  /** Abort the request after this many ms (default 15s). */
  timeoutMs?: number;
}

/** Default per-request timeout — a hung network must not hang the UI forever. */
const DEFAULT_TIMEOUT_MS = 15000;

/**
 * Thin typed fetch wrapper around the backend API.
 *
 * Attaches the bearer token when `auth` is set, enforces a request timeout,
 * normalizes the error envelope into `ApiRequestError`, and parses JSON
 * responses. Network failures and timeouts surface as `ApiRequestError` with a
 * `status` of 0 so callers can render a friendly message instead of crashing.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, auth = false, headers, timeoutMs = DEFAULT_TIMEOUT_MS, signal, ...rest } = options;
  const finalHeaders = new Headers(headers);
  finalHeaders.set('Content-Type', 'application/json');

  if (auth) {
    const token = useAuthStore.getState().accessToken;
    if (token) finalHeaders.set('Authorization', `Bearer ${token}`);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  // Honour a caller-supplied abort signal alongside the timeout.
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...rest,
      headers: finalHeaders,
      // Send the httpOnly refresh cookie with auth requests (R1).
      credentials: 'include',
      signal: controller.signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === 'AbortError';
    throw new ApiRequestError(
      0,
      aborted ? 'timeout' : 'network_error',
      aborted
        ? 'The request timed out. Please check your connection and try again.'
        : 'Could not reach the server. Please check your connection.',
    );
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const err = (payload as ApiError | null)?.error;
    throw new ApiRequestError(
      response.status,
      err?.code ?? 'unknown_error',
      err?.message ?? 'Request failed',
      err?.details ?? {},
    );
  }

  return payload as T;
}
