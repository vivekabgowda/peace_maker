/**
 * Runtime accent-colour theming.
 *
 * The accent is a CSS variable (`--accent-rgb`) consumed by Tailwind's
 * `accent` colour token. Users pick their accent in Settings → Appearance; the
 * choice is persisted to the backend (profile preferences) and mirrored to
 * localStorage so it can be applied instantly on the next load, before the
 * profile round-trips.
 */

export const ACCENT_STORAGE_KEY = 'bkn.accent';
export const DEFAULT_ACCENT = '#1f6feb';

/** Curated accent palette. Any 6-digit hex is accepted by the backend. */
export const ACCENT_PRESETS: { label: string; value: string }[] = [
  { label: 'Blue', value: '#1f6feb' },
  { label: 'Green', value: '#26a269' },
  { label: 'Amber', value: '#e3b341' },
  { label: 'Red', value: '#e5484d' },
  { label: 'Purple', value: '#8957e5' },
  { label: 'Teal', value: '#2dd4bf' },
];

const HEX6 = /^#[0-9a-fA-F]{6}$/;

export function isValidAccent(hex: string): boolean {
  return HEX6.test(hex);
}

function toRgb(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b];
}

/** Lighten a channel toward white by `amount` (0–1) for the hover shade. */
function lighten(channel: number, amount: number): number {
  return Math.round(channel + (255 - channel) * amount);
}

/**
 * Apply an accent hex to the document by setting the CSS variables. Invalid
 * values are ignored (the default stays in effect).
 */
export function applyAccent(hex: string): void {
  if (typeof document === 'undefined' || !isValidAccent(hex)) return;
  const [r, g, b] = toRgb(hex);
  const hover: [number, number, number] = [lighten(r, 0.22), lighten(g, 0.22), lighten(b, 0.22)];
  const root = document.documentElement;
  root.style.setProperty('--accent-rgb', `${r} ${g} ${b}`);
  root.style.setProperty('--accent-hover-rgb', `${hover[0]} ${hover[1]} ${hover[2]}`);
}

/** Persist the accent locally and apply it immediately. */
export function setAccent(hex: string): void {
  if (!isValidAccent(hex)) return;
  applyAccent(hex);
  try {
    localStorage.setItem(ACCENT_STORAGE_KEY, hex);
  } catch {
    // Storage may be unavailable (private mode); the in-memory apply still works.
  }
}

/** Read the persisted accent, falling back to the default. */
export function storedAccent(): string {
  try {
    const value = localStorage.getItem(ACCENT_STORAGE_KEY);
    if (value && isValidAccent(value)) return value;
  } catch {
    // ignore
  }
  return DEFAULT_ACCENT;
}
