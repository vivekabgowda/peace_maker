import { PageHeader } from '@/components/layout/PageHeader';
import { JournalView } from '@/features/journal/JournalView';

export default function JournalPage() {
  return (
    <div>
      <PageHeader
        title="Journal"
        description="Every closed paper trade — P&L, R-multiple, and outcome."
      />
      <JournalView />
    </div>
  );
}
