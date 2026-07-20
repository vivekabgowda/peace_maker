import { describe, expect, it } from 'vitest';

import { cn, formatINR, formatPct } from '@/lib/utils';

describe('cn', () => {
  it('merges and dedupes tailwind classes', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
    expect(cn('text-sm', false && 'hidden', 'font-bold')).toBe('text-sm font-bold');
  });
});

describe('formatINR', () => {
  it('formats rupees', () => {
    expect(formatINR(500000)).toContain('5,00,000');
    expect(formatINR(500000)).toContain('₹');
  });
});

describe('formatPct', () => {
  it('adds a sign', () => {
    expect(formatPct(1.23)).toBe('+1.23%');
    expect(formatPct(-0.5)).toBe('-0.50%');
  });
});
