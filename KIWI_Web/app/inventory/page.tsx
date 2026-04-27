'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { getInventory, getToken } from '@/lib/api'

const columns = ['file_id', 'filename', 'workspace', 'subfolder', 'status', 'next_stage', 'updated_at'] as const

function extractAllRows(data: Record<string, unknown>): Record<string, unknown>[] {
  const keys = [
    'all_files',
    'inventory',
    'files',
    'processed_queue',
    'completed_files',
    'current_batch_queue',
    'pending_queue',
    'other_pending_queue'
  ]
  const candidates: unknown[] = []
  for (const k of keys) {
    const v = data[k]
    if (Array.isArray(v)) candidates.push(...v)
  }
  const seen = new Set<string>()
  const out: Record<string, unknown>[] = []
  for (const row of candidates) {
    if (!row || typeof row !== 'object') continue
    const r = row as Record<string, unknown>
    const key = String(r.file_id ?? `${String(r.filename ?? '')}|${String(r.updated_at ?? '')}`)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(r)
  }
  return out
}

function getStatusBadgeClass(value: unknown) {
  const status = String(value ?? '').toLowerCase()
  if (status === 'new') return 'bg-[#e7f5ec] text-[#2f9e44] border border-[#b2f2bb]'
  if (status === 'pending') return 'bg-[#fff4e6] text-[#d9480f] border border-[#ffc9a3]'
  if (status === 'failed') return 'bg-[#ffe3e3] text-[#c92a2a] border border-[#ffc9c9]'
  return 'bg-[#eef0f7] text-[#4a4a6a] border border-[#dde1f0]'
}

const inputLight = '!border-[#dde1f0] !bg-white !text-[#1a1a2e] placeholder:!text-[#4a4a6a]'

