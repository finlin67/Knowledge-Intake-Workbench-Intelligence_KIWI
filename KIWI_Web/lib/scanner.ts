import fs from 'node:fs/promises'
import path from 'node:path'

const SUPPORTED_EXTENSIONS = new Set(['.pdf', '.docx', '.pptx', '.md', '.txt', '.html'])

export type ScanItem = {
  filename: string
  filepath: string
  fileSize: number
  fileExt: string
  preview: string
}

const readPreview = async (filepath: string, maxChars = 1000): Promise<string> => {
  try {
    const content = await fs.readFile(filepath, 'utf8')
    return content.slice(0, maxChars)
  } catch {
    return ''
  }
}

export async function scanFolder(sourceFolder: string): Promise<ScanItem[]> {
  const output: ScanItem[] = []

  const walk = async (dir: string) => {
    const entries = await fs.readdir(dir, { withFileTypes: true })
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        await walk(fullPath)
        continue
      }
      const ext = path.extname(entry.name).toLowerCase()
      if (!SUPPORTED_EXTENSIONS.has(ext)) continue
      const stat = await fs.stat(fullPath)
      output.push({
        filename: entry.name,
        filepath: fullPath,
        fileSize: stat.size,
        fileExt: ext,
        preview: await readPreview(fullPath)
      })
    }
  }

  await walk(sourceFolder)
  return output
}
