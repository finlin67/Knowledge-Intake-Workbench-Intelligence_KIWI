'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { getApiBaseUrl, getToken } from '@/lib/api'

type QueueItem = Record<string, unknown>

type TriageRow = {
  rowKey: string
  fileId: string
  filename: string
  workspace: string
  selectedWorkspace: string
  assigned: boolean
  saving: boolean
}

const DEFAULT_WORKSPACES = ['career_portfolio', 'ai_projects', 'archive', 'case_studies', 'wiki', 'skip']

function readWorkspaceOptions(): string[] {
  if (typeof window === 'undefined') return DEFAULT_WORKSPACES

  const raw = localStorage.getItem('kiwi_workspaces')
  if (!raw) return DEFAULT_WORKSPACES

  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      const extracted = parsed
        .map((entry) => {
          if (typeof entry === 'string') return entry
          if (entry && typeof entry === 'object') {
            if (typeof (entry as { key?: unknown }).key === 'string') return String((entry as { key: string }).key)
            if (typeof (entry as { value?: unknown }).value === 'string') return String((entry as { value: string }).value)
            if (typeof (entry as { name?: unknown }).name === 'string') return String((entry as { name: string }).name)
          }
          return ''
        })
        .filter(Boolean)

      return Array.from(new Set([...extracted, ...DEFAULT_WORKSPACES]))
    }
  } catch {
    return DEFAULT_WORKSPACES
  }

  return DEFAULT_WORKSPACES
}

function needsReview(item: QueueItem): boolean {
  const status = String(item.status ?? '').toLowerCase()
  const workspace = String(item.workspace ?? '').toLowerCase()
  const nextStage = String(item.next_stage ?? '').toLowerCase()
  const subfolder = String(item.subfolder ?? '').toLowerCase()
  return (status === 'new' && workspace === 'unassigned') || nextStage === 'review' || subfolder === 'review'
}

function toRows(items: QueueItem[]): TriageRow[] {
  return items.filter(needsReview).map((item, index) => {
    const fileId = String(item.file_id ?? item.id ?? item.filename ?? `row-${index}`)
    const filename = String(item.filename ?? item.path ?? item.file_path ?? fileId)
    const workspace = String(item.workspace ?? 'unassigned')
    const normalizedWorkspace = workspace || 'unassigned'

    return {
      rowKey: `${fileId}-${index}`,
      fileId,
      filename,
      workspace: normalizedWorkspace,
      selectedWorkspace: normalizedWorkspace,
      assigned: normalizedWorkspace !== 'unassigned',
      saving: false
    }
  })
}

