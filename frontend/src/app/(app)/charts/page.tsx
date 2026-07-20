import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';

export default function ChartsPage() {
  return (
    <div>
      <PageHeader title="Charts" description="TradingView charts with platform indicators." />
      <EmptyState
        title="Charts — arriving in Sprint 6"
        description="Sprint 1 delivers the foundation (auth, shell, navigation). This module's UI lands in Sprint 6 per the roadmap."
      />
    </div>
  );
}
