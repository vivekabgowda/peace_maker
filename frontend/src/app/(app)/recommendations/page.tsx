import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';

export default function RecommendationsPage() {
  return (
    <div>
      <PageHeader
        title="Recommendations"
        description="Ranked, risk-gated, explainable trade ideas."
      />
      <EmptyState
        title="Recommendations — arriving in Sprint 12"
        description="Sprint 1 delivers the foundation (auth, shell, navigation). This module's UI lands in Sprint 12 per the roadmap."
      />
    </div>
  );
}
