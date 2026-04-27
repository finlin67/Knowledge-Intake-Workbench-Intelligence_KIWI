'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, FolderOpen, Info } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { HelpIcon } from '@/components/ui/HelpIcon'
import { RefreshTipBanner } from '@/components/ui/RefreshTipBanner'
import {
  clearQueue,
  createProject,
  getApiBaseUrl,
  getQueue,
  getToken,
  loadProject,
  runExport,
  scanProject
} from '@/lib/api'
import { useProjectContext } from '@/lib/context'

const inputClass =
  '!rounded-[var(--kiwi-radius-sm)] !border-[var(--kiwi-border-strong)] !bg-white !text-[var(--kiwi-text)] placeholder:!text-[var(--kiwi-text-3)] focus:!border-[var(--kiwi-blue)] focus:!ring-1 focus:!ring-[var(--kiwi-blue)]'
const selectClass =
  '!h-10 !rounded-[var(--kiwi-radius-sm)] !border-[var(--kiwi-border)] !bg-white !text-[var(--kiwi-text)] text-sm focus:!border-[var(--kiwi-blue)] focus:!ring-1 focus:!ring-[var(--kiwi-blue)]'
const FORM_DRAFT_KEY = 'kiwi_setup_form_draft'
const PROJECT_SYNC_KEY = 'kiwi_project_sync_signature'
const DEFAULT_IMPORT_BASE = 'C:\\Users\\YourName\\Documents\\KIWI\\import'
const DEFAULT_EXPORT_BASE = 'C:\\Users\\YourName\\Documents\\KIWI\\export'
const cardClass = 'rounded-xl border border-[var(--kiwi-border)] bg-white shadow-sm'
const helpTextClass = 'text-[12.5px] leading-relaxed text-[var(--kiwi-text-3)]'
const labelClass = 'text-[13px] font-medium text-[var(--kiwi-text-2)]'
const secondaryButtonClass =
  '!rounded-[var(--kiwi-radius)] !border !border-[var(--kiwi-border)] !bg-white !px-4 !py-2 !text-sm !text-[var(--kiwi-text-2)] hover:!border-[var(--kiwi-blue)] hover:!bg-[var(--kiwi-blue-pale)] hover:!text-[var(--kiwi-blue)]'
const primaryButtonClass =
  'h-10 w-full !rounded-[var(--kiwi-radius)] !bg-[var(--kiwi-blue)] !px-4 !py-2 !text-sm !font-semibold !text-white transition-colors duration-150 hover:!bg-[#2f4ac5]'
const successButtonClass =
  'h-10 w-full !rounded-[var(--kiwi-radius)] !bg-[var(--kiwi-green)] !px-4 !py-2 !text-sm !font-semibold !text-white hover:!bg-[#27863a]'
const cardHeaderBorderClass = 'border-b border-[var(--kiwi-border)] pb-2'

const profileLabel: Record<'anythingllm' | 'open_webui' | 'both', string> = {
  anythingllm: 'AnythingLLM',
  open_webui: 'Open WebUI',
  both: 'Both'
}

const tableColumns = ['file_id', 'filename', 'subfolder', 'next_stage', 'status', 'workspace', 'updated_at'] as const
type ProjectStateMode = 'unsaved' | 'saved' | 'editing'
type BatchState = 'empty' | 'ready_to_scan' | 'scanned' | 'running' | 'complete' | 'failed'

const BATCH_SYNC_KEY = 'kiwi_batch_sync_path'

type RunSettingsReview = {
  provider: string
  model: string
  aiMode: string
  confidenceThreshold: string
  autoAssignWorkspace: string
  exportProfile: 'anythingllm' | 'open_webui' | 'both'
  workspaceMappings: string[]
  keywordMappings: string[]
}

const RUN_SETTINGS_FALLBACK: RunSettingsReview = {
  provider: 'Not configured',
  model: 'Not configured',
  aiMode: 'Default',
  confidenceThreshold: 'Default',
  autoAssignWorkspace: 'Off',
  exportProfile: 'both',
  workspaceMappings: [],
  keywordMappings: []
}

function toBatchName(path: string) {
  const normalized = path.trim().replace(/\\+$/g, '').replace(/\/+$/g, '')
  if (!normalized) return ''
  const parts = normalized.split(/[/\\]/).filter(Boolean)
  return parts[parts.length - 1] ?? ''
}

function suggestNextBatchName(value: string) {
  const input = value.trim()
  if (!input) return ''
  const match = input.match(/^(.*?)(\d+)([^\d]*)$/)
  if (!match) return input
  const [, prefix, digits, suffix] = match
  const width = digits.length
  const incremented = String(Number(digits) + 1).padStart(width, '0')
  return `${prefix}${incremented}${suffix}`
}

function normalizeBackendMessage(message: string) {
  const text = String(message ?? '').trim()
  if (!text) {
    return 'Could not connect to KIWI backend. Check that KIWI is running, then click Retry.'
  }
  if (/session not found|missing session token/i.test(text)) {
    return 'Your KIWI session expired (often after backend restart). Click Save Project or Reload Project, then scan again.'
  }
  if (/failed to fetch|networkerror|load failed|api is unreachable/i.test(text)) {
    return 'Could not connect to KIWI backend. Check that KIWI is running, then click Retry.'
  }
  return text
}

function safeParseJson(raw: string | null) {
  if (!raw) return null
  try {
    return JSON.parse(raw) as unknown
  } catch {
    return null
  }
}

function pickStoredValue(keys: string[]) {
  for (const key of keys) {
    const value = localStorage.getItem(key)
    if (value && value.trim()) return value.trim()
  }
  return ''
}

function pickStoredExportProfile(defaultValue: 'anythingllm' | 'open_webui' | 'both') {
  const raw = pickStoredValue(['kiwi_profile', 'kiwi_export_profile']).toLowerCase()
  if (raw === 'anythingllm' || raw === 'open_webui' || raw === 'both') return raw
  return defaultValue
}

function formatOnOff(value: string) {
  const normalized = value.trim().toLowerCase()
  if (!normalized) return 'Off'
  if (['1', 'true', 'yes', 'on'].includes(normalized)) return 'On'
  if (['0', 'false', 'no', 'off'].includes(normalized)) return 'Off'
  return 'Off'
}

function readMappedEntries(raw: unknown): string[] {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return []
  return Object.entries(raw as Record<string, unknown>)
    .filter(([key, value]) => String(key).trim() && String(value ?? '').trim())
    .map(([key, value]) => `${key} -> ${String(value)}`)
}

function readArrayEntries(raw: unknown): string[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => String(item ?? '').trim()).filter(Boolean)
}

function buildRunSettingsReview(defaultExportProfile: 'anythingllm' | 'open_webui' | 'both'): RunSettingsReview {
  const rawProvider = pickStoredValue(['kiwi_ai_provider', 'kiwi_provider', 'kiwi_quick_ai'])
  const provider = !rawProvider || rawProvider.toLowerCase() === 'none' ? 'Not configured' : rawProvider
  const model = pickStoredValue(['kiwi_ai_model', 'kiwi_model', 'kiwi_ollama_model']) || 'Not configured'
  const aiMode = pickStoredValue(['kiwi_ai_mode', 'kiwi_mode']) || 'Default'
  const confidenceThreshold = pickStoredValue(['kiwi_confidence_threshold', 'kiwi_threshold']) || 'Default'
  const autoAssignWorkspace = formatOnOff(pickStoredValue(['kiwi_auto_assign_workspace', 'kiwi_auto_assign']))
  const exportProfile = pickStoredExportProfile(defaultExportProfile)

  const workspacesRaw = safeParseJson(localStorage.getItem('kiwi_workspaces'))
  const workspaceMapRaw = safeParseJson(localStorage.getItem('kiwi_workspace_map'))
  const companyMapRaw = safeParseJson(localStorage.getItem('kiwi_company_map'))
  const projectMapRaw = safeParseJson(localStorage.getItem('kiwi_project_map'))

  const keywordMapRaw = safeParseJson(localStorage.getItem('kiwi_keyword_map'))
  const keywordsRaw = safeParseJson(localStorage.getItem('kiwi_keywords'))

  const workspaceMappings = [
    ...readMappedEntries(workspaceMapRaw),
    ...readMappedEntries(companyMapRaw),
    ...readMappedEntries(projectMapRaw),
    ...readArrayEntries(workspacesRaw)
  ]
  const keywordMappings = [...readMappedEntries(keywordMapRaw), ...readArrayEntries(keywordsRaw)]

  return {
    ...RUN_SETTINGS_FALLBACK,
    provider,
    model,
    aiMode,
    confidenceThreshold,
    autoAssignWorkspace,
    exportProfile,
    workspaceMappings: Array.from(new Set(workspaceMappings)),
    keywordMappings: Array.from(new Set(keywordMappings))
  }
}

function ProjectSummaryBar({
  projectName,
  projectState,
  exportProfile,
  exportFolder,
  backendHealthy,
  currentBatchName
}: {
  projectName: string
  projectState: ProjectStateMode
  exportProfile: 'anythingllm' | 'open_webui' | 'both'
  exportFolder: string
  backendHealthy: boolean | null
  currentBatchName: string
}) {
  const stateLabel = projectState === 'saved' ? 'Saved' : projectState === 'editing' ? 'Unsaved changes' : 'Unsaved'
  return (
    <div className="col-span-12 rounded-xl border border-[var(--kiwi-border)] bg-[#f8faff] px-4 py-2 md:px-5">
      <div className="flex flex-wrap items-start justify-between gap-1.5 md:gap-2.5 text-xs text-[var(--kiwi-text-2)]">
        <div className="flex flex-wrap items-center gap-1.5">
        <span className="inline-flex items-center rounded-full bg-[var(--kiwi-blue-pale)] px-3 py-1 font-medium text-[var(--kiwi-blue)]">
          Project: {projectName || 'No project yet'}
        </span>
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 font-medium ${
            projectState === 'saved'
              ? 'bg-[var(--kiwi-green-light)] text-[var(--kiwi-green)]'
              : projectState === 'editing'
                ? 'bg-[var(--kiwi-blue-light)] text-[var(--kiwi-blue)]'
                : 'bg-[var(--kiwi-amber-light)] text-[var(--kiwi-amber)]'
          }`}
        >
          {stateLabel}
        </span>
        <span className="inline-flex items-center rounded-full bg-[var(--kiwi-blue-pale)] px-3 py-1 font-medium text-[var(--kiwi-blue)]">
          Export profile: {profileLabel[exportProfile]}
        </span>
        <span className="inline-flex items-center gap-1 rounded-full bg-[var(--kiwi-blue-pale)] px-3 py-1 font-medium text-[var(--kiwi-blue)]">
          <span title="This is where KIWI saves the organized output. Keep this the same for all batches in one project.">Export folder: {exportFolder || 'Not set'}</span>
        </span>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-3 py-1 font-medium ${
            backendHealthy === true
              ? 'bg-[var(--kiwi-green-light)] text-[var(--kiwi-green)]'
              : backendHealthy === false
                ? 'bg-[var(--kiwi-red-light)] text-[var(--kiwi-red)]'
                : 'bg-[var(--kiwi-blue-light)] text-[var(--kiwi-blue)]'
          }`}
          title="Backend Online means the local KIWI service is running and ready."
        >
          Backend: {backendHealthy === true ? 'Online' : backendHealthy === false ? 'Offline' : 'Checking'}
        </span>
        </div>
        <p className="text-xs text-[var(--kiwi-text-3)]">Current batch: {currentBatchName || 'None'}</p>
      </div>
    </div>
  )
}

