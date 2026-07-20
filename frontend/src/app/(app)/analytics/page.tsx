import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';

export default function AnalyticsPage() {
  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Performance, attribution, and behavior analytics."
      />
      <EmptyState
        title="Analytics — arriving in Sprint 17"
        description="Sprint 1 delivers the foundation (auth, shell, navigation). This module's UI lands in Sprint 17 per the roadmap."
      />
    </div>
  );
}
