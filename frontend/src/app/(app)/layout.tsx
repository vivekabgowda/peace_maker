'use client';

import { useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';

import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { refresh } from '@/lib/auth/api';
import { useAuthStore } from '@/stores/authStore';

/**
 * Protected application shell.
 *
 * On load the access token is not in memory (nothing is persisted — R1), so we
 * attempt a silent /auth/refresh using the httpOnly cookie. If that fails, the
 * user is redirected to sign in.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, bootstrapped, setSession, setBootstrapped } = useAuthStore();

  useEffect(() => {
    if (bootstrapped) return;
    let active = true;
    refresh()
      .then((tokens) => {
        if (active) setSession(tokens.access_token);
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setBootstrapped(true);
      });
    return () => {
      active = false;
    };
  }, [bootstrapped, setSession, setBootstrapped]);

  useEffect(() => {
    if (bootstrapped && !isAuthenticated) router.replace('/login');
  }, [bootstrapped, isAuthenticated, router]);

  if (!bootstrapped || !isAuthenticated) {
    return (
      <div className="grid min-h-screen place-items-center text-sm text-content-muted">
        {bootstrapped ? 'Redirecting to sign in…' : 'Restoring your session…'}
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
