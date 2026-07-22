import { apiFetch } from '@/lib/api/client';
import type { Preferences, User } from '@/types';

/** Current authenticated user, including profile + preferences. */
export const getMe = () => apiFetch<User>('/me', { auth: true });

export interface ProfilePatch {
  display_name?: string | null;
  trading_capital?: string;
  timezone?: string;
  preferences?: Preferences;
}

/** Update profile fields and/or the full preferences object. */
export const updateProfile = (patch: ProfilePatch) =>
  apiFetch<User>('/me/profile', { method: 'PATCH', body: patch, auth: true });

export const changePassword = (current_password: string, new_password: string) =>
  apiFetch<void>('/auth/change-password', {
    method: 'POST',
    body: { current_password, new_password },
    auth: true,
  });

/** Revoke every refresh token for the account ("logout everywhere"). */
export const logoutAll = () => apiFetch<void>('/auth/logout-all', { method: 'POST', auth: true });

/** Revoke just the current session. */
export const logout = () => apiFetch<void>('/auth/logout', { method: 'POST', auth: true });
