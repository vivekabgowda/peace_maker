'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

import { ThemeBootstrap } from '@/components/theme/ThemeBootstrap';
import { ApiRequestError } from '@/lib/api/client';

/** App-wide client providers (TanStack Query + runtime theme). */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Retry transient failures (network/timeout/5xx) but never a 4xx —
            // an auth or validation error will not fix itself on retry.
            retry: (failureCount, error) => {
              if (error instanceof ApiRequestError && error.status >= 400 && error.status < 500) {
                return false;
              }
              return failureCount < 2;
            },
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeBootstrap />
      {children}
    </QueryClientProvider>
  );
}
