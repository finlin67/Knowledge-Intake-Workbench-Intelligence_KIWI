'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import {
  type BatchPrepPreviewResponse,
  type BatchPrepRequest,
  type BatchPrepRunResponse,
  previewBatchPrep,
  runBatchPrep
} from '@/lib/api'

type BatchMode = 'fixed' | 'pattern'
type CopyMode = 'copy' | 'move'

const cardClass = 'rounded-xl border border-[var(--kiwi-border)] bg-white shadow-sm'
const labelClass = 'text-xs font-semibold text-[var(--kiwi-text-2)]'
const inputClass =
  '!rounded-[var(--kiwi-radius-sm)] !border-[var(--kiwi-border-strong)] !bg-white !text-[var(--kiwi-text)] placeholder:!text-[var(--kiwi-text-3)] focus:!border-[var(--kiwi-blue)] focus:!ring-1 focus:!ring-[var(--kiwi-blue)]'
const selectClass =
  '!h-10 !rounded-[var(--kiwi-radius-sm)] !border-[var(--kiwi-border)] !bg-white !text-[var(--kiwi-text)] text-sm focus:!border-[var(--kiwi-blue)] focus:!ring-1 focus:!ring-[var(--kiwi-blue)]'
const primaryButtonClass =
  'h-10 w-full !rounded-[var(--kiwi-radius)] !bg-[var(--kiwi-blue)] !px-4 !py-2 !text-sm !font-semibold !text-white transition-colors duration-150 hover:!bg-[#2f4ac5]'
const secondaryButtonClass =
  '!rounded-[var(--kiwi-radius)] !border !border-[var(--kiwi-border)] !bg-white !px-4 !py-2 !text-sm !text-[var(--kiwi-text-2)] hover:!border-[var(--kiwi-blue)] hover:!bg-[var(--kiwi-blue-pale)] hover:!text-[var(--kiwi-blue)]'

function normalizeBatchPrepError(message: string) {
  const text = String(message ?? '').trim()
  if (!text) return 'Could not connect to KIWI backend. Make sure KIWI is running, then try again.'
  if (/failed to fetch|networkerror|load failed|api is unreachable|request failed/i.test(text)) {
    return 'Could not connect to KIWI backend. Make sure KIWI is running, then try again.'
  }
  if (/source folder not found/i.test(text)) {
    return 'Source folder not found. Check the path and try again.'
  }
  return text
}

