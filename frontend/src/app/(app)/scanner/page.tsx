import { PageHeader } from '@/components/layout/PageHeader';
import { ScannerView } from '@/features/scanner/ScannerView';

export default function ScannerPage() {
  return (
    <div>
      <PageHeader
        title="Scanner"
        description="Ranked, risk-gated setups from the Alpha Engine — with a NO-TRADE verdict when warranted."
      />
      <ScannerView />
    </div>
  );
}
