import { SelectHTMLAttributes } from 'react'

export function Select({ className = '', children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`h-9 w-full rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg3)] px-3 text-sm text-[var(--text)] outline-none focus:border-[var(--accent)] ${className}`}
      {...props}
    >
      {children}
    </select>
  )
}