export default function BatchPrepPage() {
  const [sourceFolder, setSourceFolder] = useState('')
  const [outputFolder, setOutputFolder] = useState('')
  const [batchSize, setBatchSize] = useState('300')
  const [batchMode, setBatchMode] = useState<BatchMode>('fixed')
  const [pattern, setPattern] = useState('300,400,500')
  const [copyMode, setCopyMode] = useState<CopyMode>('copy')
  const [removeEmpty, setRemoveEmpty] = useState(true)
  const [detectNearEmpty, setDetectNearEmpty] = useState(true)
  const [createManifest, setCreateManifest] = useState(true)
  const [minTextChars, setMinTextChars] = useState('20')

  const [loadingPreview, setLoadingPreview] = useState(false)
  const [loadingRun, setLoadingRun] = useState(false)
  const [error, setError] = useState('')
  const [previewResult, setPreviewResult] = useState<BatchPrepPreviewResponse | null>(null)
  const [runResult, setRunResult] = useState<BatchPrepRunResponse | null>(null)

  const batchSizeNumber = useMemo(() => {
    const parsed = Number(batchSize)
    if (!Number.isFinite(parsed) || parsed <= 0) return 300
    return Math.floor(parsed)
  }, [batchSize])

  const minTextCharsNumber = useMemo(() => {
    const parsed = Number(minTextChars)
    if (!Number.isFinite(parsed) || parsed < 0) return 20
    return Math.floor(parsed)
  }, [minTextChars])

  const payload: BatchPrepRequest = {
    source_folder: sourceFolder.trim(),
    output_folder: outputFolder.trim(),
    batch_size: batchSizeNumber,
    batch_mode: batchMode,
    pattern: pattern.trim(),
    copy_mode: copyMode,
    remove_empty: removeEmpty,
    detect_near_empty: detectNearEmpty,
    min_text_chars: minTextCharsNumber,
    create_manifest: createManifest,
    prepare_for_app: true
  }

  const isFormValid = Boolean(payload.source_folder && payload.output_folder)

  const handlePreview = async () => {
    setError('')
    setRunResult(null)
    if (!isFormValid) {
      setError('Please enter both Source folder and Output folder.')
      return
    }
    setLoadingPreview(true)
    try {
      const result = await previewBatchPrep(payload)
      if (result.error) {
        setError(normalizeBatchPrepError(result.error))
        setPreviewResult(null)
        return
      }
      setPreviewResult(result)
    } catch (err: unknown) {
      setError(normalizeBatchPrepError(err instanceof Error ? err.message : 'Preview failed'))
      setPreviewResult(null)
    } finally {
      setLoadingPreview(false)
    }
  }

  const handleRun = async () => {
    setError('')
    if (!isFormValid) {
      setError('Please enter both Source folder and Output folder.')
      return
    }
    setLoadingRun(true)
    try {
      const result = await runBatchPrep(payload)
      setRunResult({
        ...result,
        message: `Created ${result.batches_created} batches from ${result.usable_files} usable files.`
      })
    } catch (err: unknown) {
      setRunResult(null)
      setError(normalizeBatchPrepError(err instanceof Error ? err.message : 'Batch prep run failed'))
    } finally {
      setLoadingRun(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-56px-3rem)] bg-[#f3f4f6] px-3 py-4 md:px-4">
      <div className="mx-auto grid w-full max-w-[1280px] grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-5">
        <section className={`${cardClass} p-5`}>
          <h1 className="text-xl font-bold text-[var(--kiwi-text)]">Batch Your Files</h1>
          <p className="mt-2 text-sm text-[var(--kiwi-text-2)]">
            If you have more than 500 files, split them into smaller batches first. Very large folders may slow down or
            crash processing.
          </p>
          <div className="mt-4 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-amber)] bg-[var(--kiwi-amber-light)] px-3 py-2 text-sm text-[var(--kiwi-amber)]">
            Recommended: 300-500 files per batch. Use Copy mode first so your original files stay untouched.
          </div>

          <div className="mt-5 space-y-4">
            <div>
              <label className={`mb-1 block ${labelClass}`}>Source folder</label>
              <Input
                className={`${inputClass} font-mono text-sm`}
                placeholder="C:\\SomeLargeFolder"
                value={sourceFolder}
                onChange={(e) => setSourceFolder(e.target.value)}
              />
            </div>

            <div>
              <label className={`mb-1 block ${labelClass}`}>Output folder</label>
              <Input
                className={`${inputClass} font-mono text-sm`}
                placeholder="C:\\Users\\YourName\\Documents\\KIWI\\batches"
                value={outputFolder}
                onChange={(e) => setOutputFolder(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <label className={`mb-1 block ${labelClass}`}>Batch size</label>
                <Input
                  type="number"
                  min={1}
                  className={inputClass}
                  value={batchSize}
                  onChange={(e) => setBatchSize(e.target.value)}
                />
              </div>
              <div>
                <label className={`mb-1 block ${labelClass}`}>Copy mode</label>
                <Select className={selectClass} value={copyMode} onChange={(e) => setCopyMode(e.target.value as CopyMode)}>
                  <option value="copy">Copy files</option>
                  <option value="move">Move files</option>
                </Select>
              </div>
            </div>

            <div className="space-y-2 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-[var(--kiwi-blue-pale)] p-3">
              <label className="flex items-center justify-between gap-2 text-sm text-[var(--kiwi-text)]">
                <span>Remove empty files</span>
                <input type="checkbox" checked={removeEmpty} onChange={(e) => setRemoveEmpty(e.target.checked)} />
              </label>
              <label className="flex items-center justify-between gap-2 text-sm text-[var(--kiwi-text)]">
                <span>Detect near-empty text files</span>
                <input type="checkbox" checked={detectNearEmpty} onChange={(e) => setDetectNearEmpty(e.target.checked)} />
              </label>
              <label className="flex items-center justify-between gap-2 text-sm text-[var(--kiwi-text)]">
                <span>Create manifest CSV</span>
                <input type="checkbox" checked={createManifest} onChange={(e) => setCreateManifest(e.target.checked)} />
              </label>
            </div>

            <div className="space-y-3 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--kiwi-text-3)]">Advanced (optional)</p>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <label className={`mb-1 block ${labelClass}`}>Batch mode</label>
                  <Select className={selectClass} value={batchMode} onChange={(e) => setBatchMode(e.target.value as BatchMode)}>
                    <option value="fixed">Fixed size</option>
                    <option value="pattern">Pattern</option>
                  </Select>
                </div>
                <div>
                  <label className={`mb-1 block ${labelClass}`}>Minimum text characters</label>
                  <Input
                    type="number"
                    min={0}
                    className={inputClass}
                    value={minTextChars}
                    onChange={(e) => setMinTextChars(e.target.value)}
                  />
                </div>
              </div>
              {batchMode === 'pattern' ? (
                <div>
                  <label className={`mb-1 block ${labelClass}`}>Pattern</label>
                  <Input
                    className={`${inputClass} font-mono text-sm`}
                    value={pattern}
                    onChange={(e) => setPattern(e.target.value)}
                    placeholder="300,400,500"
                  />
                </div>
              ) : null}
            </div>

            {error ? (
              <div className="rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-red)] bg-[var(--kiwi-red-light)] px-3 py-2 text-sm text-[var(--kiwi-red)]">
                {error}
              </div>
            ) : null}

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Button className={secondaryButtonClass} onClick={handlePreview} disabled={loadingPreview || loadingRun}>
                {loadingPreview ? 'Previewing...' : 'Preview Batches'}
              </Button>
              <Button className={primaryButtonClass} onClick={handleRun} disabled={loadingRun || loadingPreview}>
                {loadingRun ? 'Creating...' : 'Create Batches'}
              </Button>
            </div>
          </div>
        </section>

        <section className={`${cardClass} p-5`}>
          <h2 className="text-lg font-bold text-[var(--kiwi-text)]">Preview / Results</h2>

          {previewResult ? (
            <div className="mt-4 space-y-3 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-white p-4">
              <p className="text-sm font-semibold text-[var(--kiwi-text)]">Preview</p>
              <div className="grid grid-cols-2 gap-2 text-sm text-[var(--kiwi-text-2)]">
                <p>Total files: {previewResult.total_files}</p>
                <p>Usable files: {previewResult.usable_files}</p>
                <p>Empty / near-empty files: {previewResult.empty_files}</p>
                <p>Estimated batches: {previewResult.estimated_batches}</p>
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--kiwi-text-3)]">
                  Batch names and counts
                </p>
                <ul className="max-h-56 space-y-1 overflow-auto rounded border border-[var(--kiwi-border)] bg-[var(--kiwi-blue-pale)] p-2 text-sm text-[var(--kiwi-text)]">
                  {previewResult.batches_preview.map((batch) => (
                    <li key={batch.name}>
                      {batch.name}: {batch.count}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}

          {runResult ? (
            <div className="mt-4 space-y-3 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-green)] bg-[var(--kiwi-green-light)] p-4">
              <p className="text-sm font-semibold text-[var(--kiwi-green)]">Batch creation complete</p>
              <div className="grid grid-cols-1 gap-1 text-sm text-[var(--kiwi-text)]">
                <p>Total files: {runResult.total_files}</p>
                <p>Usable files: {runResult.usable_files}</p>
                <p>Empty files: {runResult.empty_files}</p>
                <p>Batches created: {runResult.batches_created}</p>
                <p>Batch names: {runResult.batch_names.join(', ') || 'None'}</p>
                <p>Manifest path: {runResult.manifest_path ?? 'Not created'}</p>
                <p>Output folder: {runResult.output_folder}</p>
                <p>Message: {runResult.message}</p>
              </div>

              <div className="rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-blue)] bg-[var(--kiwi-blue-pale)] p-3 text-sm text-[var(--kiwi-blue)]">
                <p className="font-semibold">Next step:</p>
                <p className="mt-1">
                  Go back to Home and use one of these folders as your Current Batch Folder.
                </p>
                <ul className="mt-2 space-y-1 font-mono text-xs">
                  {runResult.batch_names.map((name) => (
                    <li key={name}>{`${runResult.output_folder}\\prepared_for_app\\source_batches\\${name}`}</li>
                  ))}
                </ul>
                <Link href="/setup" className="mt-3 inline-block">
                  <Button className={secondaryButtonClass}>Back to Home</Button>
                </Link>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-[var(--kiwi-text-2)]">
              Preview batches first, then create them. Results will appear here.
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
