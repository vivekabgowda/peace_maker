import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';

export default function AdminPage() {
  return (
    <div>
      <PageHeader title="Admin" description="User management, feature flags, and agent configuration." />
      <EmptyState
        title="Admin — arriving in Sprint 15"
        description="Sprint 1 delivers the foundation (auth, shell, navigation). This module's UI lands in Sprint 15 per the roadmap."
      />
    </div>
  );
}
