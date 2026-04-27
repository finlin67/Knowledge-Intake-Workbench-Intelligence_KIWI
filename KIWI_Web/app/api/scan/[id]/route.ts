import fs from 'node:fs'
import path from 'node:path'
import { NextResponse } from 'next/server'
import { classifyFile } from '@/lib/classifier'
import { getProject, insertFile } from '@/lib/db'
import { defaultRules } from '@/lib/defaultRules'
import { scanFolder } from '@/lib/scanner'

export async function POST(_: Request, { params }: { params: { id: string } }) {
  try {
    const id = Number(params.id)
    const project = await getProject(id)
    if (!project) return NextResponse.json({ error: 'Project not found' }, { status: 404 })
    const rulesPath = path.join(project.outputFolder, '.kiw', 'classification_rules.json')
    const rules = fs.existsSync(rulesPath) ? JSON.parse(fs.readFileSync(rulesPath, 'utf8')) : defaultRules
    const items = await scanFolder(project.sourceFolder)
    let inserted = 0
    for (const item of items) {
      const c = classifyFile(item.filename, item.preview, rules)
      await insertFile({
        projectId: id,
        filename: item.filename,
        filepath: item.filepath,
        fileSize: item.fileSize,
        fileExt: item.fileExt,
        nextStage: 'classify',
        status: 'new',
        workspace: c.workspace,
        subfolder: c.subfolder,
        matchedBy: c.matchedBy,
        confidence: c.confidence,
        priority: c.priority,
        signals: c.signals
      })
      inserted += 1
    }
    return NextResponse.json({ scanned: items.length, inserted })
  } catch (error: any) {
    return NextResponse.json({ error: error.message ?? 'Scan failed' }, { status: 500 })
  }
}