export default function TriagePage() {
  const router = useRouter()
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [rows, setRows] = useState<TriageRow[]>([])
  const [workspaceOptions, setWorkspaceOptions] = useState<string[]>(DEFAULT_WORKSPACES)
  const [bulkWorkspace, setBulkWorkspace] = useState(DEFAULT_WORKSPACES[0])
  const [loading, setLoading] = useState(false)
  const [bulkSaving, setBulkSaving] = useState(false)
  const [error, setError] = useState('')

  const needsReviewCount = useMemo(() => rows.filter((row) => !row.assigned).length, [rows])
  const assignedCount = useMemo(() => rows.filter((row) => row.assigned).length, [rows])

  const load = async () => {
    const token = getToken()
    setSessionToken(token)
    setWorkspaceOptions(readWorkspaceOptions())
    setError('')

    if (!token) {
      setRows([])
      return
    }

    setLoading(true)
    try {
      const apiBase = await getApiBaseUrl()
      const response = await fetch(`${apiBase}/api/queue?session_token=${encodeURIComponent(token)}`)
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload?.detail ?? 'Failed to load triage queue.')
      }

      const payload = (await response.json()) as {
        current_batch_queue?: QueueItem[]
        pending_queue?: QueueItem[]
        other_pending_queue?: QueueItem[]
      }

      const merged = [...(payload.current_batch_queue ?? []), ...(payload.pending_queue ?? []), ...(payload.other_pending_queue ?? [])]
      setRows(toRows(merged))
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load triage queue.')
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const assignFile = async (rowKey: string, workspace: string) => {
    if (!sessionToken) return

    const target = rows.find((row) => row.rowKey === rowKey)
    if (!target) return

    setRows((prev) => prev.map((row) => (row.rowKey === rowKey ? { ...row, saving: true } : row)))
    setError('')

    try {
      const apiBase = await getApiBaseUrl()
      const response = await fetch(`${apiBase}/api/queue/assign`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_token: sessionToken,
          file_id: target.fileId,
          workspace
        })
      })

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(payload?.detail ?? 'Failed to assign file.')
      }

      setRows((prev) =>
        prev.map((row) =>
          row.rowKey === rowKey
            ? {
                ...row,
                workspace,
                selectedWorkspace: workspace,
                assigned: workspace !== 'unassigned',
                saving: false
              }
            : row
        )
      )
    } catch (err: any) {
      setRows((prev) => prev.map((row) => (row.rowKey === rowKey ? { ...row, saving: false } : row)))
      setError(err?.message ?? `Failed to assign ${target.filename}.`)
    }
  }

  const applyToAll = async (workspace: string) => {
    if (!sessionToken || !rows.length) return
    setBulkSaving(true)
    setError('')

    const pending = rows.filter((row) => row.selectedWorkspace !== workspace || row.workspace !== workspace || !row.assigned)

    for (const row of pending) {
      await assignFile(row.rowKey, workspace)
    }

    setBulkSaving(false)
  }

  const handleSkipAll = async () => {
    await applyToAll('skip')
  }

  const goRunQueue = () => {
    localStorage.setItem('kiwi_trigger_run_queue', '1')
    router.push('/')
  }

  const showMissingToken = !sessionToken && !loading
  const showEmpty = sessionToken && !loading && rows.length === 0

  return (
    <div className="space-y-4">
      <PageHeader
        title="Triage — Review Unclassified Files"
        subtitle="These files could not be automatically classified. Assign each to a workspace before running this batch."
      />

      {showMissingToken ? (
        <div className="rounded-[var(--radius)] border border-[var(--border)] bg-white px-4 py-3 text-sm text-[var(--danger)]">
          No active project. Go to Home and create or load a project first.
        </div>
      ) : null}

      {error ? (
        <div className="rounded-[var(--radius)] border border-[rgba(184,64,64,0.35)] bg-[rgba(184,64,64,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
          {error}
        </div>
      ) : null}

      {showEmpty ? (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-white p-6">
          <p className="text-base font-medium text-[var(--text)]">✅ All files are classified and ready to run.</p>
          <Button className="mt-4" onClick={goRunQueue}>
            Run This Batch →
          </Button>
        </div>
      ) : null}

      {!showMissingToken && !showEmpty ? (
        <>
          <div className="rounded-[var(--radius)] border border-[var(--border)] bg-white px-4 py-3 text-sm text-[var(--text2)]">
            {needsReviewCount} files need review | {assignedCount} already assigned | Run This Batch when ready →
          </div>

          <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] bg-white px-3 py-2">
            <span className="text-sm text-[var(--text2)]">Assign all visible to:</span>
            <Select
              className="h-8 w-52 rounded text-sm"
              value={bulkWorkspace}
              onChange={(event) => setBulkWorkspace(event.target.value)}
              disabled={bulkSaving}
            >
              {workspaceOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
            <Button variant="secondary" onClick={() => void applyToAll(bulkWorkspace)} disabled={bulkSaving || loading}>
              {bulkSaving ? 'Applying...' : 'Apply to All'}
            </Button>
            <Button variant="secondary" onClick={() => void handleSkipAll()} disabled={bulkSaving || loading}>
              Skip All
            </Button>
            <Button className="ml-auto" onClick={() => router.push('/')}>
              Done - Go to Home →
            </Button>
          </div>

          <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)]">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg3)] text-left text-[11px] uppercase tracking-[0.06em] text-[var(--text3)]">
                <tr className="h-10">
                  <th className="px-3">filename</th>
                  <th className="px-3">current workspace</th>
                  <th className="px-3">assign to</th>
                  <th className="px-3">action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.rowKey}
                    className={`border-t border-[var(--border)] transition-colors ${row.assigned ? 'bg-[var(--kiwi-green-light)]' : 'bg-white hover:bg-[var(--kiwi-blue-pale)]'}`}
                  >
                    <td className="px-3 py-2 text-[var(--text)]">{row.filename}</td>
                    <td className="px-3 py-2 text-[var(--text2)]">{row.workspace || 'unassigned'}</td>
                    <td className="px-3 py-2">
                      <Select
                        className="h-8 w-52 rounded text-sm"
                        value={row.selectedWorkspace}
                        onChange={(event) => {
                          const nextValue = event.target.value
                          setRows((prev) =>
                            prev.map((candidate) =>
                              candidate.rowKey === row.rowKey ? { ...candidate, selectedWorkspace: nextValue } : candidate
                            )
                          )
                        }}
                        disabled={row.saving || bulkSaving}
                      >
                        <option value="unassigned">unassigned</option>
                        {workspaceOptions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </Select>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="secondary"
                          onClick={() => void assignFile(row.rowKey, row.selectedWorkspace)}
                          disabled={row.saving || bulkSaving || row.selectedWorkspace === 'unassigned'}
                        >
                          {row.saving ? 'Assigning...' : 'Assign'}
                        </Button>
                        {row.assigned ? <span className="text-sm text-[var(--kiwi-green)]">✓ Assigned</span> : null}
                      </div>
                    </td>
                  </tr>
                ))}
                {!rows.length ? (
                  <tr>
                    <td className="px-3 py-4 text-center text-[var(--text3)]" colSpan={4}>
                      {loading ? 'Loading triage files...' : 'No files currently need review.'}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}
