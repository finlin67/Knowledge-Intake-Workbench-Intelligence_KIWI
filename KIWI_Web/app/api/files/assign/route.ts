import { NextResponse } from 'next/server'
import { updateFileWorkspace } from '@/lib/db'

export async function POST(request: Request) {
  try {
    const { ids, workspace, subfolder = '' } = await request.json()
    if (!Array.isArray(ids) || !workspace) {
      return NextResponse.json({ error: 'ids and workspace are required' }, { status: 400 })
    }
    const updated = await updateFileWorkspace(ids.map(Number), workspace, subfolder)
    return NextResponse.json({ updated })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Failed to assign files' }, { status: 500 })
  }
}
