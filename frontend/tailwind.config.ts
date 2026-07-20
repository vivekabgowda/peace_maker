import type { Config } from 'tailwindcss';

/**
 * BKN AI Capital design tokens. Dark-first, institutional terminal palette.
 * Semantic colors (long/gain = green, short/loss = red) are never the only
 * signal — always paired with an icon or label in components (accessibility).
 */
const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0d1117',
          raised: '#161b22',
          overlay: '#1c2230',
          border: '#2a3140',
        },
        content: {
          DEFAULT: '#e6edf3',
          muted: '#8b98a9',
          faint: '#5b6472',
        },
        accent: {
          DEFAULT: '#1f6feb',
          hover: '#388bfd',
        },
        gain: '#26a269',
        loss: '#e5484d',
        caution: '#e3b341',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        md: '6px',
      },
    },
  },
  plugins: [],
};

export default config;
