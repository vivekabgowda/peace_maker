'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { TokenPair, User } from '@/types';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setSession: (tokens: TokenPair, user?: User | null) => void;
  setUser: (user: User | null) => void;
  clear: () => void;
}

/**
 * Client-side auth store.
 *
 * Sprint 1 keeps tokens in a persisted store for a working end-to-end flow.
 * A later sprint moves the refresh token to an httpOnly cookie (see
 * docs/12-security-compliance.md) and keeps only the access token in memory.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      setSession: (tokens, user = null) =>
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          user,
          isAuthenticated: true,
        }),
      setUser: (user) => set({ user }),
      clear: () =>
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false }),
    }),
    { name: 'bkn-auth' },
  ),
);
