import type { Metadata } from 'next'
import { Toaster } from 'react-hot-toast'
import { Providers } from '@/components/providers'
import './globals.css'

export const metadata: Metadata = {
  title: 'DataShield OSINT — Privacy Protection Platform',
  description:
    'Discover, monitor, and remove your exposed personal information from the internet. Privacy protection powered by ethical OSINT.',
  icons: { icon: '/favicon.ico' },
  openGraph: {
    title: 'DataShield OSINT',
    description: 'Privacy Protection Platform',
    type: 'website',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-navy-950 text-white min-h-screen font-sans">
        <Providers>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: '#0f2040',
                color: '#fff',
                border: '1px solid rgba(6, 182, 212, 0.3)',
              },
              success: { iconTheme: { primary: '#22c55e', secondary: '#fff' } },
              error: { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
            }}
          />
        </Providers>
      </body>
    </html>
  )
}
