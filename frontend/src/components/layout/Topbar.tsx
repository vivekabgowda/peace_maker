'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { MobileNav } from '@/components/layout/MobileNav';
import { Button } from '@/components/ui/Button';
import { getIndices, type Quote } from '@/features/market/api';
import { logout as logoutRequest } from '@/lib/auth/api';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';

/** Header ticker strip: real index quotes (Nifty, Bank Nifty, Sensex, VIX). */
const HEADER_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'SENSEX', 'INDIAVIX'];
const LABELS: Record<string, string> = { INDIAVIX: 'INDIA VIX' };

function TickerStrip() {
  // Shares the ['indices'] cache with the dashboard, so this adds no extra
  // request while on the dashboard and one lightweight poll elsewhere.
  const { data } = useQuery({
    queryKey: ['indices'],
    queryFn: getIndices,
    refetchInterval: 30000,
  });

  const bySymbol = new Map((data ?? []).map((q) => [q.symbol, q]));

  return (
    <div className="flex items-center gap-4 overflow-x-auto text-xs">
      {HEADER_SYMBOLS.map((symbol) => {
        const quote: Quote | undefined = bySymbol.get(symbol);
        const changePct = quote?.change_pct ?? null;
        const ltp = quote && quote.ltp !== '' ? Number(quote.ltp) : null;
        return (
          <span key={symbol} className="flex items-center gap-1.5 whitespace-nowrap">
            <span className="text-content-faint">{LABELS[symbol] ?? symbol}</span>
            <span className="tabular text-content-muted">
              {ltp != null && !Number.isNaN(ltp) ? ltp.toLocaleString('en-IN') : '—'}
            </span>
            {changePct != null ? (
              <span
                className={cn(
                  'tabular',
                  changePct > 0 ? 'text-gain' : changePct < 0 ? 'text-loss' : 'text-content-faint',
                )}
              >
                {changePct > 0 ? '+' : ''}
                {changePct.toFixed(2)}%
              </span>
            ) : null}
          </span>
        );
      })}
    </div>
  );
}

export function Topbar() {
  const router = useRouter();
  const { user, clear } = useAuthStore();

  async function handleLogout() {
    await logoutRequest().catch(() => undefined);
    clear();
    router.push('/login');
  }

  return (
    <header className="flex h-14 items-center justify-between gap-3 border-b border-surface-border bg-surface-raised px-4 sm:px-5">
      <div className="flex min-w-0 items-center gap-2">
        <MobileNav />
        <TickerStrip />
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span className="hidden max-w-[12rem] truncate text-xs text-content-muted sm:inline">
          {user?.email}
        </span>
        <Button variant="ghost" onClick={handleLogout}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
