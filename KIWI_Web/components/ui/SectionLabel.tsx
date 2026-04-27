export function SectionLabel({ label, subtext }: { label: string; subtext?: string }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <div className="font-mono text-xs uppercase tracking-[0.08em] text-[var(--text3)]">{label}</div>
      <div className="h-px flex-1 bg-[var(--border)]" />
      {subtext ? <div className="text-xs text-[var(--text3)]">{subtext}</div> : null}
    </div>
  )
}
