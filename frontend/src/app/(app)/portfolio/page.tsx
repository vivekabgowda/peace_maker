import { PageHeader } from '@/components/layout/PageHeader';
import { PortfolioView } from '@/features/portfolio/PortfolioView';

export default function PortfolioPage() {
  return (
    <div>
      <PageHeader
        title="Portfolio"
        description="Paper account summary, open positions, equity curve, allocation and risk."
      />
      <PortfolioView />
    </div>
  );
}
