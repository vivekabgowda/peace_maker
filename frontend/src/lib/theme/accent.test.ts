import { describe, expect, it } from 'vitest';

import { DEFAULT_ACCENT, isValidAccent } from './accent';

describe('isValidAccent', () => {
  it('accepts 6-digit hex colours', () => {
    expect(isValidAccent('#1f6feb')).toBe(true);
    expect(isValidAccent('#ABCDEF')).toBe(true);
    expect(isValidAccent(DEFAULT_ACCENT)).toBe(true);
  });

  it('rejects malformed values', () => {
    expect(isValidAccent('1f6feb')).toBe(false); // missing #
    expect(isValidAccent('#fff')).toBe(false); // 3-digit shorthand
    expect(isValidAccent('#1f6fe')).toBe(false); // 5 digits
    expect(isValidAccent('#1f6fegg')).toBe(false); // non-hex
    expect(isValidAccent('')).toBe(false);
  });
});
