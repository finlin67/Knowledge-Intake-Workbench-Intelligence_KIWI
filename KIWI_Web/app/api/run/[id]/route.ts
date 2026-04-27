import { NextResponse } from 'next/server'
import { convertToMarkdown } from '@/lib/converter'
import { getFiles, getProject, updateFileStatus } from '@/lib/db'
import { defaultRules } from '@/lib/defaultRules'
import { exportMarkdown } from '@/lib/exporter'
import { getRunState, setRunState, updateRunState } from '@/lib/runState'
import { RunStatus } from '@/types'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export async function POST(_: Request, { params }: { params: { id: string } }) {
  try {
    const projectId = Number(params.id)
    const project = await getProject(projectId)
    if (!project) return NextResponse.json({ error: 'Project not found' }, { status: 404 })

    const snapshot = await getFiles(projectId, { status: 'new', limit: 100000, offset: 0 })
    const start = Date.now()
    const initial: RunStatus = {
      projectId,
      status: 'running',
      total: snapshot.total,
      processed: 0,
      exported: 0,
      failed: 0,
      currentFile: '',
      elapsedSeconds: 0,
      log: []
    }
    setRunState(projectId, initial)

    setImmediate(async () => {
      while (true) {
        const state = getRunState(projectId)
        if (!state || state.status !== 'running') break

        const batch = (await getFiles(projectId, { status: 'new', limit: 10, offset: 0 })).files
        if (!batch.length) {
          updateRunState(projectId, (s) => ({ ...s, status: 'complete', elapsedSeconds: Math.round((Date.now() - start) / 1000) }))
          break
        }

        for (const file of batch) {
          const run = getRunState(projectId)
          if (!run || run.status !== 'running') break
          try {
            await updateFileStatus(file.id, 'processing')
            const markdownRaw = await convertToMarkdown(file.filepath)
            const markdown = defaultRules.chunk_target_size ? markdownRaw.split('\n\n').slice(0, defaultRules.chunk_target_size).join('\n\n') : markdownRaw
            await exportMarkdown(project, file, markdown)
            await updateFileStatus(file.id, 'exported')
            updateRunState(projectId, (s) => ({
              ...s,
              processed: s.processed + 1,
              exported: s.exported + 1,
              currentFile: file.filename,
              elapsedSeconds: Math.round((Date.now() - start) / 1000),
              log: [...s.log, { timestamp: new Date().toISOString(), status: 'success' as const, workspace: file.workspace, filename: file.filename }].slice(-50)
            }))
          } catch {
            await updateFileStatus(file.id, 'failed')
            updateRunState(projectId, (s) => ({
              ...s,
              processed: s.processed + 1,
              failed: s.failed + 1,
              currentFile: file.filename,
              elapsedSeconds: Math.round((Date.now() - start) / 1000),
              log: [...s.log, { timestamp: new Date().toISOString(), status: 'failed' as const, workspace: file.workspace, filename: file.filename }].slice(-50)
            }))
          }
        }
        await sleep(40)
      }
    })

    return NextResponse.json({ started: true })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Run start failed' }, { status: 500 })
  }
}
