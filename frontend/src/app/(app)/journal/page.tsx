import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';

export default function JournalPage() {
  return (
    <div>
      <PageHeader title="Journal" description="Trade journal and behavioral insights." />
      <EmptyState
        title="Journal — arriving in Sprint 16"
        description="Sprint 1 delivers the foundation (auth, shell, navigation). This module's UI lands in Sprint 16 per the roadmap."
      />
    </div>
  );
}
