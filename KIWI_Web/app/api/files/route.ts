import { NextResponse } from 'next/server'
import { getFiles } from '@/lib/db'

export async function GET(request: Request) {
  try {
    const url = new URL(request.url)
    const projectId = Number(url.searchParams.get('projectId') ?? '1')
    const status = url.searchParams.get('status') ?? undefined
    const workspace = url.searchParams.get('workspace') ?? undefined
    const search = url.searchParams.get('search') ?? undefined
    const sort = url.searchParams.get('sort') ?? undefined
    const limit = Number(url.searchParams.get('limit') ?? '100')
    const offset = Number(url.searchParams.get('offset') ?? '0')
    return NextResponse.json(await getFiles(projectId, { status, workspace, search, sort, limit, offset }))
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Failed to fetch files' }, { status: 500 })
  }
}
