import type { Metadata } from 'next';
import { IBM_Plex_Mono, IBM_Plex_Sans, Spectral } from 'next/font/google';
import './globals.css';

const doc = Spectral({
  subsets: ['latin', 'latin-ext'],
  // 600 é para o <strong> das respostas: sem ele o browser faz bold sintético.
  weight: ['400', '500', '600'],
  style: ['normal', 'italic'],
  variable: '--fonte-doc',
  display: 'swap',
});

const ui = IBM_Plex_Sans({
  subsets: ['latin', 'latin-ext'],
  weight: ['400', '500'],
  variable: '--fonte-ui',
  display: 'swap',
});

const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400'],
  variable: '--fonte-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Juiz sintético',
  description: 'Consulte as sentenças de um magistrado do TJSP.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${doc.variable} ${ui.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
