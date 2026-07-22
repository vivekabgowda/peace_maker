import { PageHeader } from '@/components/layout/PageHeader';
import { AdminGuard } from '@/features/admin/AdminGuard';
import { AdminView } from '@/features/admin/AdminView';

export default function AdminPage() {
  return (
    <div>
      <PageHeader
        title="Admin"
        description="System health, users & roles, AI committee configuration, logs and audit trail."
      />
      <AdminGuard>
        <AdminView />
      </AdminGuard>
    </div>
  );
}
