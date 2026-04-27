'use client'

import { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const variantClasses: Record<Variant, string> = {
  primary: 'h-9 px-4 bg-[var(--accent)] text-white hover:bg-[#6090ff]',
  secondary: 'h-9 px-[14px] bg-[var(--bg3)] border border-[var(--border2)] text-[var(--text2)] hover:border-[var(--accent)] hover:text-[var(--text)]',
  danger: 'h-9 px-4 bg-[var(--danger-dim)] border border-[var(--danger)] text-[var(--danger)] hover:bg-[rgba(184,64,64,0.2)]',
  ghost: 'h-9 px-2 text-[var(--text3)] hover:text-[var(--text2)]'
}

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-[var(--radius)] text-sm font-medium transition-colors ${variantClasses[variant]} ${className}`}
      {...props}
    />
  )
}