export default function InventoryPage() {
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [filter, setFilter] = useState('')
  const [aiFilter, setAiFilter] = useState<'all' | 'ai' | 'rules'>('all')
  const [matchedByFilter, setMatchedByFilter] = useState('all')
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    const token = getToken()
    if (!token) {
      setRows([])
      setError('No active project. Load a project from Home first.')
      return
    }
    setLoading(true)
    try {
      const data = await getInventory(10000)
      setRows(extractAllRows({ rows: data.rows, inventory: data.rows }))
    } catch (e: unknown) {
      setRows([])
      setError(e instanceof Error ? e.message : 'Failed to load inventory.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const interval = window.setInterval(() => {
      void load()
    }, 10000)
    const onVisibility = () => {
      if (!document.hidden) void load()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [load])

  const matchedByOptions = useMemo(() => {
    const keys = new Set<string>()
    for (const row of rows) {
      const key = String(row.matched_by ?? '').trim().toLowerCase()
      if (key) keys.add(key)
    }
    return ['all', ...Array.from(keys).sort()]
  }, [rows])

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    return rows.filter((r) => {
      const filenameMatch = !q || String(r.filename ?? '').toLowerCase().includes(q)
      if (!filenameMatch) return false

      const matchedBy = String(r.matched_by ?? '').trim().toLowerCase()
      const aiUsedRaw = String(r.ai_used ?? '').trim().toLowerCase()
      const reviewRequiredRaw = String(r.review_required ?? '').trim().toLowerCase()
      const aiUsed = aiUsedRaw === '1' || aiUsedRaw === 'true' || matchedBy === 'ollama'
      const reviewRequired = reviewRequiredRaw === '1' || reviewRequiredRaw === 'true'

      if (aiFilter === 'ai' && !aiUsed) return false
      if (aiFilter === 'rules' && aiUsed) return false
      if (matchedByFilter !== 'all' && matchedBy !== matchedByFilter) return false
      if (needsReviewOnly && !reviewRequired) return false
      return true
    })
  }, [rows, filter, aiFilter, matchedByFilter, needsReviewOnly])

  const applyQuickFilter = useCallback((preset: 'all' | 'ai' | 'rules' | 'fallback' | 'review') => {
    if (preset === 'all') {
      setAiFilter('all')
      setMatchedByFilter('all')
      setNeedsReviewOnly(false)
      return
    }
    if (preset === 'ai') {
      setAiFilter('ai')
      setMatchedByFilter('all')
      setNeedsReviewOnly(false)
      return
    }
    if (preset === 'rules') {
      setAiFilter('rules')
      setMatchedByFilter('all')
      setNeedsReviewOnly(false)
      return
    }
    if (preset === 'fallback') {
      setAiFilter('all')
      setMatchedByFilter('fallback')
      setNeedsReviewOnly(false)
      return
    }
    setAiFilter('all')
    setMatchedByFilter('all')
    setNeedsReviewOnly(true)
  }, [])

  const searchScopedRows = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return rows
    return rows.filter((r) => String(r.filename ?? '').toLowerCase().includes(q))
  }, [rows, filter])

  const computeQuickCounts = useCallback((sourceRows: Record<string, unknown>[]) => {
    const counts = {
      all: sourceRows.length,
      ai: 0,
      rules: 0,
      fallback: 0,
      review: 0
    }
    for (const row of sourceRows) {
      const matchedBy = String(row.matched_by ?? '').trim().toLowerCase()
      const aiUsedRaw = String(row.ai_used ?? '').trim().toLowerCase()
      const reviewRequiredRaw = String(row.review_required ?? '').trim().toLowerCase()
      const aiUsed = aiUsedRaw === '1' || aiUsedRaw === 'true' || matchedBy === 'ollama'
      const reviewRequired = reviewRequiredRaw === '1' || reviewRequiredRaw === 'true'
      if (aiUsed) counts.ai += 1
      else counts.rules += 1
      if (matchedBy === 'fallback') counts.fallback += 1
      if (reviewRequired) counts.review += 1
    }
    return counts
  }, [])

  const quickCountsTotal = useMemo(() => computeQuickCounts(rows), [rows, computeQuickCounts])
  const quickCountsScoped = useMemo(
    () => computeQuickCounts(searchScopedRows),
    [searchScopedRows, computeQuickCounts]
  )

  return (
    <div className="mx-auto max-w-[1400px] space-y-4">
      <div>
        <h1 className="text-xl font-bold text-[#1a1a2e]">Inventory — All Processed Files</h1>
        <p className="mt-1 text-sm text-[#4a4a6a]">Read-only list from the project queue endpoint.</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          className={`max-w-md ${inputLight}`}
          placeholder="Filter by filename…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter by filename"
        />
        <Select className="max-w-[160px]" value={aiFilter} onChange={(e) => setAiFilter(e.target.value as 'all' | 'ai' | 'rules')}>
          <option value="all">AI Used: All</option>
          <option value="ai">AI Used: Yes</option>
          <option value="rules">AI Used: No</option>
        </Select>
        <Select className="max-w-[180px]" value={matchedByFilter} onChange={(e) => setMatchedByFilter(e.target.value)}>
          {matchedByOptions.map((option) => (
            <option key={option} value={option}>
              {option === 'all' ? 'Matched By: All' : `Matched By: ${option}`}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {[
          { key: 'all', label: 'All' },
          { key: 'ai', label: 'AI Only' },
          { key: 'rules', label: 'Rules Only' },
          { key: 'fallback', label: 'Fallback Only' },
          { key: 'review', label: 'Needs Review' }
        ].map((chip) => {
          const active =
            (chip.key === 'all' && aiFilter === 'all' && matchedByFilter === 'all' && !needsReviewOnly) ||
            (chip.key === 'ai' && aiFilter === 'ai' && matchedByFilter === 'all' && !needsReviewOnly) ||
            (chip.key === 'rules' && aiFilter === 'rules' && matchedByFilter === 'all' && !needsReviewOnly) ||
            (chip.key === 'fallback' && aiFilter === 'all' && matchedByFilter === 'fallback' && !needsReviewOnly) ||
            (chip.key === 'review' && aiFilter === 'all' && matchedByFilter === 'all' && needsReviewOnly)
          return (
            <button
              key={chip.key}
              type="button"
              onClick={() => applyQuickFilter(chip.key as 'all' | 'ai' | 'rules' | 'fallback' | 'review')}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                active
                  ? 'border-[#3b5bdb] bg-[#e7edff] text-[#2f4ac5]'
                  : 'border-[#dde1f0] bg-white text-[#4a4a6a] hover:border-[#3b5bdb] hover:text-[#2f4ac5]'
              }`}
            >
              {chip.label} ({quickCountsScoped[chip.key as keyof typeof quickCountsScoped]}/{quickCountsTotal[chip.key as keyof typeof quickCountsTotal]})
            </button>
          )
        })}
      </div>

      {error ? <p className="text-sm text-[#c92a2a]">{error}</p> : null}

      <p className="text-sm text-[#4a4a6a]">
        <strong className="text-[#1a1a2e]">Total files:</strong> {rows.length}
        {filter.trim() ? (
          <>
            {' '}
            · <strong className="text-[#1a1a2e]">Matching filter:</strong> {filtered.length}
          </>
        ) : null}
      </p>

      <div className="overflow-hidden rounded-xl border border-[#dde1f0] bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-[#eef0f7] text-left text-[11px] font-medium uppercase tracking-wide text-[#4a4a6a]">
              <tr className="h-10">
                {columns.map((col) => (
                  <th key={col} className="px-3">
                    {col.replace(/_/g, ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, idx) => (
                <tr
                  key={`${String(row.file_id ?? idx)}-${idx}`}
                  className={`h-10 border-b border-[#dde1f0] ${idx % 2 === 0 ? 'bg-white' : 'bg-[#fafbff]'}`}
                >
                  {columns.map((col) => (
                    <td key={col} className="px-3 text-[#4a4a6a]">
                      {col === 'status' ? (
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getStatusBadgeClass(row[col])}`}>
                          {String(row[col] ?? '-')}
                        </span>
                      ) : (
                        String(row[col] ?? '-')
                      )}
                    </td>
                  ))}
                </tr>
              ))}
              {!filtered.length ? (
                <tr>
                  <td className="px-3 py-8 text-center text-[#4a4a6a]" colSpan={columns.length}>
                    {loading ? 'Loading…' : 'No files to display.'}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
