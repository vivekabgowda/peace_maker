'use client';

import { create } from 'zustand';

import type { User } from '@/types';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  bootstrapped: boolean;
  setSession: (accessToken: string, user?: User | null) => void;
  setUser: (user: User | null) => void;
  setBootstrapped: (value: boolean) => void;
  clear: () => void;
}

/**
 * Client-side auth store.
 *
 * SECURITY (R1): tokens are held **in memory only** and never persisted. The
 * refresh token lives in an httpOnly cookie the browser sends automatically;
 * on load the app calls /auth/refresh to obtain a fresh in-memory access token.
 * This removes the XSS-exfiltration risk of storing tokens in localStorage.
 */
export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  bootstrapped: false,
  setSession: (accessToken, user = null) =>
    set((s) => ({ accessToken, isAuthenticated: true, user: user ?? s.user })),
  setUser: (user) => set({ user }),
  setBootstrapped: (value) => set({ bootstrapped: value }),
  clear: () => set({ user: null, accessToken: null, isAuthenticated: false }),
}));
