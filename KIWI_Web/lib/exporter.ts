import fs from 'node:fs/promises'
import path from 'node:path'
import { FileRecord, Project } from '@/types'

const safeName = (value: string) => value.replace(/[<>:"/\\|?*\x00-\x1F]/g, '_')

const buildOutputPath = (project: Project, file: FileRecord): string => {
  const base = path.join(project.outputFolder, 'exports')
  if (project.exportProfile === 'anythingllm') {
    return path.join(base, 'anythingllm', `${safeName(file.filename)}.md`)
  }
  const workspace = file.workspace || 'unassigned'
  const subfolder = file.subfolder || ''
  return path.join(base, 'open_webui', workspace, subfolder, `${safeName(file.filename)}.md`)
}

export const exportMarkdown = async (project: Project, file: FileRecord, markdown: string): Promise<string> => {
  const outPath = buildOutputPath(project, file)
  await fs.mkdir(path.dirname(outPath), { recursive: true })
  await fs.writeFile(outPath, markdown, 'utf8')
  return outPath
}
