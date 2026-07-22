'use client';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

/**
 * Error boundary for the authenticated app shell. A render error in any page
 * is caught here and shown inside the existing chrome (sidebar/topbar remain),
 * with a recover action — no full-page crash.
 */
export default function AppError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-lg py-12">
      <Card>
        <h1 className="text-base font-semibold text-content">This page hit an error</h1>
        <p className="mt-2 text-sm text-content-muted">
          Something went wrong while rendering this view. The rest of the app is still working — you
          can retry, or navigate elsewhere.
        </p>
        {error.message ? (
          <p className="mt-3 rounded-md border border-surface-border bg-surface p-3 text-xs text-content-faint">
            {error.message}
          </p>
        ) : null}
        <div className="mt-4">
          <Button onClick={reset}>Try again</Button>
        </div>
      </Card>
    </div>
  );
}
