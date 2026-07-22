'use client';

import dynamic from 'next/dynamic';

import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';

// The chart pulls in the ~50kB lightweight-charts library; load it only when
// this page mounts (client-side) so it never weighs on other routes.
const ChartView = dynamic(() => import('@/features/charts/ChartView').then((m) => m.ChartView), {
  ssr: false,
  loading: () => <Card className="text-sm text-content-muted">Loading chart…</Card>,
});

export default function ChartsPage() {
  return (
    <div>
      <PageHeader
        title="Charts"
        description="Candlesticks, volume, EMA 20/50, and your paper-trade markers."
      />
      <ChartView />
    </div>
  );
}
