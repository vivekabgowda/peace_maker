import { PageHeader } from '@/components/layout/PageHeader';
import { EmptyState } from '@/components/ui/EmptyState';

export default function ScannerPage() {
  return (
    <div>
      <PageHeader title="Scanner" description="Continuous market scanning and candidate setups." />
      <EmptyState
        title="Scanner — arriving in Sprint 9"
        description="Sprint 1 delivers the foundation (auth, shell, navigation). This module's UI lands in Sprint 9 per the roadmap."
      />
    </div>
  );
}
