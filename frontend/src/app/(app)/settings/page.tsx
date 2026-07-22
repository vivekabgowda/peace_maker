import { PageHeader } from '@/components/layout/PageHeader';
import { SettingsView } from '@/features/settings/SettingsView';

export default function SettingsPage() {
  return (
    <div>
      <PageHeader
        title="Settings"
        description="Profile, trading defaults, notifications, appearance, and security."
      />
      <SettingsView />
    </div>
  );
}
