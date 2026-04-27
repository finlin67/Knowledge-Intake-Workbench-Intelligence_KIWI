import { NextResponse } from 'next/server'
import { getTriageSummary } from '@/lib/db'

export async function GET(_: Request, { params }: { params: { id: string } }) {
  try {
    const projectId = Number(params.id)
    return NextResponse.json(await getTriageSummary(projectId))
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Failed to fetch triage summary' }, { status: 500 })
  }
}
