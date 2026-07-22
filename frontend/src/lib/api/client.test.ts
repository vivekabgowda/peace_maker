import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiRequestError, apiFetch } from '@/lib/api/client';
import { useAuthStore } from '@/stores/authStore';

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

afterEach(() => {
  vi.restoreAllMocks();
  useAuthStore.getState().clear();
});

describe('apiFetch', () => {
  it('parses a successful JSON response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, { hello: 'world' })));
    await expect(apiFetch<{ hello: string }>('/x')).resolves.toEqual({ hello: 'world' });
  });

  it('returns undefined for a 204 No Content', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 204 } as Response));
    await expect(apiFetch<void>('/x', { method: 'POST' })).resolves.toBeUndefined();
  });

  it('maps the error envelope to ApiRequestError on 4xx', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(422, { error: { code: 'validation_error', message: 'bad', details: {} } }),
        ),
    );
    await expect(apiFetch('/x')).rejects.toMatchObject({
      status: 422,
      code: 'validation_error',
      message: 'bad',
    });
  });

  it('surfaces a network failure as ApiRequestError status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const err = (await apiFetch('/x').catch((e) => e)) as ApiRequestError;
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err.status).toBe(0);
    expect(err.code).toBe('network_error');
  });

  it('maps an aborted (timed-out) request to a timeout error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')));
    const err = (await apiFetch('/x', { timeoutMs: 5 }).catch((e) => e)) as ApiRequestError;
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err.code).toBe('timeout');
  });

  it('attaches the bearer token when auth is requested', async () => {
    useAuthStore.getState().setSession('tok-123');
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}));
    vi.stubGlobal('fetch', fetchMock);
    await apiFetch('/secure', { auth: true });
    const headers = (fetchMock.mock.calls[0]?.[1] as RequestInit).headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer tok-123');
  });

  it('does not attach a token when auth is not requested', async () => {
    useAuthStore.getState().setSession('tok-123');
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, {}));
    vi.stubGlobal('fetch', fetchMock);
    await apiFetch('/public');
    const headers = (fetchMock.mock.calls[0]?.[1] as RequestInit).headers as Headers;
    expect(headers.get('Authorization')).toBeNull();
  });
});
