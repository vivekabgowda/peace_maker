'use client';

import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/Button';
import { logout as logoutRequest } from '@/lib/auth/api';
import { useAuthStore } from '@/stores/authStore';

/** Static index tickers until live market data lands (Sprint 6). */
const TICKERS = [
  { symbol: 'NIFTY', value: '—' },
  { symbol: 'BANKNIFTY', value: '—' },
  { symbol: 'SENSEX', value: '—' },
  { symbol: 'INDIA VIX', value: '—' },
];

export function Topbar() {
  const router = useRouter();
  const { user, refreshToken, clear } = useAuthStore();

  async function handleLogout() {
    if (refreshToken) {
      await logoutRequest(refreshToken).catch(() => undefined);
    }
    clear();
    router.push('/login');
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-surface-border bg-surface-raised px-5">
      <div className="flex items-center gap-4 overflow-x-auto text-xs">
        {TICKERS.map((t) => (
          <span key={t.symbol} className="flex items-center gap-1.5 whitespace-nowrap">
            <span className="text-content-faint">{t.symbol}</span>
            <span className="tabular text-content-muted">{t.value}</span>
          </span>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden text-xs text-content-muted sm:inline">{user?.email}</span>
        <Button variant="ghost" onClick={handleLogout}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
