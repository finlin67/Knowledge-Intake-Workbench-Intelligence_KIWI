type BadgeVariant = 'new' | 'processing' | 'exported' | 'failed' | 'review' | 'unassigned'

const styles: Record<BadgeVariant, string> = {
  new: 'bg-[var(--success-dim)] text-[var(--success)]',
  processing: 'bg-[var(--accent-dim)] text-[var(--accent)]',
  exported: 'bg-[var(--bg4)] text-[var(--text3)]',
  failed: 'bg-[var(--danger-dim)] text-[var(--danger)]',
  review: 'bg-[var(--warning-dim)] text-[var(--warning)]',
  unassigned: 'bg-[var(--bg4)] text-[var(--text3)]'
}

export function Badge({ variant, children }: { variant: BadgeVariant; children: string }) {
  return (
    <span className={`inline-flex rounded px-[7px] py-[2px] font-mono text-[11px] ${styles[variant]}`}>{children}</span>
  )
}