function PathTipBanner({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="flex items-start gap-4 rounded-[var(--kiwi-radius)] border border-[var(--kiwi-blue-light)] bg-[var(--kiwi-blue-pale)] p-4 text-sm text-[var(--kiwi-blue)]">
      <span className="text-lg">💡</span>
      <div>
        <strong>How to select folders:</strong> Use short folder names with your base paths (recommended), or switch
        either field to manual mode and paste a full path from File Explorer.
        <button className="ml-2 underline opacity-60 hover:opacity-100" onClick={onDismiss}>
          Got it
        </button>
      </div>
    </div>
  )
}

function SupportedFileTypesButton() {
  return (
    <div className="group relative">
      <button
        type="button"
        className="inline-flex items-center gap-2 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-white px-3 py-2 text-xs text-[var(--kiwi-text-2)] hover:text-[var(--kiwi-text)]"
        aria-label="Supported file types"
      >
        <Info className="h-3.5 w-3.5" />
        File Types
      </button>
      <div className="pointer-events-none absolute right-0 top-full z-20 mt-2 hidden w-[320px] rounded-[var(--kiwi-radius)] border border-[var(--kiwi-border)] bg-white p-3 shadow-lg group-hover:block group-focus-within:block">
        <p className="mb-2 text-xs font-semibold text-[var(--kiwi-text)]">Supported File Types</p>
        <div className="mb-2 flex flex-wrap gap-2">
          {['PDF', 'Word (.docx)', 'PowerPoint (.pptx)', 'Markdown (.md)', 'Text (.txt)'].map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 rounded-full border border-[var(--kiwi-border)] bg-[var(--kiwi-blue-pale)] px-2 py-0.5 text-[11px] text-[var(--kiwi-text)]"
            >
              <CheckCircle2 className="h-3 w-3 text-[var(--kiwi-green)]" />
              {t}
            </span>
          ))}
        </div>
        <div className="mb-1 flex flex-wrap gap-2">
          {['Images', 'Audio', 'Video'].map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 rounded-full border border-[var(--kiwi-red-light)] bg-[var(--kiwi-red-light)] px-2 py-0.5 text-[11px] text-[var(--kiwi-red)]"
            >
              <AlertTriangle className="h-3 w-3" />
              {t} — not supported
            </span>
          ))}
        </div>
        <p className="text-[11px] text-[var(--kiwi-text-2)]">For best results use text-based documents</p>
      </div>
    </div>
  )
}

function WorkspaceList() {
  const [workspaces, setWorkspaces] = useState<string[]>([])

  useEffect(() => {
    const raw = localStorage.getItem('kiwi_workspaces')
    if (raw) {
      try {
        setWorkspaces(JSON.parse(raw))
      } catch {
        // ignore malformed workspace cache
      }
    } else {
      setWorkspaces(['career_portfolio', 'ai_projects', 'archive', 'case_studies', 'wiki'])
    }
  }, [])

  return (
    <div className="flex flex-wrap gap-2">
      {workspaces.map((ws) => (
        <span
          key={ws}
          className="rounded-full border border-[#c5cae9] bg-[#eef2ff] px-2 py-1 text-xs text-[#3b5bdb]"
        >
          {ws}
        </span>
      ))}
    </div>
  )
}

type ExistingProjectPanelProps = {
  loadExistingOpen: boolean
  existingPath: string
  loading: boolean
  onToggle: () => void
  onPathChange: (value: string) => void
  onPastePath: () => void
  onClearPath: () => void
  onReload: () => void
}

function ExistingProjectPanel({
  loadExistingOpen,
  existingPath,
  loading,
  onToggle,
  onPathChange,
  onPastePath,
  onClearPath,
  onReload
}: ExistingProjectPanelProps) {
  return (
    <div className={`${cardClass} overflow-hidden`}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-[var(--kiwi-blue-pale)]"
      >
        <span className="flex items-center gap-2 font-semibold text-[var(--kiwi-text)]">
          <FolderOpen className="h-5 w-5 text-[var(--kiwi-blue)]" />
          Load Existing Project
        </span>
        {loadExistingOpen ? (
          <ChevronDown className="h-5 w-5 text-[var(--kiwi-text-2)]" />
        ) : (
          <ChevronRight className="h-5 w-5 text-[var(--kiwi-text-2)]" />
        )}
      </button>
      {loadExistingOpen ? (
        <div className="space-y-4 border-t border-[var(--kiwi-border)] px-4 pb-4 pt-4">
          <div className="space-y-2">
            <label className={labelClass}>Existing project output folder</label>
            <Input
              className={`${inputClass} min-w-0 flex-1 font-mono text-sm`}
              placeholder="Paste full path e.g. C:\\Users\\YourName\\Documents\\KIWI\\output"
              value={existingPath}
              onChange={(e) => onPathChange(e.target.value)}
            />
            <div className="flex flex-wrap gap-3">
              <Button
                variant="secondary"
                type="button"
                className={`${secondaryButtonClass} shrink-0 !text-xs`}
                onClick={onPastePath}
              >
                📋 Paste
              </Button>
              <Button
                variant="secondary"
                type="button"
                className={`${secondaryButtonClass} shrink-0 !text-xs`}
                onClick={onClearPath}
              >
                Clear path
              </Button>
            </div>
            <p className="text-xs text-[var(--kiwi-text-2)]">
              In File Explorer, click the address bar - Ctrl+C to copy the path - click Paste
            </p>
          </div>
          <p className="text-xs text-[var(--kiwi-text-2)]">Continue from a project you already created.</p>
          <Button
            variant="secondary"
            className={secondaryButtonClass}
            onClick={onReload}
            disabled={loading}
          >
            Load Existing Project
          </Button>
        </div>
      ) : null}
    </div>
  )
}

