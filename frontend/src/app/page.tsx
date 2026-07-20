'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { useAuthStore } from '@/stores/authStore';

/** Entry point: route to the dashboard or the login screen. */
export default function Home() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    router.replace(isAuthenticated ? '/dashboard' : '/login');
  }, [isAuthenticated, router]);

  return (
    <div className="grid min-h-screen place-items-center text-sm text-content-muted">
      Loading BKN AI Capital…
    </div>
  );
}
