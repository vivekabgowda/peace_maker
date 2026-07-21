import { PageHeader } from '@/components/layout/PageHeader';
import { AnalyticsView } from '@/features/analytics/AnalyticsView';

export default function AnalyticsPage() {
  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Performance, expectancy, drawdown, and per-strategy attribution."
      />
      <AnalyticsView />
    </div>
  );
}
