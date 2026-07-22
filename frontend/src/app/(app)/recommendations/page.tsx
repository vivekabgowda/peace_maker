import { PageHeader } from '@/components/layout/PageHeader';
import { RecommendationsView } from '@/features/recommendations/RecommendationsView';

export default function RecommendationsPage() {
  return (
    <div>
      <PageHeader
        title="Recommendations"
        description="Ranked, risk-gated trade ideas with the AI committee's vote and reasoning."
      />
      <RecommendationsView />
    </div>
  );
}
