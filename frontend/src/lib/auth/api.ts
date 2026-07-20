import { apiFetch } from '@/lib/api/client';
import type { User } from '@/types';

interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

interface RegisterResponse {
  user: User;
  tokens: AccessTokenResponse;
}

export function login(email: string, password: string): Promise<AccessTokenResponse> {
  return apiFetch<AccessTokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
  });
}

export function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>('/auth/register', {
    method: 'POST',
    body: { email, password, display_name: displayName },
  });
}

/** Restore an access token from the httpOnly refresh cookie (session bootstrap). */
export function refresh(): Promise<AccessTokenResponse> {
  return apiFetch<AccessTokenResponse>('/auth/refresh', { method: 'POST' });
}

export function logout(): Promise<void> {
  return apiFetch<void>('/auth/logout', { method: 'POST' });
}

/** Obtain a short-lived, single-use ticket to authenticate the WebSocket. */
export function fetchWsTicket(): Promise<{ ticket: string; expires_in: number }> {
  return apiFetch<{ ticket: string; expires_in: number }>('/auth/ws-ticket', {
    method: 'POST',
    auth: true,
  });
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>('/me', { auth: true });
}
