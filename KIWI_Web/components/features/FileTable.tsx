'use client'

import { FileRecord } from '@/types'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'

interface FileTableProps {
  files: FileRecord[]
  onSort?: (key: string) => void
  selectable?: boolean
  selectedIds?: number[]
  onToggleSelect?: (id: number) => void
}

export function FileTable({ files, onSort, selectable, selectedIds = [], onToggleSelect }: FileTableProps) {
  if (!files.length) return <EmptyState message="No files to display." />

  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead className="bg-[var(--bg3)] text-[11px] uppercase tracking-[0.06em] text-[var(--text3)]">
          <tr className="h-10">
            {selectable ? <th className="px-3 text-left">Select</th> : null}
            {['#', 'File ID', 'File', 'Folder', 'Next Stage', 'Status', 'Workspace', 'Updated'].map((h) => (
              <th key={h} className="px-3 text-left">
                <button type="button" className="hover:text-[var(--text2)]" onClick={() => onSort?.(h)}>
                  {h}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {files.map((file, idx) => {
            const selected = selectedIds.includes(file.id)
            return (
              <tr
                key={file.id}
                className={`h-10 border-b border-[var(--border)] ${idx % 2 === 0 ? 'bg-[var(--bg2)]' : 'bg-[var(--bg3)]'} hover:bg-[var(--bg4)] ${selected ? 'bg-[var(--accent-dim)]' : ''}`}
              >
                {selectable ? (
                  <td className="px-3">
                    <input checked={selected} onChange={() => onToggleSelect?.(file.id)} type="checkbox" />
                  </td>
                ) : null}
                <td className="px-3">{idx + 1}</td>
                <td className="px-3 font-mono text-xs">{file.id}</td>
                <td className="px-3">{file.filename}</td>
                <td className="px-3">{file.subfolder || '-'}</td>
                <td className="px-3">{file.nextStage}</td>
                <td className="px-3">
                  <Badge variant={(file.status === 'skipped' ? 'review' : file.status) as any}>{file.status}</Badge>
                </td>
                <td className="px-3">{file.workspace}</td>
                <td className="px-3">{new Date(file.updatedAt).toLocaleString()}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
