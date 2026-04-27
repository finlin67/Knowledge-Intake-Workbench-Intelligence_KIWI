'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { SectionLabel } from '@/components/ui/SectionLabel'
import { clearQueue, getApiBaseUrl, getQueue, getToken, runExport } from '@/lib/api'

export default function QueuePage() {
  const searchParams = useSearchParams()
  const [currentBatch, setCurrentBatch] = useState<Record<string, unknown>[]>([])
  const [pendingQueue, setPendingQueue] = useState<Record<string, unknown>[]>([])
  const [sortKey, setSortKey] = useState('status')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [runMessage, setRunMessage] = useState('')
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [activeProfile, setActiveProfile] = useState<'anythingllm' | 'open_webui' | 'both'>('anythingllm')

  const load = async () => {
    setError('')
    const token = getToken()
    setSessionToken(token)
    const selectedProfile = (localStorage.getItem('kiwi_profile') ?? localStorage.getItem('kiwi_export_profile') ?? 'anythingllm') as 'anythingllm' | 'open_webui' | 'both'
    setActiveProfile(selectedProfile)
    if (!token) {
      setCurrentBatch([])
      setPendingQueue([])
      return
    }
    setLoading(true)
    try {
      const data = await getQueue()
      setCurrentBatch(data.current_batch_queue ?? [])
      setPendingQueue(data.pending_queue ?? data.other_pending_queue ?? [])
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load queue data.')
    } finally {
      setLoading(false)
    }
  }

  const handleRunQueue = async () => {
    setError('')
    setRunMessage('Running queue...')
    const activeToken = getToken()
    setSessionToken(activeToken)
    if (!activeToken) {
      setRunMessage('')
      setError('No active project. Go to Setup and create or load a project first.')
      return
    }
    setRunning(true)
    try {
      const apiBase = await getApiBaseUrl()
      const health = await fetch(`${apiBase}/api/health`)
      if (!health.ok) {
        throw new Error('Backend API is not running. Start the backend and retry.')
      }
      const payload = await runExport(
        (localStorage.getItem('kiwi_profile') ??
          localStorage.getItem('kiwi_export_profile') ??
          'anythingllm') as 'anythingllm' | 'open_webui' | 'both'
      )
      const totalCount = Object.values(payload?.results ?? {}).reduce((sum: number, item: any) => {
        return sum + Number(item?.files_finished_ok ?? item?.files_started ?? item?.count ?? 0)
      }, 0)
      setRunMessage(`Run complete. ${totalCount} file(s) exported.`)
      await load()
    } catch (err: any) {
      setRunMessage('')
      setError(err?.message ?? 'Backend API is not running. Start the backend and retry.')
    } finally {
      setRunning(false)
    }
  }

  const handleClearQueue = async () => {
    setError('')
    setRunMessage('')
    setClearing(true)
    try {
      const profile = (localStorage.getItem('kiwi_profile') as 'anythingllm' | 'open_webui' | 'both' | null) ?? (localStorage.getItem('kiwi_export_profile') as 'anythingllm' | 'open_webui' | 'both' | null) ?? 'anythingllm'
      const result = await clearQueue(profile)
      setRunMessage(`Cleared ${result.cleared_count} queued item(s) for ${profile}.`)
      await load()
    } catch (err: any) {
      setError(err?.message ?? 'Failed to clear queue.')
    } finally {
      setClearing(false)
    }
  }

  const getStatusBadgeClass = (value: unknown) => {
    const status = String(value ?? '').toLowerCase()
    if (status === 'new') return 'bg-[rgba(73,185,111,0.15)] text-[var(--success)] border border-[rgba(73,185,111,0.35)]'
    if (status === 'pending') return 'bg-[rgba(230,173,88,0.15)] text-[var(--warning)] border border-[rgba(230,173,88,0.35)]'
    if (status === 'failed') return 'bg-[rgba(184,64,64,0.15)] text-[var(--danger)] border border-[rgba(184,64,64,0.35)]'
    return 'bg-[var(--bg4)] text-[var(--text2)] border border-[var(--border)]'
  }

  const sortBy = (key: string) => {
    setSortDirection((prev) => (key === sortKey ? (prev === 'asc' ? 'desc' : 'asc') : 'asc'))
    setSortKey(key)
  }

  const tableColumns = ['file_id', 'filename', 'subfolder', 'next_stage', 'status', 'workspace', 'updated_at']

  const sortRows = (rows: Record<string, unknown>[]) =>
    [...rows].sort((a, b) => {
      const left = String(a[sortKey] ?? '')
      const right = String(b[sortKey] ?? '')
      const compare = left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' })
      return sortDirection === 'asc' ? compare : -compare
    })

  const renderTable = (rows: Record<string, unknown>[]) => (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--bg2)]">
      <table className="w-full text-sm">
        <thead className="bg-[var(--bg3)] text-[11px] uppercase tracking-[0.06em] text-[var(--text3)]">
          <tr className="h-10">
            {tableColumns.map((column) => (
              <th key={column} className="px-3 text-left">
                <button type="button" className="hover:text-[var(--text2)]" onClick={() => sortBy(column)}>
                  {column.replace(/_/g, ' ')}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortRows(rows).map((row, idx) => (
            <tr key={`${String(row.file_id ?? idx)}-${idx}`} className={`h-10 border-b border-[var(--border)] ${idx % 2 === 0 ? 'bg-[#13131a]' : 'bg-[#171720]'}`}>
              {tableColumns.map((column) => (
                <td key={column} className="px-3 text-[var(--text2)]">
                  {column === 'status' ? (
                    <span className={`rounded-full px-2 py-1 text-xs ${getStatusBadgeClass(row[column])}`}>{String(row[column] ?? '-')}</span>
                  ) : (
                    String(row[column] ?? '-')
                  )}
                </td>
              ))}
            </tr>
          ))}
          {!rows.length ? (
            <tr>
              <td className="px-3 py-5 text-center text-[var(--text3)]" colSpan={tableColumns.length}>
                {loading ? 'Loading queue...' : 'No files to display.'}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  )

  useEffect(() => {
    setSessionToken(getToken())
    load()
  }, [])

  useEffect(() => {
    const shouldRun = searchParams.get('run') === '1' || localStorage.getItem('kiwi_trigger_run_queue') === '1'
    if (!shouldRun || running) return
    localStorage.removeItem('kiwi_trigger_run_queue')
    void handleRunQueue()
  }, [searchParams])

  return (
    <div className="space-y-4">
      <PageHeader title="Queue" subtitle={`Active profile: ${activeProfile}`} />
      <div className="rounded border border-[var(--border)] bg-[var(--bg2)] px-5 py-2 font-mono text-xs text-[var(--text3)]">
        Current batch files: {currentBatch.length} | Other pending files: {pendingQueue.length}
      </div>
      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {runMessage ? <p className="text-sm text-[var(--success)]">{runMessage}</p> : null}
      <div className="sticky top-0 z-10 flex items-center gap-3 rounded border border-[var(--border)] bg-[#11131d] p-2">
        <Button variant="secondary" onClick={load} disabled={loading}>Refresh</Button>
        <Button variant="secondary" onClick={handleClearQueue} disabled={clearing || running || loading}>
          {clearing ? 'Clearing...' : 'Clear Queue'}
        </Button>
        {sessionToken ? (
          <Button className="flex-1" onClick={handleRunQueue} disabled={running || loading}>
            {running ? 'Running...' : 'Run This Batch'}
          </Button>
        ) : (
          <p className="text-sm text-[var(--danger)]">No active project. Go to Setup and create or load a project first.</p>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="space-y-2 lg:col-span-3">
          <SectionLabel label="CURRENT BATCH QUEUE" subtext="(pending in current Raw Folder)" />
          <p className="text-xs text-[var(--text3)]">File count: {currentBatch.length}</p>
          {renderTable(currentBatch)}
        </div>
        <div className="space-y-2 lg:col-span-2">
          <SectionLabel label="OTHER PENDING QUEUE" />
          <p className="text-xs text-[var(--text3)]">File count: {pendingQueue.length}</p>
          {renderTable(pendingQueue)}
        </div>
      </div>
    </div>
  )
}
