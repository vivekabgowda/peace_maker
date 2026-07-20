'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';

import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader } from '@/components/ui/Card';
import { fetchMe } from '@/lib/auth/api';
import { useAuthStore } from '@/stores/authStore';

const PANELS = [
  { title: 'Market Regime', body: 'Live market intelligence arrives in Sprint 6.' },
  {
    title: 'Top Recommendations',
    body: 'The risk-gated recommendation feed arrives in Sprint 12.',
  },
  {
    title: 'Portfolio Snapshot',
    body: 'Holdings, P&L, and risk-budget gauges arrive in Sprint 16.',
  },
];

export default function DashboardPage() {
  const setUser = useAuthStore((s) => s.setUser);
  const { data: user } = useQuery({ queryKey: ['me'], queryFn: fetchMe });

  useEffect(() => {
    if (user) setUser(user);
  }, [user, setUser]);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description={
          user ? `Welcome back, ${user.profile?.display_name ?? user.email}` : 'Loading…'
        }
      />
      <div className="grid gap-4 md:grid-cols-3">
        {PANELS.map((panel) => (
          <Card key={panel.title}>
            <CardHeader title={panel.title} subtitle="Coming soon" />
            <p className="text-sm text-content-muted">{panel.body}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