function SidebarStep({
  number,
  title,
  text,
  link,
  linkLabel,
  active,
  complete
}: {
  number: number
  title: string
  text: string
  link?: string
  linkLabel?: string
  active?: boolean
  complete?: boolean
}) {
  return (
    <div className="flex gap-3 relative">
      {number < 5 && (
        <div className="absolute left-3.5 top-7 w-px h-full bg-[#dde1f0]" />
      )}
      <div
        className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold z-10 ${
          complete
            ? 'bg-[#d3f9d8] text-[#2f9e44]'
            : active
              ? 'bg-[#3b5bdb] text-white'
              : 'bg-[#f3f4f8] text-[#9ca3af]'
        }`}
      >
        {complete ? '✓' : number}
      </div>
      <div className="pb-5">
        <p className={`text-xs font-semibold mb-0.5 ${active ? 'text-[#3b5bdb]' : 'text-[#1a1a2e]'}`}>{title}</p>
        <p className="text-[0.7rem] text-[#6b7280] leading-relaxed">{text}</p>
        {link ? (
          <a href={link} className="text-[0.7rem] text-[#3b5bdb] hover:underline mt-1 block">
            {linkLabel}
          </a>
        ) : null}
      </div>
    </div>
  )
}

export default function SetupPage() {
  const searchParams = useSearchParams()
  const { setProject } = useProjectContext()
  const initialFormState = {
    name: '',
    sourceFolderName: '',
    outputFolderName: '',
    sourceFolderPath: '',
    outputFolderPath: '',
    sourcePathMode: 'base' as 'base' | 'manual',
    outputPathMode: 'base' as 'base' | 'manual',
    exportProfile: 'anythingllm' as 'anythingllm' | 'open_webui' | 'both'
  }

  const [form, setForm] = useState(initialFormState)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [existingPath, setExistingPath] = useState('')
  const [loadExistingOpen, setLoadExistingOpen] = useState(false)
  const [showPathTip, setShowPathTip] = useState(true)

  const [currentBatch, setCurrentBatch] = useState<Record<string, unknown>[]>([])
  const [pendingQueue, setPendingQueue] = useState<Record<string, unknown>[]>([])
  const [sortKey, setSortKey] = useState<string>('status')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [queueError, setQueueError] = useState('')
  const [queueLoading, setQueueLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [runQueueRunning, setRunQueueRunning] = useState(false)
  const [pendingQueueRunning, setPendingQueueRunning] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [runMessage, setRunMessage] = useState('')
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [projectSaved, setProjectSaved] = useState(false)
  const [projectState, setProjectState] = useState<ProjectStateMode>('unsaved')
  const [batchState, setBatchState] = useState<BatchState>('empty')
  const [lastScannedBatchName, setLastScannedBatchName] = useState('')
  const [lastScannedFileCount, setLastScannedFileCount] = useState(0)
  const [lastCompletedBatchName, setLastCompletedBatchName] = useState('')
  const [lastScanTargetPath, setLastScanTargetPath] = useState('')
  const [activeProfile, setActiveProfile] = useState<'anythingllm' | 'open_webui' | 'both'>('anythingllm')
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null)
  const [backendMessage, setBackendMessage] = useState('Checking backend...')
  const [backendChecking, setBackendChecking] = useState(false)
  const [importBase, setImportBase] = useState(DEFAULT_IMPORT_BASE)
  const [exportBase, setExportBase] = useState(DEFAULT_EXPORT_BASE)
  const [quickAiProvider, setQuickAiProvider] = useState('none')
  const [showQuickSettings, setShowQuickSettings] = useState(true)
  const [pendingOpen, setPendingOpen] = useState(false)
  const [reviewSettingsOpen, setReviewSettingsOpen] = useState(false)
  const [leftReviewSettingsOpen, setLeftReviewSettingsOpen] = useState(false)
  const [queueAiFilter, setQueueAiFilter] = useState<'all' | 'ai' | 'rules'>('all')
  const [queueMatchedByFilter, setQueueMatchedByFilter] = useState('all')
  const [queueNeedsReviewOnly, setQueueNeedsReviewOnly] = useState(false)
  const [runSettingsReview, setRunSettingsReview] = useState<RunSettingsReview>(RUN_SETTINGS_FALLBACK)
  const draftHydratedRef = useRef(false)
  const skipFirstDraftPersistRef = useRef(true)
  const quickAiHydratedRef = useRef(false)
  const batchFolderInputRef = useRef<HTMLInputElement | null>(null)
  const consecutiveHealthFailuresRef = useRef(0)
  const manualProjectEditRef = useRef(false)

  const normalizedImportBase = importBase.trim().replace(/[\\/]+$/, '')
  const normalizedExportBase = exportBase.trim().replace(/[\\/]+$/, '')
  const resolvedSourcePath = form.sourceFolderName.trim()
    ? `${normalizedImportBase}\\${form.sourceFolderName.trim()}`
    : ''
  const resolvedOutputPath = form.outputFolderPath.trim() || normalizedExportBase
  const projectName = form.name.trim()
  const importPath = resolvedSourcePath.trim()
  const currentProjectSignature = JSON.stringify({
    name: projectName,
    output_folder: resolvedOutputPath.trim(),
    export_profile: form.exportProfile
  })
  const hasActiveProject = Boolean(sessionToken)
  const currentBatchName = toBatchName(importPath)
  const canSaveProject = Boolean(projectName && resolvedOutputPath.trim() && form.exportProfile)
  const canScanBatch = Boolean(
    projectName && resolvedOutputPath.trim() && normalizedImportBase && form.sourceFolderName.trim()
  )
  const canRunBatch =
    batchState === 'scanned' && (currentBatch.length > 0 || pendingQueue.length > 0 || lastScannedFileCount > 0) && !running
  const canStartNextBatch = batchState === 'complete'
  const hasUnsavedProjectChanges = projectState === 'editing'
  const scanSucceeded = batchState === 'scanned' || batchState === 'running' || batchState === 'complete'
  const hasScannedBatch =
    scanSucceeded || lastScannedFileCount > 0 || currentBatch.length > 0 || pendingQueue.length > 0
  const runCompleted = batchState === 'complete' || runMessage.toLowerCase().includes('complete')
  const nextBatchPrepared = batchState === 'empty' && Boolean(lastCompletedBatchName)

  const loadQueue = useCallback(async (options?: { surfaceError?: boolean }) => {
    const surfaceError = options?.surfaceError ?? false
    if (surfaceError) {
      setQueueError('')
    }
    const token = getToken()
    setSessionToken(token)
    const selectedProfile = (localStorage.getItem('kiwi_profile') ??
      localStorage.getItem('kiwi_export_profile') ??
      'anythingllm') as 'anythingllm' | 'open_webui' | 'both'
    setActiveProfile(selectedProfile)
    if (!token) {
      setCurrentBatch([])
      setPendingQueue([])
      return { currentCount: 0, pendingCount: 0 }
    }
    setQueueLoading(true)
    try {
      const data = await getQueue()
      const currentRows = data.current_batch_queue ?? []
      const pendingRows = selectedProfile === 'both' ? data.pending_queue ?? data.other_pending_queue ?? [] : []
      setCurrentBatch(currentRows)
      setPendingQueue(pendingRows)
      if (surfaceError) {
        setQueueError('')
      }
      return { currentCount: currentRows.length, pendingCount: pendingRows.length }
    } catch (err: unknown) {
      if (surfaceError) {
        setQueueError(
          normalizeBackendMessage(err instanceof Error ? err.message : 'Could not connect to KIWI backend. Check that KIWI is running, then click Retry.')
        )
      }
      return { currentCount: 0, pendingCount: 0 }
    } finally {
      setQueueLoading(false)
    }
  }, [])

  const handleRunQueue = async () => {
    setQueueError('')
    setRunMessage('Running batch...')
    setBatchState('running')
    const activeToken = getToken()
    setSessionToken(activeToken)
    if (!activeToken) {
      setRunMessage('')
      setQueueError('No active project yet. Save your project on the left to begin.')
      setBatchState('failed')
      return
    }
    setRunning(true)
    setRunQueueRunning(true)
    try {
      const payload = await runExport(
        (localStorage.getItem('kiwi_profile') ??
          localStorage.getItem('kiwi_export_profile') ??
          'anythingllm') as 'anythingllm' | 'open_webui' | 'both'
      )
      const totalCount = Object.values((payload as { results?: Record<string, unknown> })?.results ?? {}).reduce(
        (sum: number, item: unknown) => {
          const it = item as { files_finished_ok?: number; files_started?: number; count?: number }
          return sum + Number(it?.files_finished_ok ?? it?.files_started ?? it?.count ?? 0)
        },
        0
      )
      const finishedBatch = currentBatchName || lastScannedBatchName || 'Current batch'
      setRunMessage(`${finishedBatch} is complete. You can now start the next batch.`)
      setLastCompletedBatchName(finishedBatch)
      setBatchState('complete')
      await loadQueue({ surfaceError: false })
    } catch (err: unknown) {
      setRunMessage('')
      setQueueError(
        normalizeBackendMessage(
          err instanceof Error
            ? err.message
            : 'Could not connect to KIWI backend. Check that KIWI is running, then click Retry.'
        )
      )
      setBatchState('failed')
    } finally {
      setRunQueueRunning(false)
      setRunning(false)
    }
  }

  const handleRunPendingQueue = async () => {
    setQueueError('')
    setRunMessage('Processing pending queue...')
    setBatchState('running')
    const activeToken = getToken()
    setSessionToken(activeToken)
    if (!activeToken) {
      setRunMessage('')
      setQueueError('No active project yet. Save your project on the left to begin.')
      setBatchState('failed')
      return
    }
    if (pendingQueue.length === 0) {
      setRunMessage('')
      setQueueError('No pending files available to process.')
      setBatchState('failed')
      return
    }
    setRunning(true)
    setPendingQueueRunning(true)
    try {
      const payload = await runExport(
        (localStorage.getItem('kiwi_profile') ??
          localStorage.getItem('kiwi_export_profile') ??
          'anythingllm') as 'anythingllm' | 'open_webui' | 'both'
      )
      const totalCount = Object.values((payload as { results?: Record<string, unknown> })?.results ?? {}).reduce(
        (sum: number, item: unknown) => {
          const it = item as { files_finished_ok?: number; files_started?: number; count?: number }
          return sum + Number(it?.files_finished_ok ?? it?.files_started ?? it?.count ?? 0)
        },
        0
      )
      setRunMessage(
        totalCount > 0
          ? `Pending queue complete. Processed ${totalCount} file${totalCount === 1 ? '' : 's'}.`
          : 'Pending queue complete.'
      )
      setBatchState('complete')
      await loadQueue({ surfaceError: false })
    } catch (err: unknown) {
      setRunMessage('')
      setQueueError(
        normalizeBackendMessage(
          err instanceof Error
            ? err.message
            : 'Could not connect to KIWI backend. Check that KIWI is running, then click Retry.'
        )
      )
      setBatchState('failed')
    } finally {
      setPendingQueueRunning(false)
      setRunning(false)
    }
  }

  const checkBackendHealth = useCallback(async (options?: { surfaceError?: boolean }) => {
    const surfaceError = options?.surfaceError ?? false
    setBackendChecking(true)
    try {
      const apiBase = await getApiBaseUrl()
      const response = await fetch(`${apiBase}/api/health`)
      const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      if (!contentType.includes('application/json')) {
        throw new Error('Unexpected response type')
      }
      const payload = await response.json().catch(() => ({}))
      if (payload?.status !== 'ok') {
        throw new Error('Invalid health payload')
      }
      consecutiveHealthFailuresRef.current = 0
      setBackendHealthy(true)
      setBackendMessage('Backend API is running')
      setQueueError('')
    } catch (err: unknown) {
      consecutiveHealthFailuresRef.current += 1
      const reason = err instanceof Error ? err.message : 'Request failed'
      const normalized = normalizeBackendMessage(reason)
      if (consecutiveHealthFailuresRef.current >= 2 || surfaceError) {
        setBackendHealthy(false)
        setBackendMessage(normalized)
      }
      if (surfaceError) {
        setQueueError(normalized)
      }
    } finally {
      setBackendChecking(false)
    }
  }, [])

  const handleClearQueue = async () => {
    setQueueError('')
    setRunMessage('')
    setClearing(true)
    try {
      const profile =
        (localStorage.getItem('kiwi_profile') as 'anythingllm' | 'open_webui' | 'both' | null) ??
        (localStorage.getItem('kiwi_export_profile') as 'anythingllm' | 'open_webui' | 'both' | null) ??
        'anythingllm'
      const result = await clearQueue(profile)
      setRunMessage(`Cleared ${result.cleared_count} queued item(s) for ${profile}.`)
      await loadQueue({ surfaceError: true })
    } catch (err: unknown) {
      setQueueError(
        normalizeBackendMessage(err instanceof Error ? err.message : 'Could not connect to KIWI backend. Check that KIWI is running, then click Retry.')
      )
    } finally {
      setClearing(false)
    }
  }

  const handleSaveProject = async () => {
    setError('')
    if (!projectName || !resolvedOutputPath.trim()) {
      setError('Please provide a project name and export folder.')
      return
    }
    setLoading(true)
    setStatusMessage('Saving project...')
    try {
      localStorage.setItem('kiwi_profile', form.exportProfile)
      localStorage.setItem('kiwi_export_profile', form.exportProfile)
      const project = await createProject({
        name: projectName,
        raw_folder: importPath || importBase,
        output_folder: resolvedOutputPath
      })
      localStorage.setItem('kiwi_path_tip_dismissed', '1')
      setShowPathTip(false)
      localStorage.setItem(PROJECT_SYNC_KEY, currentProjectSignature)
      setProject(project)
      setStatusMessage('Project saved')
      setSessionToken(project.session_token)
      localStorage.setItem('kiwi_session', project.session_token)
      localStorage.setItem(BATCH_SYNC_KEY, importPath || importBase)
      setProjectSaved(true)
      setProjectState('saved')
      manualProjectEditRef.current = false
      setBatchState(importPath ? 'ready_to_scan' : 'empty')
      void loadQueue({ surfaceError: false })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Project save failed.')
      setStatusMessage('')
    } finally {
      setLoading(false)
    }
  }

  const handleScanBatch = async () => {
    setError('')
    setQueueError('')
    setRunMessage('')
    if (!projectName || !resolvedOutputPath.trim()) {
      setError('Please provide a project name and export path before scanning.')
      return
    }
    if (!importPath) {
      setError('Please enter a current batch folder before scanning.')
      return
    }
    setLoading(true)
    setBatchState('ready_to_scan')
    setLastScanTargetPath(importPath)
    setStatusMessage(`Preparing batch scan for: ${importPath}`)
    try {
      const effectiveProjectName = projectName || 'KIWI Project'
      localStorage.setItem('kiwi_profile', form.exportProfile)
      localStorage.setItem('kiwi_export_profile', form.exportProfile)
      setStatusMessage(`Saving folder changes for: ${importPath}`)
      const project = await createProject({
        name: effectiveProjectName,
        raw_folder: importPath,
        output_folder: resolvedOutputPath
      })
      setProject(project)
      setSessionToken(project.session_token)
      localStorage.setItem('kiwi_session', project.session_token)
      localStorage.setItem(PROJECT_SYNC_KEY, currentProjectSignature)
      localStorage.setItem(BATCH_SYNC_KEY, importPath)
      setProjectSaved(true)
      setProjectState('saved')
      manualProjectEditRef.current = false
      setStatusMessage(`Scanning files from: ${importPath}`)
      const scanResult = await scanProject()
      const scannedCount = Number(scanResult.files_scanned ?? scanResult.scanned_count ?? 0)
      const queueSnapshot = await loadQueue({ surfaceError: true })
      const scannedBatch = currentBatchName || 'current batch'
      setLastScannedBatchName(scannedBatch)
      const totalQueuedCount = queueSnapshot.currentCount + queueSnapshot.pendingCount
      setLastScannedFileCount(scannedCount)
      setBatchState('scanned')
      if (scannedCount > 0 && queueSnapshot.currentCount > 0) {
        setStatusMessage(`Scanned ${scannedCount} files in ${scannedBatch}. ${queueSnapshot.currentCount} ready to run.`)
      } else if (scannedCount > 0 && queueSnapshot.pendingCount > 0) {
        setStatusMessage(
          `Scanned ${scannedCount} files in ${scannedBatch}. ${queueSnapshot.pendingCount} currently in Pending Queue. Use Process Pending Queue.`
        )
      } else if (scannedCount > 0) {
        setStatusMessage(
          `Scanned ${scannedCount} files in ${scannedBatch}, but 0 are currently queued. They may already be completed from a prior run.`
        )
      } else if (queueSnapshot.currentCount > 0) {
        setStatusMessage(`Found ${queueSnapshot.currentCount} files in ${scannedBatch}. Ready to run.`)
      } else if (queueSnapshot.pendingCount > 0) {
        setStatusMessage(
          `Found ${queueSnapshot.pendingCount} files in ${scannedBatch}, currently in Pending Queue. Use Process Pending Queue.`
        )
      } else {
        setStatusMessage(`Found 0 supported files in ${scannedBatch}. Check folder path and supported file types.`)
      }
    } catch (err: unknown) {
      setBatchState('failed')
      const detail = err instanceof Error ? normalizeBackendMessage(err.message) : ''
      setError(
        detail
          ? `Could not scan this batch. Check that the folder exists and try again. ${detail}`
          : 'Could not scan this batch. Check that the folder exists and try again.'
      )
      setStatusMessage('')
    } finally {
      setLoading(false)
    }
  }

  const handleReload = async () => {
    setError('')
    if (!existingPath) {
      setError('Please provide an output folder to reload.')
      return
    }
    setLoading(true)
    setStatusMessage('Loading existing project...')
    try {
      const project = await loadProject({ output_folder: existingPath })
      localStorage.setItem('kiwi_path_tip_dismissed', '1')
      setShowPathTip(false)
      setProject(project)
      setStatusMessage('Project loaded.')
      localStorage.setItem('kiwi_session', project.session_token)
      localStorage.setItem(PROJECT_SYNC_KEY, JSON.stringify({
        name: project.name,
        output_folder: project.output_folder,
        export_profile: (localStorage.getItem('kiwi_profile') ?? 'anythingllm')
      }))
      setProjectSaved(true)
      setProjectState('saved')
      manualProjectEditRef.current = false
      setBatchState('empty')
      void loadQueue({ surfaceError: true })
    } catch (err: unknown) {
      setError(
        normalizeBackendMessage(err instanceof Error ? err.message : 'Could not connect to KIWI backend. Check that KIWI is running, then click Retry.')
      )
      setStatusMessage('')
    } finally {
      setLoading(false)
    }
  }

  const handleStartNextBatch = () => {
    const nextBatchName =
      suggestNextBatchName(form.sourceFolderName || lastScannedBatchName || currentBatchName || '') || ''

    setForm((prev) => ({
      ...prev,
      sourceFolderName: nextBatchName
    }))
    localStorage.removeItem(BATCH_SYNC_KEY)
    setCurrentBatch([])
    setQueueError('')
    setRunMessage('')
    setStatusMessage(
      nextBatchName
        ? `Ready for next batch. Suggested folder: ${nextBatchName}`
        : 'Ready for next batch. Project settings were kept.'
    )
    setLastScannedFileCount(0)
    setLastScannedBatchName('')
    setBatchState('empty')
    window.setTimeout(() => {
      batchFolderInputRef.current?.focus()
    }, 0)
  }

  const handleResetLocalSetupData = () => {
    if (!window.confirm('Clear saved setup values from this browser? This will not delete backend files.')) {
      return
    }
    ;[
      FORM_DRAFT_KEY,
      'kiwi_draft',
      'kiwi_project_sync_signature',
      BATCH_SYNC_KEY,
      'kiwi_session',
      'kiwi_profile',
      'kiwi_export_profile',
      'kiwi_trigger_run_queue',
      'kiwi_path_tip_dismissed',
      'kiwi_quick_ai'
    ].forEach((key) => localStorage.removeItem(key))

    setForm(initialFormState)
    setProjectSaved(false)
    setProjectState('unsaved')
    manualProjectEditRef.current = false
    setBatchState('empty')
    setStatusMessage('Local setup data cleared. You can start fresh.')
    setRunMessage('')
    setError('')
    setQueueError('')
    setCurrentBatch([])
    setPendingQueue([])
    setSessionToken(null)
    setLastScannedFileCount(0)
    setLastScannedBatchName('')
    setLastCompletedBatchName('')
  }

  const getStatusBadgeClass = (value: unknown) => {
    const status = String(value ?? '').toLowerCase()
    if (status === 'new' || status === 'done' || status === 'complete' || status === 'online') return 'bg-[var(--kiwi-green-light)] text-[var(--kiwi-green)]'
    if (status === 'pending' || status === 'queued' || status === 'warning') return 'bg-[var(--kiwi-amber-light)] text-[var(--kiwi-amber)]'
    if (status === 'failed' || status === 'error' || status === 'offline') return 'bg-[var(--kiwi-red-light)] text-[var(--kiwi-red)]'
    return 'bg-[var(--kiwi-blue-light)] text-[var(--kiwi-blue)]'
  }

  const sortBy = (key: string) => {
    setSortDirection((prev) => (key === sortKey ? (prev === 'asc' ? 'desc' : 'asc') : 'asc'))
    setSortKey(key)
  }

  const sortRows = (rows: Record<string, unknown>[]) =>
    [...rows].sort((a, b) => {
      const left = String(a[sortKey] ?? '')
      const right = String(b[sortKey] ?? '')
      const compare = left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' })
      return sortDirection === 'asc' ? compare : -compare
    })

  const matchesQueueFilters = useCallback(
    (row: Record<string, unknown>) => {
      const matchedBy = String(row.matched_by ?? '').trim().toLowerCase()
      const aiUsedRaw = String(row.ai_used ?? '').trim().toLowerCase()
      const reviewRequiredRaw = String(row.review_required ?? '').trim().toLowerCase()
      const aiUsed = aiUsedRaw === '1' || aiUsedRaw === 'true' || matchedBy === 'ollama'
      const reviewRequired = reviewRequiredRaw === '1' || reviewRequiredRaw === 'true'

      if (queueAiFilter === 'ai' && !aiUsed) return false
      if (queueAiFilter === 'rules' && aiUsed) return false
      if (queueMatchedByFilter !== 'all' && matchedBy !== queueMatchedByFilter) return false
      if (queueNeedsReviewOnly && !reviewRequired) return false
      return true
    },
    [queueAiFilter, queueMatchedByFilter, queueNeedsReviewOnly]
  )

  const applyQueueQuickFilter = useCallback(
    (preset: 'all' | 'ai' | 'rules' | 'fallback' | 'review') => {
      if (preset === 'all') {
        setQueueAiFilter('all')
        setQueueMatchedByFilter('all')
        setQueueNeedsReviewOnly(false)
        return
      }
      if (preset === 'ai') {
        setQueueAiFilter('ai')
        setQueueMatchedByFilter('all')
        setQueueNeedsReviewOnly(false)
        return
      }
      if (preset === 'rules') {
        setQueueAiFilter('rules')
        setQueueMatchedByFilter('all')
        setQueueNeedsReviewOnly(false)
        return
      }
      if (preset === 'fallback') {
        setQueueAiFilter('all')
        setQueueMatchedByFilter('fallback')
        setQueueNeedsReviewOnly(false)
        return
      }
      setQueueAiFilter('all')
      setQueueMatchedByFilter('all')
      setQueueNeedsReviewOnly(true)
    },
    []
  )

  const matchedByOptions = useMemo(() => {
    const vals = new Set<string>()
    for (const row of [...currentBatch, ...pendingQueue]) {
      const key = String(row.matched_by ?? '').trim().toLowerCase()
      if (key) vals.add(key)
    }
    return ['all', ...Array.from(vals).sort()]
  }, [currentBatch, pendingQueue])

  const filteredCurrentBatch = useMemo(
    () => currentBatch.filter(matchesQueueFilters),
    [currentBatch, matchesQueueFilters]
  )

  const filteredPendingQueue = useMemo(
    () => pendingQueue.filter(matchesQueueFilters),
    [pendingQueue, matchesQueueFilters]
  )

  const queueQuickCounts = useMemo(() => {
    const counts = {
      all: 0,
      ai: 0,
      rules: 0,
      fallback: 0,
      review: 0
    }
    const rows = [...currentBatch, ...pendingQueue]
    counts.all = rows.length
    for (const row of rows) {
      const matchedBy = String(row.matched_by ?? '').trim().toLowerCase()
      const aiUsedRaw = String(row.ai_used ?? '').trim().toLowerCase()
      const reviewRequiredRaw = String(row.review_required ?? '').trim().toLowerCase()
      const aiUsed = aiUsedRaw === '1' || aiUsedRaw === 'true' || matchedBy === 'ollama'
      const reviewRequired = reviewRequiredRaw === '1' || reviewRequiredRaw === 'true'
      if (aiUsed) counts.ai += 1
      else counts.rules += 1
      if (matchedBy === 'fallback') counts.fallback += 1
      if (reviewRequired) counts.review += 1
    }
    return counts
  }, [currentBatch, pendingQueue])

  const renderTable = (rows: Record<string, unknown>[], opts?: { scrollBody?: boolean; emptyMessage?: string }) => {
    const tableInner = (
      <table className="w-full text-sm">
        <thead className="bg-[var(--kiwi-blue-pale)] text-left text-[0.65rem] font-bold uppercase tracking-[0.06em] text-[var(--kiwi-text-3)]">
          <tr className="h-8">
            {tableColumns.map((column) => (
              <th key={column} className="px-3">
                <button type="button" className="hover:text-[var(--kiwi-text)]" onClick={() => sortBy(column)}>
                  {column.replace(/_/g, ' ')}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortRows(rows).map((row, idx) => (
            <tr
              key={`${String(row.file_id ?? idx)}-${idx}`}
              className={`h-8 border-b border-[var(--kiwi-border)] ${idx % 2 === 0 ? 'bg-white' : 'bg-[var(--kiwi-blue-pale)]'}`}
            >
              {tableColumns.map((column) => (
                <td key={column} className="px-3 text-[0.8rem] text-[var(--kiwi-text-2)]">
                  {column === 'status' ? (
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getStatusBadgeClass(row[column])}`}>
                      {String(row[column] ?? '-')}
                    </span>
                  ) : (
                    String(row[column] ?? '-')
                  )}
                </td>
              ))}
            </tr>
          ))}
          {!rows.length ? (
            <tr>
              <td className="px-3 py-6 text-center text-xs text-[var(--kiwi-text-3)]" colSpan={tableColumns.length}>
                {queueLoading ? 'Loading queue...' : (opts?.emptyMessage ?? '📂 No files to display')}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    )

    if (opts?.scrollBody) {
      return (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[var(--kiwi-radius)] bg-white">
          <div className="min-h-0 flex-1 overflow-auto">{tableInner}</div>
        </div>
      )
    }

    return (
      <div className="overflow-hidden rounded-[var(--kiwi-radius)] bg-white">
        {tableInner}
      </div>
    )
  }

  useEffect(() => {
    if (typeof window === 'undefined') return
    const detectedUsername = navigator.userAgent.includes('Windows')
      ? (localStorage.getItem('kiwi_username') ?? 'YourName')
      : 'YourName'
    const defaultImport = `C:\\Users\\${detectedUsername}\\Documents\\KIWI\\import`
    const defaultExport = `C:\\Users\\${detectedUsername}\\Documents\\KIWI\\export`
    const storedImport = localStorage.getItem('kiwi_import_base') ?? defaultImport
    const storedExport = localStorage.getItem('kiwi_export_base') ?? defaultExport
    const storedQuickAi = localStorage.getItem('kiwi_quick_ai') ?? 'none'
    if (!localStorage.getItem('kiwi_import_base')) localStorage.setItem('kiwi_import_base', storedImport)
    if (!localStorage.getItem('kiwi_export_base')) localStorage.setItem('kiwi_export_base', storedExport)
    setImportBase(storedImport)
    setExportBase(storedExport)
    setForm((prev) => ({
      ...prev,
      outputFolderPath: prev.outputFolderPath || storedExport
    }))
    setQuickAiProvider(storedQuickAi)
    setShowPathTip(localStorage.getItem('kiwi_path_tip_dismissed') !== '1')
    setShowQuickSettings(!localStorage.getItem('kiwi_import_base'))
    const savedDraft = localStorage.getItem(FORM_DRAFT_KEY)
    if (savedDraft) {
      try {
        const parsed = JSON.parse(savedDraft) as Partial<typeof form>
        setForm((prev) => ({ ...prev, ...parsed }))
      } catch {
        // ignore malformed draft data
      }
    }
    draftHydratedRef.current = true
    quickAiHydratedRef.current = true
  }, [])

  useEffect(() => {
    const hasSession = !!localStorage.getItem('kiwi_session')
    setProjectSaved(hasSession)
    setProjectState(hasSession ? 'saved' : 'unsaved')
    manualProjectEditRef.current = false
  }, [])

  useEffect(() => {
    if (projectState === 'unsaved') return
    const syncedSignature = localStorage.getItem(PROJECT_SYNC_KEY)
    if (!syncedSignature) return
    if (syncedSignature === currentProjectSignature) {
      if (projectState === 'editing' && !manualProjectEditRef.current) setProjectState('saved')
      return
    }
    if (projectState === 'saved') setProjectState('editing')
  }, [projectState, currentProjectSignature])

  useEffect(() => {
    if (projectState !== 'saved') return
    if (hasScannedBatch && batchState !== 'running' && batchState !== 'complete' && batchState !== 'scanned') {
      setBatchState('scanned')
      return
    }
    if (!importPath) {
      if (batchState !== 'running' && batchState !== 'complete') {
        setBatchState('empty')
      }
      return
    }
    if (batchState === 'empty' || batchState === 'failed') {
      setBatchState('ready_to_scan')
    }
  }, [importPath, projectState, batchState, hasScannedBatch])

  useEffect(() => {
    if (!draftHydratedRef.current) return
    if (skipFirstDraftPersistRef.current) {
      skipFirstDraftPersistRef.current = false
      return
    }
    localStorage.setItem(FORM_DRAFT_KEY, JSON.stringify(form))
  }, [form])

  useEffect(() => {
    if (!quickAiHydratedRef.current) return
    localStorage.setItem('kiwi_quick_ai', quickAiProvider)
  }, [quickAiProvider])

  useEffect(() => {
    if (typeof window === 'undefined') return
    setRunSettingsReview(buildRunSettingsReview(form.exportProfile))
  }, [form.exportProfile, activeProfile, quickAiProvider])

  useEffect(() => {
    localStorage.setItem(
      'kiwi_draft',
      JSON.stringify({
        name: form.name,
        sourceFolderName: form.sourceFolderName,
        outputFolderName: form.outputFolderName,
        exportProfile: form.exportProfile
      })
    )
  }, [form])

  useEffect(() => {
    const raw = localStorage.getItem('kiwi_draft')
    if (!raw) return
    try {
      const draft = JSON.parse(raw)
      setForm((prev) => ({
        ...prev,
        name: draft.name || prev.name,
        sourceFolderName: draft.sourceFolderName || prev.sourceFolderName,
        outputFolderName: draft.outputFolderName || prev.outputFolderName,
        exportProfile: draft.exportProfile || prev.exportProfile
      }))
    } catch {
      // ignore malformed draft cache
    }
  }, [])

  useEffect(() => {
    setSessionToken(getToken())
    void loadQueue({ surfaceError: false })
    void checkBackendHealth({ surfaceError: false })
  }, [loadQueue, checkBackendHealth])

  useEffect(() => {
    const token = getToken()
    if (!token) return
    const id = window.setInterval(() => {
      void loadQueue({ surfaceError: false })
    }, 5000)
    return () => window.clearInterval(id)
  }, [loadQueue, sessionToken])

  useEffect(() => {
    if (!running) return
    const interval = window.setInterval(() => {
      void loadQueue({ surfaceError: false })
    }, 8000)
    return () => window.clearInterval(interval)
  }, [running, loadQueue])

  useEffect(() => {
    const interval = window.setInterval(() => {
      void checkBackendHealth({ surfaceError: false })
    }, 10000)
    return () => window.clearInterval(interval)
  }, [checkBackendHealth])

  useEffect(() => {
    const shouldRun = searchParams.get('run') === '1' || localStorage.getItem('kiwi_trigger_run_queue') === '1'
    if (!shouldRun || running) return
    localStorage.removeItem('kiwi_trigger_run_queue')
    void handleRunQueue()
  }, [searchParams])

  useEffect(() => {
    const warnMessage = 'You have unsaved project changes. Leave this page without saving?'

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedProjectChanges) return
      event.preventDefault()
      event.returnValue = ''
    }

    const onDocumentClick = (event: MouseEvent) => {
      if (!hasUnsavedProjectChanges) return
      if (event.defaultPrevented) return
      if (event.button !== 0) return
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return

      const target = event.target as HTMLElement | null
      const anchor = target?.closest('a[href]') as HTMLAnchorElement | null
      if (!anchor) return

      const href = anchor.getAttribute('href')
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return

      const current = new URL(window.location.href)
      const destination = new URL(anchor.href, current.href)
      if (destination.href === current.href) return

      const shouldLeave = window.confirm(warnMessage)
      if (!shouldLeave) {
        event.preventDefault()
        event.stopPropagation()
      }
    }

    window.addEventListener('beforeunload', onBeforeUnload)
    document.addEventListener('click', onDocumentClick, true)
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload)
      document.removeEventListener('click', onDocumentClick, true)
    }
  }, [hasUnsavedProjectChanges])

  const projectFieldsLocked = projectState === 'saved'
  const showScanAction = canScanBatch && (batchState === 'empty' || batchState === 'ready_to_scan' || batchState === 'failed')
  const step2Disabled = projectState !== 'saved'
  const step3Disabled = !scanSucceeded
  const isProjectPrimary = projectState !== 'saved'
  const isScanPrimary = projectState === 'saved' && showScanAction
  const isRunPrimary = canRunBatch
  const isNextBatchPrimary = canStartNextBatch
  const sidebarStep =
    !projectSaved
      ? 1
      : !hasScannedBatch
        ? 2
        : runCompleted
            ? 5
            : running
              ? 4
              : 3

  return (
    <div className="min-h-[calc(100vh-48px)] bg-[#f3f4f6] px-0 py-0">
      <div className="flex min-h-[calc(100vh-48px)]">
      <aside className="hidden lg:flex w-64 min-w-[256px] border-r border-[#dde1f0] bg-white px-4 py-5 flex-col gap-4 sticky top-[48px] h-[calc(100vh-48px)] overflow-y-auto">
        <Link
          href="/batch-prep"
          className="group flex items-start gap-2.5 rounded-lg border border-[#c7ddff] bg-[#eef4ff] px-3 py-2.5 text-xs text-[#1f3f8f] transition-colors hover:bg-[#e6f0ff]"
        >
          <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white text-[#2f58d6] shadow-sm">
            <FolderOpen className="h-3.5 w-3.5" />
          </span>
          <div className="leading-relaxed">
            <strong className="block text-[13px] text-[#17337f]">Need to organize lots of files first?</strong>
            <span className="text-[12px] text-[#2a4c9e]">
              Open Batch Prep to group folders before running setup.
            </span>
          </div>
        </Link>

        <p className="text-[0.6rem] font-bold uppercase tracking-widest text-[#9ca3af] px-1 mt-2">Workflow Guide</p>

        <div>
          <SidebarStep
            number={1}
            title="Project Setup"
            text="Enter Project Name, paste your full Export path, and choose Export Profile. Click Save Project. Do this once — settings persist across batches."
            active={sidebarStep === 1}
            complete={projectSaved}
          />
          <SidebarStep
            number={2}
            title="Scan a Batch"
            text="Paste your Import base path, enter the next batch folder name (e.g. batch_001), then click Scan This Batch."
            active={sidebarStep === 2}
            complete={hasScannedBatch}
          />
          <SidebarStep
            number={3}
            title="Check Settings (optional)"
            text="Review AI Provider, Workspaces, and Keywords in Settings before your first run."
            link="/settings"
            linkLabel="Open Settings →"
            active={sidebarStep === 3}
            complete={hasScannedBatch}
          />
          <SidebarStep
            number={4}
            title="Run the Batch"
            text="Click Run Queue in the right panel. Check Triage first for any unassigned files that need manual review."
            link="/triage"
            linkLabel="Open Triage →"
            active={sidebarStep === 4}
            complete={runCompleted}
          />
          <SidebarStep
            number={5}
            title="Next Batch"
            text="Click Start Next Batch when done. Only the batch folder clears. Enter batch_002 and repeat from Step 2."
            active={sidebarStep === 5}
            complete={nextBatchPrepared}
          />
        </div>

        <a href="/help" className="mt-auto flex items-center gap-1.5 text-xs text-[#3b5bdb] hover:underline px-1 pt-4 border-t border-[#dde1f0]">
          📖 Full documentation in Help
        </a>
      </aside>

      <div className="flex-1 grid grid-cols-12 gap-3 p-3 md:p-4">
      <ProjectSummaryBar
        projectName={projectName}
        projectState={projectState}
        exportProfile={form.exportProfile}
        exportFolder={resolvedOutputPath}
        backendHealthy={backendHealthy}
        currentBatchName={currentBatchName || lastScannedBatchName}
      />
      <div className="col-span-12">
        <RefreshTipBanner />
      </div>
      <div className="col-span-12 space-y-4 lg:col-span-5">
        {showPathTip ? (
          <PathTipBanner
            onDismiss={() => {
              localStorage.setItem('kiwi_path_tip_dismissed', '1')
              setShowPathTip(false)
            }}
          />
        ) : null}

        <div className={`${cardClass} p-4`}>
          <div className="mb-2 flex items-center gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--kiwi-radius-sm)] bg-[var(--kiwi-blue)] text-xs font-bold text-white">
              1
            </span>
            <h2 className="text-[16px] font-semibold leading-snug text-[#151726]">Project Setup</h2>
            <HelpIcon title="Your project keeps the same export location, profile, AI settings, and workspace rules across multiple batches." />
            <div className="ml-auto flex items-center gap-2">
              <SupportedFileTypesButton />
            </div>
          </div>
          <p className="mb-3 text-[12px] leading-relaxed text-[var(--kiwi-text-3)]">
            Set this once at the beginning by pasting your full Export path. You can reuse these project settings for every batch.
          </p>

          {projectState === 'saved' ? (
            <div className="space-y-2">
              <div className="rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-[var(--kiwi-blue-pale)] px-3 py-2 text-sm leading-relaxed">
                <p className="text-[14px] font-medium text-[#1f2333]">
                  <span className="font-semibold">Project:</span> {projectName || 'Not configured'}
                </p>
                <p className="mt-1 text-[14px] font-medium text-[#1f2333]">
                  <span className="font-semibold">Export Folder:</span> {resolvedOutputPath || 'Not configured'}
                </p>
                <p className="mt-1 text-[14px] font-medium text-[#1f2333]">
                  <span className="font-semibold">Export Profile:</span> {profileLabel[form.exportProfile]}
                </p>
                <p className="mt-2 font-semibold text-[var(--kiwi-green)]">✔ Project saved</p>
              </div>
              <p className="rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-white px-3 py-1.5 text-xs text-[var(--kiwi-text-2)]">
                You only set this once. Now process batches below.
              </p>
              <Button
                variant="secondary"
                type="button"
                className={secondaryButtonClass}
                onClick={() => {
                  manualProjectEditRef.current = true
                  setProjectState('editing')
                }}
              >
                Edit Project Settings
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className={`mb-1 flex items-center gap-1.5 ${labelClass}`}>
                  Project Name
                  <HelpIcon title="A name to remember this project (e.g. MyCareerFiles, Q3Archive)." />
                </label>
                <Input
                  className={inputClass}
                  placeholder="e.g. MyCareerFiles, Q3Archive"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  readOnly={projectFieldsLocked}
                />
              </div>

              <div className="space-y-1">
                <label className={`flex items-center gap-1.5 ${labelClass}`}>
                  Export path (paste full path)
                  <HelpIcon title="This is where KIWI saves the organized output. Keep this the same for all batches in one project." />
                </label>
                <Input
                  placeholder="C:\\Users\\YourName\\Documents\\KIWI\\export\\my_export"
                  value={form.outputFolderPath}
                  onChange={(e) => {
                    const value = e.target.value
                    setForm({ ...form, outputFolderPath: value })
                    setExportBase(value)
                    localStorage.setItem('kiwi_export_base', value)
                  }}
                  className={`${inputClass} font-mono`}
                  readOnly={projectFieldsLocked}
                />
                {resolvedOutputPath ? (
                  <p className="font-mono text-xs text-[var(--kiwi-text-2)]">
                    → {resolvedOutputPath}
                  </p>
                ) : null}
                <p className={`text-xs text-[var(--kiwi-text-3)]`}>
                  Organized exports will be saved here under anythingllm/ or open_webui/ subfolders.
                </p>
              </div>

              <div>
                <label className={`mb-1 flex items-center gap-1.5 ${labelClass}`}>
                  Export profile
                  <HelpIcon title="Choose the format KIWI should prepare for upload into tools like AnythingLLM or Open WebUI." />
                </label>
                <Select
                  className={selectClass}
                  value={form.exportProfile}
                  onChange={(e) => setForm({ ...form, exportProfile: e.target.value as typeof form.exportProfile })}
                  disabled={projectFieldsLocked}
                >
                  <option value="anythingllm">AnythingLLM</option>
                  <option value="open_webui">Open WebUI</option>
                  <option value="both">Both</option>
                </Select>
              </div>

              {statusMessage ? (
                <div className="flex items-center gap-2 text-sm text-[var(--kiwi-text-2)]">
                  {loading ? (
                    <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-[var(--kiwi-border)] border-t-[var(--kiwi-blue)]" />
                  ) : null}
                  <span>{statusMessage}</span>
                </div>
              ) : null}
              {error ? <p className="text-sm text-[var(--kiwi-red)]">{error}</p> : null}
              <hr className="my-2 border-[var(--kiwi-border)]" />
              <Button
                className={isProjectPrimary ? primaryButtonClass : secondaryButtonClass}
                onClick={handleSaveProject}
                disabled={loading || !canSaveProject}
              >
                {loading && statusMessage === 'Saving project...'
                  ? 'Saving project...'
                  : hasUnsavedProjectChanges
                    ? 'Update Project'
                    : 'Save Project'}
              </Button>
            </div>
          )}
        </div>

        <div
          className={`${cardClass} p-4 transition-colors ${
            step2Disabled
              ? 'border-l-4 border-l-[var(--kiwi-text-3)] bg-[var(--kiwi-blue-pale)]/40 opacity-80'
              : `border-l-4 ${projectState === 'saved' ? 'border-l-[var(--kiwi-green)] bg-[var(--kiwi-green-light)]/30' : 'border-l-[var(--kiwi-blue)]'}`
          }`}
        >
          <div className="mb-2 flex items-center gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--kiwi-radius-sm)] bg-[var(--kiwi-blue)] text-xs font-bold text-white">
              2
            </span>
            <h2 className="text-[16px] font-semibold leading-snug text-[#151726]">Current Batch</h2>
            <HelpIcon title="This is the only folder you change when moving from batch_001 to batch_002." />
          </div>
          <p className="mb-3 text-[12px] leading-relaxed text-[var(--kiwi-text-3)]">
            Paste your Import base path and enter the next batch folder name each run.
          </p>
          {step2Disabled ? (
            <p className="mb-2 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-white px-3 py-2 text-xs text-[var(--kiwi-text-2)]">
              Save your project first to unlock batch scanning.
            </p>
          ) : null}

          <div className="space-y-2.5">
            <div>
              <label className={`mb-1 flex items-center gap-1.5 ${labelClass}`}>
                Import path (paste base path)
                <HelpIcon title="This is the parent folder that contains your batch folders." />
              </label>
              <Input
                placeholder="C:\\Users\\YourName\\Documents\\KIWI\\import"
                value={importBase}
                onChange={(e) => {
                  const value = e.target.value
                  setImportBase(value)
                  localStorage.setItem('kiwi_import_base', value)
                }}
                className={`${inputClass} font-mono`}
                readOnly={projectState !== 'saved'}
              />
            </div>
            <div>
              <label className={`mb-1 flex items-center gap-1.5 ${labelClass}`}>
                Next batch folder name
                <HelpIcon title="Enter only the folder name, such as batch_004, if you are using the saved import path above." />
              </label>
              <Input
                ref={batchFolderInputRef}
                placeholder="batch_001"
                value={form.sourceFolderName}
                onChange={(e) => setForm({ ...form, sourceFolderName: e.target.value })}
                className={`${inputClass} font-mono`}
                readOnly={projectState !== 'saved'}
              />
            </div>
            <p className="rounded bg-[#eef2ff] px-3 py-1.5 text-[12px] leading-relaxed text-[#2d3f99]">
              <span className="font-medium text-[var(--kiwi-text-2)]">Batch to scan:</span>
              <span className="mt-0.5 block font-mono text-[13px] font-medium text-[#1f2333]">{importPath || 'Not configured'}</span>
            </p>
            <p className="rounded bg-[#f8f9fc] px-3 py-1.5 font-mono text-[11px] leading-relaxed text-[var(--kiwi-text-2)]">
              Debug - last scan: {lastScanTargetPath || 'No scan yet'}
            </p>
            {showScanAction ? (
              <Button
                className={isScanPrimary ? primaryButtonClass : successButtonClass}
                onClick={handleScanBatch}
                disabled={loading}
              >
                {loading && statusMessage.startsWith('Scanning files from:') ? 'Scanning...' : 'Scan Batch'}
              </Button>
            ) : null}
            {scanSucceeded ? (
              <p className="text-xs text-[var(--kiwi-green)]">
                ✓ Found {lastScannedFileCount} files in {lastScannedBatchName || currentBatchName || 'current batch'}. Continue to Step 3.
              </p>
            ) : null}
          </div>
        </div>

        <div className={`${cardClass} p-4 overflow-hidden`}>
          <button
            type="button"
            onClick={() => setLeftReviewSettingsOpen((prev) => !prev)}
            className="flex w-full items-center justify-between text-left transition-colors hover:bg-[var(--kiwi-blue-pale)] p-0"
          >
            <span className="flex items-center gap-1.5 text-sm font-semibold text-[var(--kiwi-text)]">
              Review AI & Classification Settings
              <HelpIcon title="Confirm AI, model, workspace, and export settings before processing files." />
            </span>
            {leftReviewSettingsOpen ? (
              <ChevronDown className="h-4 w-4 text-[var(--kiwi-text-2)]" />
            ) : (
              <ChevronRight className="h-4 w-4 text-[var(--kiwi-text-2)]" />
            )}
          </button>
          {leftReviewSettingsOpen ? (
            <div className="space-y-2.5 border-t border-[var(--kiwi-border)] pt-2.5 mt-2.5">
              <p className="text-xs leading-relaxed text-[var(--kiwi-text-3)]">Check these before your first run. Usually no changes needed between batches.</p>
              <div>
                <p className="text-xs font-semibold text-[var(--kiwi-text-2)] mb-1.5">Current AI Setup</p>
                <div className="space-y-0.5 text-xs text-[var(--kiwi-text)]">
                  <p>Provider: <span className="font-medium">{runSettingsReview.provider}</span></p>
                  <p>Model: <span className="font-medium">{runSettingsReview.model}</span></p>
                  <p>Mode: <span className="font-medium">{runSettingsReview.aiMode}</span></p>
                  <p>Threshold: <span className="font-medium">{runSettingsReview.confidenceThreshold}</span></p>
                </div>
              </div>
              {runSettingsReview.workspaceMappings.length ? (
                <div>
                  <p className="text-xs font-semibold text-[var(--kiwi-text-2)] mb-0.5">Workspaces</p>
                  <p className="text-xs text-[var(--kiwi-text)]">✔ {runSettingsReview.workspaceMappings.length} configured</p>
                </div>
              ) : (
                <p className="text-xs text-[var(--kiwi-text-3)]">No workspace rules configured.</p>
              )}
              {runSettingsReview.keywordMappings.length ? (
                <div>
                  <p className="text-xs font-semibold text-[var(--kiwi-text-2)] mb-0.5">Keywords / Categories</p>
                  <p className="text-xs text-[var(--kiwi-text)]">✔ {runSettingsReview.keywordMappings.length} configured</p>
                </div>
              ) : (
                <p className="text-xs text-[var(--kiwi-text-3)]">No keyword rules configured.</p>
              )}
              <Link
                href="/settings"
                className="inline-flex items-center rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] px-2 py-1 text-xs font-medium text-[var(--kiwi-text-2)] hover:border-[var(--kiwi-blue)] hover:text-[var(--kiwi-blue)]"
              >
                Open Full Settings
              </Link>
            </div>
          ) : (
            <div className="pt-1.5 text-xs text-[var(--kiwi-text-3)]">
              AI: {runSettingsReview.provider} · Model: {runSettingsReview.model} · Mode: {runSettingsReview.aiMode}
            </div>
          )}
        </div>

        <div className="space-y-1 rounded-xl border border-[var(--kiwi-border)] bg-white p-3 shadow-sm text-[12.5px]">
          <Link
            href="/settings"
            className="block p-2 rounded-[var(--kiwi-radius-sm)] text-[var(--kiwi-text-2)] hover:bg-[var(--kiwi-blue-pale)] hover:text-[var(--kiwi-blue)]"
          >
            Advanced Setup
          </Link>
          <button
            type="button"
            onClick={() => setLoadExistingOpen((o) => !o)}
            className="block w-full text-left p-2 rounded-[var(--kiwi-radius-sm)] text-[var(--kiwi-text-2)] hover:bg-[var(--kiwi-blue-pale)] hover:text-[var(--kiwi-blue)]"
          >
            Load Existing Project
          </button>
          <button
            type="button"
            onClick={handleResetLocalSetupData}
            className="block w-full text-left p-2 rounded-[var(--kiwi-radius-sm)] text-[var(--kiwi-text-2)] hover:bg-[var(--kiwi-red-light)] hover:text-[var(--kiwi-red)]"
          >
            Clear Saved Data
          </button>
        </div>

        {loadExistingOpen ? (
          <ExistingProjectPanel
            loadExistingOpen={loadExistingOpen}
            existingPath={existingPath}
            loading={loading}
            onToggle={() => setLoadExistingOpen((o) => !o)}
            onPathChange={setExistingPath}
            onPastePath={async () => {
              try {
                const text = await navigator.clipboard.readText()
                if (text && (text.includes('\\') || text.includes('/'))) {
                  setExistingPath(text.trim())
                  setError('')
                }
              } catch {
                // clipboard not available
              }
            }}
            onClearPath={() => {
              setExistingPath('')
              setError('')
            }}
            onReload={handleReload}
          />
        ) : null}

      </div>

      <div className="col-span-12 flex min-h-0 flex-col gap-3 lg:col-span-7">
        <div
          className={`shrink-0 p-4 ${cardClass} transition-colors ${
            step3Disabled
              ? 'border-l-4 border-l-[var(--kiwi-text-3)] bg-[var(--kiwi-blue-pale)]/40 opacity-80'
              : 'border-l-4 border-l-[var(--kiwi-green)]'
          }`}
        >
          <div className="mb-2 flex items-center gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--kiwi-radius-sm)] bg-[var(--kiwi-blue)] text-xs font-bold text-white">
              3
            </span>
            <h3 className="text-[16px] font-semibold leading-snug text-[#151726]">Run Batch</h3>
            <HelpIcon title="Run Batch processes the scanned files using your current settings." />
          </div>
          <p className="mb-2 text-[12px] leading-relaxed text-[var(--kiwi-text-3)]">Process the files you just scanned in Step 2.</p>
          {!hasActiveProject ? (
            <p className="mb-2 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-white px-3 py-1.5 text-xs text-[var(--kiwi-text-2)]">
              Save your project first.
            </p>
          ) : !scanSucceeded ? (
            <p className="mb-2 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-white px-3 py-1.5 text-xs text-[var(--kiwi-text-2)]">
              Scan a batch first, then Run Batch will be enabled here.
            </p>
          ) : null}
          <div className="mb-2 rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] bg-white">
            <button
              type="button"
              onClick={() => setReviewSettingsOpen((prev) => !prev)}
              className={`${secondaryButtonClass} !flex w-full items-center justify-between !rounded-[var(--kiwi-radius-sm)] !border-0 !px-3 !py-2 !text-[12px] !font-semibold !text-[#1f2333]`}
            >
              <span className="flex items-center gap-1.5">
                Review settings before running
                <HelpIcon title="Confirm AI, model, workspace, and export settings before processing files." />
              </span>
              <span>{reviewSettingsOpen ? '▲' : '▼'}</span>
            </button>
            <div className="border-t border-[var(--kiwi-border)] px-3 py-2">
              <p className="text-[13px] font-medium leading-relaxed text-[#1f2333]">
                ✔ AI: <span className="font-semibold">{runSettingsReview.provider}</span> · Model:{' '}
                <span className="font-semibold">{runSettingsReview.model}</span> · Mode:{' '}
                <span className="font-semibold">{runSettingsReview.aiMode}</span> · Export:{' '}
                <span className="font-semibold">{profileLabel[runSettingsReview.exportProfile]}</span>
              </p>
            </div>
            {reviewSettingsOpen ? (
              <div className="space-y-3 border-t border-[var(--kiwi-border)] px-3 py-3 leading-relaxed">
                <div>
                  <p className="text-[15px] font-semibold text-[#151726]">Current AI Setup</p>
                  <div className="mt-2 grid grid-cols-[minmax(120px,150px)_1fr] gap-x-3 gap-y-1.5">
                    <p className="text-[12px] font-medium text-[var(--kiwi-text-2)]">AI provider</p>
                    <p className="text-[13px] font-semibold text-[#1f2333]">
                      {runSettingsReview.provider === 'Not configured' ? 'Not configured' : `✔ ${runSettingsReview.provider}`}
                    </p>
                    <p className="text-[12px] font-medium text-[var(--kiwi-text-2)]">AI model</p>
                    <p className="text-[13px] font-semibold text-[#1f2333]">
                      {runSettingsReview.model === 'Not configured' ? 'Not configured' : `✔ ${runSettingsReview.model}`}
                    </p>
                    <p className="text-[12px] font-medium text-[var(--kiwi-text-2)]">Classification mode</p>
                    <p className="text-[13px] font-semibold text-[#1f2333]">
                      {runSettingsReview.aiMode ? `✔ ${runSettingsReview.aiMode}` : 'Not configured'}
                    </p>
                    <p className="text-[12px] font-medium text-[var(--kiwi-text-2)]">Confidence threshold</p>
                    <p className="text-[13px] font-semibold text-[#1f2333]">
                      {runSettingsReview.confidenceThreshold ? `✔ ${runSettingsReview.confidenceThreshold}` : 'Not configured'}
                    </p>
                    <p className="text-[12px] font-medium text-[var(--kiwi-text-2)]">Auto-assign workspace</p>
                    <p className="text-[13px] font-semibold text-[#1f2333]">{runSettingsReview.autoAssignWorkspace}</p>
                  </div>
                </div>
                <div>
                  <p className="text-[15px] font-semibold text-[#151726]">Workspaces / Keywords</p>
                  {runSettingsReview.workspaceMappings.length || runSettingsReview.keywordMappings.length ? (
                    <div className="mt-2 space-y-2">
                      {runSettingsReview.workspaceMappings.length ? (
                        <div>
                          <p className="text-[12px] font-medium text-[var(--kiwi-text-2)]">Workspace mappings</p>
                          <p className="mt-0.5 text-[13px] font-medium text-[#1f2333]">✔ {runSettingsReview.workspaceMappings.join(' · ')}</p>
                        </div>
                      ) : null}
                      {runSettingsReview.keywordMappings.length ? (
                        <div>
                          <p className="text-[12px] font-medium text-[var(--kiwi-text-2)]">Keyword/category mappings</p>
                          <p className="mt-0.5 text-[13px] font-medium text-[#1f2333]">✔ {runSettingsReview.keywordMappings.join(' · ')}</p>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="mt-2 space-y-1">
                      <p className="text-[13px] font-medium text-[#1f2333]">Workspaces: Not configured</p>
                      <p className="text-[12px] text-[var(--kiwi-text-3)]">No custom workspace or keyword rules found.</p>
                    </div>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Link
                    href="/settings"
                    className="inline-flex items-center rounded-[var(--kiwi-radius-sm)] border border-[var(--kiwi-border)] px-2 py-1 text-xs font-medium text-[var(--kiwi-text-2)] hover:border-[var(--kiwi-blue)] hover:text-[var(--kiwi-blue)]"
                  >
                    Open Advanced Settings
                  </Link>
                  <p className="text-[11px] leading-relaxed text-[var(--kiwi-text-3)]">
                    Review these settings before running a batch. To change AI, model, workspaces, or keywords, open Advanced Settings.
                  </p>
                </div>
              </div>
            ) : null}
          </div>
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            {canRunBatch ? (
              <Button
                className={`${isRunPrimary ? primaryButtonClass : successButtonClass} w-auto min-w-[140px]`}
                onClick={handleRunQueue}
                disabled={running}
              >
                {runQueueRunning ? `Processing...` : 'Run Batch'}
              </Button>
            ) : canStartNextBatch ? (
              <Button
                className={`${isNextBatchPrimary ? primaryButtonClass : successButtonClass} w-auto min-w-[160px]`}
                onClick={handleStartNextBatch}
              >
                Start Next Batch
              </Button>
            ) : null}
            <Button
              variant="secondary"
              className={secondaryButtonClass}
              onClick={() => void loadQueue({ surfaceError: true })}
              disabled={queueLoading}
            >
              ⟳ Refresh
            </Button>
            <Button
              variant="secondary"
              className={secondaryButtonClass}
              onClick={handleClearQueue}
              disabled={clearing || running || queueLoading}
            >
              {clearing ? 'Clearing...' : '✕ Clear'}
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-semibold ${
                backendHealthy === true
                  ? 'bg-[var(--kiwi-green-light)] text-[var(--kiwi-green)]'
                  : backendHealthy === false
                    ? 'bg-[var(--kiwi-red-light)] text-[var(--kiwi-red)]'
                    : 'bg-[var(--kiwi-blue-light)] text-[var(--kiwi-blue)]'
              }`}
              title="Backend Online means the local KIWI service is running and ready."
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  backendHealthy === true
                    ? 'bg-[var(--kiwi-green)] animate-pulse'
                    : backendHealthy === false
                      ? 'bg-[var(--kiwi-red)] animate-pulse'
                      : 'bg-[var(--kiwi-blue)]'
                }`}
              />
              Backend: {backendHealthy === true ? 'Online' : backendHealthy === false ? 'Offline' : 'Checking'}
            </span>
            <span className="inline-flex rounded-full bg-[var(--kiwi-blue-light)] px-3 py-1 text-[13px] font-semibold text-[var(--kiwi-blue)]">
              Profile: {profileLabel[activeProfile]}
            </span>
            <span className="text-[13px] font-medium leading-relaxed text-[#1f2333]">{backendMessage}</span>
            <Button
              variant="secondary"
              type="button"
              className={`${secondaryButtonClass} shrink-0`}
              onClick={() => void checkBackendHealth({ surfaceError: true })}
              disabled={backendChecking}
            >
              {backendChecking ? 'Checking...' : 'Retry'}
            </Button>
          </div>
          {!sessionToken ? (
            <p className="mt-2 rounded-[var(--kiwi-radius-sm)] bg-[var(--kiwi-red-light)] px-3 py-1.5 text-xs text-[var(--kiwi-red)]">
              No active project yet. Save your project on the left to begin.
            </p>
          ) : null}
          {queueError ? <p className="mt-2 text-xs text-[var(--kiwi-red)]">{queueError}</p> : null}
          {runMessage ? <p className="mt-2 text-xs text-[var(--kiwi-green)]">{runMessage}</p> : null}
        </div>

          <div className="flex min-h-0 flex-1 flex-col gap-2">
          <h4 className="pb-1.5 text-[13px] font-semibold text-[#151726] border-b border-[var(--kiwi-border)] flex items-center gap-1.5">
            Current Batch Queue
            <HelpIcon title="These are the files KIWI found in the batch you scanned." />
          </h4>
          <div className="mb-1 flex flex-wrap items-center gap-1.5">
            <Select className={`max-w-[150px] ${selectClass}`} value={queueAiFilter} onChange={(e) => setQueueAiFilter(e.target.value as 'all' | 'ai' | 'rules')}>
              <option value="all">AI Used: All</option>
              <option value="ai">AI Used: Yes</option>
              <option value="rules">AI Used: No</option>
            </Select>
            <Select className={`max-w-[170px] ${selectClass}`} value={queueMatchedByFilter} onChange={(e) => setQueueMatchedByFilter(e.target.value)}>
              {matchedByOptions.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'Matched By: All' : `Matched By: ${option}`}
                </option>
              ))}
            </Select>
          </div>
          <div className="mb-1 flex flex-wrap items-center gap-1">
            {[
              { key: 'all', label: 'All' },
              { key: 'ai', label: 'AI Only', help: 'Filter files based on whether AI was used during classification.' },
              { key: 'rules', label: 'Rules Only' },
              { key: 'fallback', label: 'Fallback Only', help: 'Filter files by how KIWI matched or categorized them.' },
              { key: 'review', label: 'Needs Review' }
            ].map((chip) => {
              const active =
                (chip.key === 'all' && queueAiFilter === 'all' && queueMatchedByFilter === 'all' && !queueNeedsReviewOnly) ||
                (chip.key === 'ai' && queueAiFilter === 'ai' && queueMatchedByFilter === 'all' && !queueNeedsReviewOnly) ||
                (chip.key === 'rules' && queueAiFilter === 'rules' && queueMatchedByFilter === 'all' && !queueNeedsReviewOnly) ||
                (chip.key === 'fallback' && queueAiFilter === 'all' && queueMatchedByFilter === 'fallback' && !queueNeedsReviewOnly) ||
                (chip.key === 'review' && queueAiFilter === 'all' && queueMatchedByFilter === 'all' && queueNeedsReviewOnly)
              return (
                <button
                  key={chip.key}
                  type="button"
                  onClick={() => applyQueueQuickFilter(chip.key as 'all' | 'ai' | 'rules' | 'fallback' | 'review')}
                  title={chip.help}
                  className={`rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors ${
                    active
                      ? 'border-[var(--kiwi-blue)] bg-[var(--kiwi-blue-light)] text-[var(--kiwi-blue)]'
                      : 'border-[var(--kiwi-border)] bg-white text-[var(--kiwi-text-2)] hover:border-[var(--kiwi-blue)] hover:text-[var(--kiwi-blue)]'
                  }`}
                >
                  {chip.label} ({queueQuickCounts[chip.key as keyof typeof queueQuickCounts]})
                </button>
              )
            })}
          </div>
          <p className="text-[11px] text-[var(--kiwi-text-3)] mb-1">Files: {filteredCurrentBatch.length} of {currentBatch.length}</p>
          <div className="rounded-[var(--kiwi-radius)] border border-[var(--kiwi-border)] border-l-4 border-l-[var(--kiwi-green)] bg-white">
            {renderTable(filteredCurrentBatch, {
              scrollBody: true,
              emptyMessage: 'No files scanned yet. Scan a batch to populate this queue.'
            })}
          </div>
        </div>

        {activeProfile === 'both' && pendingQueue.length > 0 ? (
        <div className="shrink-0 space-y-1.5">
          <button
            type="button"
            className="w-full text-left pb-1.5 text-[13px] font-semibold text-[#151726] border-b border-[var(--kiwi-border)]"
            onClick={() => setPendingOpen((prev) => !prev)}
          >
            Pending Queue ({filteredPendingQueue.length}/{pendingQueue.length}) {pendingOpen ? '▲' : '▼'}
          </button>
          {pendingOpen ? (
            <>
              <Button
                className={`${pendingQueue.length > 0 ? successButtonClass : secondaryButtonClass} w-auto`}
                onClick={handleRunPendingQueue}
                disabled={running || queueLoading || !sessionToken}
              >
                {pendingQueueRunning ? 'Processing...' : 'Process Queue'}
              </Button>
              <div className="rounded-[var(--kiwi-radius)] border border-[var(--kiwi-border)] bg-white">
                {renderTable(filteredPendingQueue)}
              </div>
            </>
          ) : null}
        </div>
        ) : null}
      </div>
      </div>
    </div>
    </div>
  )
}
