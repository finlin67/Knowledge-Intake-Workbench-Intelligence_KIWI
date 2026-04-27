'use client'

import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'

interface FilterBarProps {
  reason: string
  priority: string
  workspace: string
  search: string
  setReason: (value: string) => void
  setPriority: (value: string) => void
  setWorkspace: (value: string) => void
  setSearch: (value: string) => void
  onRefresh: () => void
}

export function FilterBar(props: FilterBarProps) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--bg2)] px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Select value={props.reason} onChange={(e) => props.setReason(e.target.value)} className="w-40">
          <option>All Reasons</option>
          <option>fallback</option>
          <option>manual</option>
        </Select>
        <Select value={props.priority} onChange={(e) => props.setPriority(e.target.value)} className="w-32">
          <option>All Priority</option>
          <option>High</option>
          <option>Low</option>
        </Select>
        <Select value={props.workspace} onChange={(e) => props.setWorkspace(e.target.value)} className="w-40">
          <option>All Workspaces</option>
          <option>unassigned</option>
          <option>operations</option>
          <option>marketing</option>
        </Select>
        <Input value={props.search} onChange={(e) => props.setSearch(e.target.value)} placeholder="Search filename..." className="w-56" />
        <Button onClick={props.onRefresh}>Refresh</Button>
      </div>
    </div>
  )
}
