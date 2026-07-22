'use client';

import { useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';

import { Card } from '@/components/ui/Card';
import { useAuthStore } from '@/stores/authStore';

/**
 * Client-side defence-in-depth for the admin area. The backend already enforces
 * the admin role on every /admin API (returning 403), and the nav hides the
 * link for non-admins — this additionally keeps a non-admin who navigates
 * directly to /admin from seeing the shell, redirecting them to the dashboard.
 */
export function AdminGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    if (user && user.role !== 'admin') router.replace('/dashboard');
  }, [user, router]);

  if (!user) {
    return <Card className="text-sm text-content-muted">Checking permissions…</Card>;
  }
  if (user.role !== 'admin') {
    return (
      <Card className="text-sm text-content-muted">
        You don&apos;t have access to this area. Redirecting…
      </Card>
    );
  }
  return <>{children}</>;
}
