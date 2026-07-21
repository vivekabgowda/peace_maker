'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';

import { PageHeader } from '@/components/layout/PageHeader';
import { LiveDashboard } from '@/features/market/LiveDashboard';
import { fetchMe } from '@/lib/auth/api';
import { useAuthStore } from '@/stores/authStore';

export default function DashboardPage() {
  const setUser = useAuthStore((s) => s.setUser);
  const { data: user } = useQuery({ queryKey: ['me'], queryFn: fetchMe });

  useEffect(() => {
    if (user) setUser(user);
  }, [user, setUser]);

  return (
    <div>
      <PageHeader
        title="Live Market Dashboard"
        description={
          user ? `Welcome back, ${user.profile?.display_name ?? user.email}` : 'Loading…'
        }
      />
      <LiveDashboard />
    </div>
  );
}
