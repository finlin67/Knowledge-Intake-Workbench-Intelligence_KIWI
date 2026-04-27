import { ReactNode } from 'react'

export function StatCard({ label, value, accent }: { label: string; value: ReactNode; accent?: string }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--bg2)] px-5 py-4">
      <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--text3)]">{label}</div>
      <div className={`mt-2 text-[28px] font-semibold ${accent ?? 'text-[var(--text)]'}`}>{value}</div>
    </div>
  )
}
