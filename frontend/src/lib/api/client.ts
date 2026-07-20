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
}

/**
 * Thin typed fetch wrapper around the backend API.
 *
 * Attaches the bearer token when `auth` is set, normalizes the error envelope
 * into `ApiRequestError`, and parses JSON responses.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, auth = false, headers, ...rest } = options;
  const finalHeaders = new Headers(headers);
  finalHeaders.set('Content-Type', 'application/json');

  if (auth) {
    const token = useAuthStore.getState().accessToken;
    if (token) finalHeaders.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
    // Send the httpOnly refresh cookie with auth requests (R1).
    credentials: 'include',
    body: body === undefined ? undefined : JSON.stringify(body),
  });

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
