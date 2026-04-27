'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const nav = [
  { href: '/setup', label: 'Home' },
  { href: '/settings', label: 'Settings' },
  { href: '/triage', label: 'Triage' },
  { href: '/inventory', label: 'Inventory' },
  { href: '/batch-prep', label: 'Batch Your Files' }
] as const

function navIsActive(pathname: string | null, href: string) {
  if (href === '/setup') return pathname === '/setup' || pathname === '/'
  return pathname === href
}

export function TopBar() {
  const pathname = usePathname()

  const legacyQueueBanner = pathname === '/queue' || pathname === '/monitor'
  const showFullTitle = pathname === '/setup' || pathname === '/'

  return (
    <>
      <header className="sticky top-0 z-40 flex h-12 w-full shrink-0 items-center bg-[#102f4b] px-4 md:px-8">
        <div className="flex w-full min-w-0 items-center gap-4 md:gap-6">
          <Link href="/setup" className="shrink-0 text-[2rem] font-extrabold leading-none tracking-[0.03em] text-white">
            KIWI <span aria-hidden="true">🥝</span>
          </Link>
          {showFullTitle ? (
            <span className="hidden min-w-0 truncate text-[1.05rem] font-semibold text-white/95 md:block">
              Knowledge Intake Workbench Intelligence: Developer Guide
            </span>
          ) : null}

          <nav className="flex min-w-0 flex-1 flex-wrap items-center justify-center gap-6 sm:gap-8 md:gap-10">
            {nav.map((item) => {
              const active = navIsActive(pathname, item.href)
              const isBatchLink = item.href === '/batch-prep'
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`shrink-0 text-[0.95rem] transition-colors ${
                    active
                      ? 'font-bold text-white underline decoration-white underline-offset-4'
                      : isBatchLink
                        ? 'font-bold text-[#57e578] hover:text-[#6ff089]'
                        : 'font-semibold text-white hover:text-white'
                  }`}
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>

          <Link
            href="/help"
            className={`shrink-0 text-[0.95rem] font-semibold transition-colors ${
              pathname === '/help' ? 'text-white underline decoration-white underline-offset-4' : 'text-white/95 hover:text-white'
            }`}
          >
            Help
          </Link>
        </div>
      </header>

      {legacyQueueBanner ? (
        <div className="border-b border-[var(--kiwi-border)] bg-[var(--kiwi-blue-pale)] px-6 py-2.5 text-center text-sm text-[var(--kiwi-text-2)]">
          <Link href="/setup" className="font-medium text-[var(--kiwi-blue)] underline decoration-[var(--kiwi-blue)] underline-offset-2">
            Queue and Run Monitor are now on the Home screen. Click here to go to Home →
          </Link>
        </div>
      ) : null}
    </>
  )
}
