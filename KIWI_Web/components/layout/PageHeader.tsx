export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-[22px] font-medium text-[var(--text)]">{title}</h1>
      {subtitle ? <p className="mt-1 text-sm text-[var(--text2)]">{subtitle}</p> : null}
    </div>
  )
}
