import type { Metadata, Viewport } from 'next';

import { Providers } from '@/app/providers';
import '@/styles/globals.css';

export const metadata: Metadata = {
  title: {
    default: 'BKN AI Capital',
    template: '%s · BKN AI Capital',
  },
  description: 'Institutional-grade, AI-assisted trading analysis for the Indian market.',
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: '#0d1117',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
