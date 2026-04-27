export function ProgressBar({ value, total }: { value: number; total: number }) {
  const percent = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0
  return (
    <div className="space-y-2">
      <div className="h-3 w-full overflow-hidden rounded bg-[var(--bg3)]">
        <div className="h-full bg-[var(--accent)] transition-all duration-500" style={{ width: `${percent}%` }} />
      </div>
      <div className="text-xs text-[var(--text3)]">{value} of {total} files</div>
    </div>
  )
}
