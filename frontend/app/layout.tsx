import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'AgenticAIOps - Intelligent ML Operations',
  description: 'Your intelligent assistant for training, optimizing, and deploying ML models',
  keywords: ['MLOps', 'AI', 'Machine Learning', 'Agent', 'AWS'],
  authors: [{ name: 'Your Team' }],
  viewport: 'width=device-width, initial-scale=1',
  themeColor: '#3b82f6',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Runtime configuration - loaded before app starts */}
        <script src="/config.js" />
        <script src="/auth-config.js" />
      </head>
      <body className={inter.className}>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}