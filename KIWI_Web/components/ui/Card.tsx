import { ReactNode } from 'react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--bg2)] px-6 py-5 ${className}`}>{children}</div>
}
