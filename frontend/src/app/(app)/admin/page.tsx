import { PageHeader } from '@/components/layout/PageHeader';
import { AdminView } from '@/features/admin/AdminView';

export default function AdminPage() {
  return (
    <div>
      <PageHeader
        title="Admin"
        description="System health, users & roles, AI committee configuration, logs and audit trail."
      />
      <AdminView />
    </div>
  );
}
