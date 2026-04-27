'use client'

import { HelpCircle } from 'lucide-react'

export function HelpIcon({ 
  title,
  className = ''
}: { 
  title: string
  className?: string
}) {
  return (
    <HelpCircle
      className={`h-4 w-4 text-[var(--kiwi-text-3)] hover:text-[var(--kiwi-blue)] cursor-help transition-colors ${className}`}
      title={title}
      aria-label={title}
    />
  )
}
