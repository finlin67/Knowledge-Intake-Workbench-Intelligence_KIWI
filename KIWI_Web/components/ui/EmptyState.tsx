import { FolderOpen } from 'lucide-react'

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 text-center text-[var(--text3)]">
      <FolderOpen className="h-10 w-10" />
      <p>{message}</p>
    </div>
  )
}
