import type { ReactNode } from 'react';

/** A designed placeholder for module pages that have no content yet (Sprint 1). */
export function EmptyState({
  title,
  description,
  badge = 'Coming soon',
  children,
}: {
  title: string;
  description: string;
  badge?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center rounded-md border border-dashed border-surface-border bg-surface-raised/40 p-10 text-center">
      <span className="mb-3 rounded-full border border-surface-border px-3 py-1 text-xs font-medium text-content-muted">
        {badge}
      </span>
      <h2 className="text-lg font-semibold text-content">{title}</h2>
      <p className="mt-2 max-w-md text-sm text-content-muted">{description}</p>
      {children}
    </div>
  );
}
