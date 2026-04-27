import { NextResponse } from 'next/server'
import { getFiles, getProject } from '@/lib/db'
import { exportMarkdown } from '@/lib/exporter'

export async function POST(_: Request, { params }: { params: { id: string } }) {
  try {
    const projectId = Number(params.id)
    const project = await getProject(projectId)
    if (!project) return NextResponse.json({ error: 'Project not found' }, { status: 404 })
    const files = (await getFiles(projectId, { status: 'exported', limit: 100000, offset: 0 })).files
    let written = 0
    for (const file of files) {
      await exportMarkdown(project, file, `# ${file.filename}\n\nAlready exported content placeholder.`)
      written += 1
    }
    return NextResponse.json({ written })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Export failed' }, { status: 500 })
  }
}
