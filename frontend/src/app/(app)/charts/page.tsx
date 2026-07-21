import { PageHeader } from '@/components/layout/PageHeader';
import { ChartView } from '@/features/charts/ChartView';

export default function ChartsPage() {
  return (
    <div>
      <PageHeader
        title="Charts"
        description="Candlesticks, volume, EMA 20/50, and your paper-trade markers."
      />
      <ChartView />
    </div>
  );
}
