import { forwardRef, InputHTMLAttributes } from 'react'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className = '', ...props },
  ref
) {
  return (
    <input
      ref={ref}
      className={`h-9 w-full rounded-[var(--radius)] border border-[var(--border)] bg-[var(--bg3)] px-3 text-[var(--text)] outline-none placeholder:text-[var(--text3)] focus:border-[var(--accent)] ${className}`}
      {...props}
    />
  )
})
