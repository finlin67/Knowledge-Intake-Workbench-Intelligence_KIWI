'use client'

import './globals.css'
import { ReactNode } from 'react'
import { TopBar } from '@/components/layout/TopBar'
import { ProjectProvider } from '@/lib/context'

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ProjectProvider>
          <AppShell>{children}</AppShell>
        </ProjectProvider>
      </body>
    </html>
  )
}

function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#eef0f7]">
      <TopBar />
      <main className="min-h-[calc(100vh-48px)] flex-1 bg-[#eef0f7] px-3 py-2 md:px-4 md:py-3 text-[#4a4a6a]">{children}</main>
    </div>
  )
}
