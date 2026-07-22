/** Primary navigation — mirrors the module pages in docs/09-frontend-ui.md. */

export interface NavItem {
  label: string;
  href: string;
  /** Inline SVG path data for a 24x24 icon (stroke-based). */
  icon: string;
  adminOnly?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: 'M3 12l9-9 9 9M5 10v10h14V10' },
  { label: 'Scanner', href: '/scanner', icon: 'M4 6h16M4 12h10M4 18h7' },
  { label: 'Charts', href: '/charts', icon: 'M4 19V5m0 14h16M8 15l3-3 3 2 4-5' },
  {
    label: 'Recommendations',
    href: '/recommendations',
    icon: 'M12 3l2.5 5 5.5.8-4 3.9 1 5.5L12 16l-5 2.6 1-5.5-4-3.9 5.5-.8z',
  },
  { label: 'Portfolio', href: '/portfolio', icon: 'M3 7h18v12H3zM3 7l3-3h12l3 3' },
  { label: 'Journal', href: '/journal', icon: 'M5 4h11l3 3v13H5zM8 9h8M8 13h8M8 17h5' },
  { label: 'Analytics', href: '/analytics', icon: 'M4 19h16M7 16v-5m5 5V7m5 9v-8' },
  {
    label: 'Validation',
    href: '/validation',
    icon: 'M9 12l2 2 4-4M12 3l7 4v5c0 5-3.5 8-7 9-3.5-1-7-4-7-9V7z',
  },
  { label: 'Diagnostics', href: '/diagnostics', icon: 'M3 12h4l2 5 4-14 2 9h6' },
  {
    label: 'Settings',
    href: '/settings',
    icon: 'M12 8a4 4 0 100 8 4 4 0 000-8zM3 12h2m14 0h2M12 3v2m0 14v2',
  },
  {
    label: 'Admin',
    href: '/admin',
    icon: 'M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z',
    adminOnly: true,
  },
];
