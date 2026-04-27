import { NextResponse } from 'next/server'
import { getRunState, updateRunState } from '@/lib/runState'

export async function POST(_: Request, { params }: { params: { id: string } }) {
  try {
    const projectId = Number(params.id)
    const state = getRunState(projectId)
    if (!state) return NextResponse.json({ error: 'Run not found' }, { status: 404 })
    updateRunState(projectId, (s) => ({ ...s, status: 'paused' }))
    return NextResponse.json({ paused: true })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Pause failed' }, { status: 500 })
  }
}
