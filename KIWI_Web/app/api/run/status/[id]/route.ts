import { NextResponse } from 'next/server'
import { getRunState } from '@/lib/runState'
import { RunStatus } from '@/types'

export async function GET(_: Request, { params }: { params: { id: string } }) {
  try {
    const projectId = Number(params.id)
    const state = getRunState(projectId)
    if (state) return NextResponse.json(state)
    const idle: RunStatus = { projectId, status: 'idle', total: 0, processed: 0, exported: 0, failed: 0, currentFile: '', elapsedSeconds: 0, log: [] }
    return NextResponse.json(idle)
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Failed to get run status' }, { status: 500 })
  }
}
