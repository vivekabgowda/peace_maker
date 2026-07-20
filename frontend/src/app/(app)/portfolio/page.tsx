import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';

export default function PortfolioPage() {
  return (
    <div>
      <PageHeader title="Portfolio" description="Holdings, P&L, exposure and portfolio heat." />
      <EmptyState
        title="Portfolio — arriving in Sprint 16"
        description="Sprint 1 delivers the foundation (auth, shell, navigation). This module's UI lands in Sprint 16 per the roadmap."
      />
    </div>
  );
}
