import fs from 'node:fs/promises'
import { createRequire } from 'node:module'
import path from 'node:path'
import mammoth from 'mammoth'
import pdfParse from 'pdf-parse'

const normalizeWhitespace = (value: string): string => value.replace(/\r\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim()
const require = createRequire(import.meta.url)

const extractPptxText = async (filepath: string): Promise<string> => {
  const textract = (() => {
    try {
      return require('textract') as {
        fromFileWithPath: (
          filepath: string,
          options: { preserveLineBreaks: boolean },
          callback: (error: Error | null, text: string) => void
        ) => void
      }
    } catch {
      return null
    }
  })()
  if (!textract) return ''
  return new Promise((resolve) => {
    textract.fromFileWithPath(filepath, { preserveLineBreaks: true }, (error: Error | null, text: string) => {
      if (error) return resolve('')
      resolve(text || '')
    })
  })
}

export const truncateByParagraphCount = (markdown: string, chunkTargetSize = 0): string => {
  if (!chunkTargetSize || chunkTargetSize <= 0) return markdown
  const parts = markdown.split(/\n\s*\n/g)
  if (parts.length <= chunkTargetSize) return markdown
  return parts.slice(0, chunkTargetSize).join('\n\n')
}

export async function convertToMarkdown(filepath: string): Promise<string> {
  const ext = path.extname(filepath).toLowerCase()

  if (ext === '.md' || ext === '.txt' || ext === '.html') {
    return normalizeWhitespace(await fs.readFile(filepath, 'utf8'))
  }

  if (ext === '.pdf') {
    const data = await fs.readFile(filepath)
    const output = await pdfParse(data)
    return normalizeWhitespace(output.text)
  }

  if (ext === '.docx') {
    const result = await mammoth.extractRawText({ path: filepath })
    return normalizeWhitespace(result.value)
  }

  if (ext === '.pptx') {
    const text = await extractPptxText(filepath)
    return normalizeWhitespace(text)
  }

  throw new Error(`Unsupported extension: ${ext}`)
}
