'use client'

import { useEffect, useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { getPreflight } from '@/lib/api'

export default function MonitorPage() {
  const [summary, setSummary] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refresh = async () => {
    setError('')
    setLoading(true)
    try {
      const data = await getPreflight()
      setSummary(data.summary ?? {})
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load preflight summary.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const filesInScope = Number(summary.files_in_scope ?? summary.total_files ?? 0)
  const pending = Number(summary.pending ?? summary.pending_count ?? 0)
  const alreadyProcessed = Number(summary.already_processed ?? summary.processed ?? 0)
  const activeAiProvider = String(summary.active_ai_provider ?? summary.ai_provider ?? 'unknown')
  const ready = pending > 0 && filesInScope > 0

  return (
    <div className="space-y-4">
      <PageHeader title="Run Monitor" />
      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <StatCard label="Files In Scope" value={filesInScope} />
        <StatCard label="Pending" value={pending} accent={pending > 0 ? 'text-[var(--warning)]' : undefined} />
        <StatCard label="Already Processed" value={alreadyProcessed} />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Card>
          <p className="text-xs uppercase tracking-[0.08em] text-[var(--text3)]">Active AI Provider</p>
          <p className="mt-2 text-xl text-[var(--text)]">{activeAiProvider}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.08em] text-[var(--text3)]">Status</p>
          <div className="mt-2 flex items-center gap-2">
            <span className={`h-3 w-3 rounded-full ${ready ? 'bg-[var(--success)]' : 'bg-[var(--danger)]'}`} />
            <span className={`font-medium ${ready ? 'text-[var(--success)]' : 'text-[var(--danger)]'}`}>{ready ? 'Ready' : 'Not Ready'}</span>
          </div>
        </Card>
      </div>
      <div className="flex gap-2">
        <Button variant="secondary" onClick={refresh} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh Preflight'}
        </Button>
      </div>
    </div>
  )
}
