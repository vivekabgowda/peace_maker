'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

import { NAV_ITEMS } from '@/lib/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';

/**
 * Mobile/tablet navigation. The sidebar is hidden below `md`, so this hamburger
 * + slide-in drawer provides navigation on small screens. Closes on route
 * change, backdrop click, or Escape.
 */
export function MobileNav() {
  const pathname = usePathname();
  const role = useAuthStore((s) => s.user?.role);
  const [open, setOpen] = useState(false);

  const items = NAV_ITEMS.filter((item) => !item.adminOnly || role === 'admin');

  // Close when the route changes.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Close on Escape and lock body scroll while open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        aria-label="Open navigation"
        aria-expanded={open}
        onClick={() => setOpen(true)}
        className="grid h-9 w-9 place-items-center rounded-md text-content-muted hover:bg-surface-overlay hover:text-content"
      >
        <svg
          className="h-5 w-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.8}
          strokeLinecap="round"
          aria-hidden
        >
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 flex">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />
          <aside className="relative flex w-64 max-w-[80%] flex-col border-r border-surface-border bg-surface-raised">
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
        </div>
      ) : null}
    </div>
  );
}
