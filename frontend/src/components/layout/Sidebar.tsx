'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { NAV_ITEMS } from '@/lib/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';

export function Sidebar() {
  const pathname = usePathname();
  const role = useAuthStore((s) => s.user?.role);

  const items = NAV_ITEMS.filter((item) => !item.adminOnly || role === 'admin');

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-surface-border bg-surface-raised md:flex">
      <div className="flex h-14 items-center gap-2 border-b border-surface-border px-5">
        <span className="grid h-7 w-7 place-items-center rounded bg-accent text-xs font-bold text-white">
          BKN
        </span>
        <span className="text-sm font-semibold tracking-tight">AI Capital</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-accent/15 text-content'
                  : 'text-content-muted hover:bg-surface-overlay hover:text-content',
              )}
            >
              <svg
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.8}
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d={item.icon} />
              </svg>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-surface-border p-3 text-[10px] leading-relaxed text-content-faint">
        Advisory only · No trade execution in V1
      </div>
    </aside>
  );
}
