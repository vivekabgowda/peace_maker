import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils';

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-md border border-surface-border bg-surface-raised p-5 shadow-sm',
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ title, subtitle }: { title: string; subtitle?: ReactNode }) {
  return (
    <div className="mb-4">
      <h2 className="text-sm font-semibold text-content">{title}</h2>
      {subtitle ? <p className="mt-0.5 text-xs text-content-muted">{subtitle}</p> : null}
    </div>
  );
}
