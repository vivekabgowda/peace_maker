import { PageHeader } from '@/components/layout/PageHeader';
import { ValidationView } from '@/features/validation/ValidationView';

export default function ValidationPage() {
  return (
    <div>
      <PageHeader
        title="Validation"
        description="Cost-aware backtests, walk-forward, deflated Sharpe, Monte Carlo — does the edge survive?"
      />
      <ValidationView />
    </div>
  );
}
