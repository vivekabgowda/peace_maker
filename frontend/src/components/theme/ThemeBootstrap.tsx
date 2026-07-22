'use client';

import { useEffect } from 'react';

import { applyAccent, storedAccent } from '@/lib/theme/accent';

/**
 * Applies the user's persisted accent colour on first paint so the UI doesn't
 * flash the default blue before the profile loads. Renders nothing.
 */
export function ThemeBootstrap() {
  useEffect(() => {
    applyAccent(storedAccent());
  }, []);
  return null;
}
