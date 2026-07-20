import { apiFetch } from '@/lib/api/client';
import type { TokenPair, User } from '@/types';

interface RegisterResponse {
  user: User;
  tokens: TokenPair;
}

export function login(email: string, password: string): Promise<TokenPair> {
  return apiFetch<TokenPair>('/auth/login', { method: 'POST', body: { email, password } });
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

export function logout(refreshToken: string): Promise<void> {
  return apiFetch<void>('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } });
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>('/me', { auth: true });
}
