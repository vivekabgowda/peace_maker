import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';

export default function SettingsPage() {
  return (
    <div>
      <PageHeader title="Settings" description="Profile, risk limits, and notification preferences." />
      <EmptyState
        title="Settings — arriving in Sprint 2"
        description="Sprint 1 delivers the foundation (auth, shell, navigation). This module's UI lands in Sprint 2 per the roadmap."
      />
    </div>
  );
}
