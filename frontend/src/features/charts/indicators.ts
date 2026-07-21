/**
 * Exponential moving average over a series of closes.
 * Returns an array aligned to the input; entries before the seed period are null.
 * Derived from real candle closes — not mock data.
 */
export function ema(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  const k = 2 / (period + 1);
  let prev = 0;
  let seeded = false;
  values.forEach((v, i) => {
    if (i < period - 1) {
      out.push(null);
      return;
    }
    if (!seeded) {
      const seed = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
      prev = seed;
      seeded = true;
      out.push(seed);
      return;
    }
    prev = v * k + prev * (1 - k);
    out.push(prev);
  });
  return out;
}
