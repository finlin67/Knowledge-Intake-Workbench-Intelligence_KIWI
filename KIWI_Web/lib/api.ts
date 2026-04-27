const BASE_URL = process.env.NEXT_PUBLIC_KIWI_API_BASE ?? 'http://localhost:8000'
const API_BASE_STORAGE_KEY = 'kiwi_api_base'
const API_REQUEST_TIMEOUT_MS = 15000
const API_BASE_CANDIDATES = [
  BASE_URL,
  'http://127.0.0.1:8000',
  'http://127.0.0.1:8010',
  'http://127.0.0.1:8100',
  'http://127.0.0.1:8200',
  'http://127.0.0.1:8300',
  'http://localhost:8000',
  'http://localhost:8010',
  'http://localhost:8100',
  'http://localhost:8200',
  'http://localhost:8300'
]
let activeBaseUrl: string | null = null
function sanitizeBaseUrl(value: string): string {
  return value.trim().replace(/\s+/g, '').replace(/\/+$/, '')
}

const SESSION_KEY = 'kiwi_session'

export interface ProjectContextResponse {
  session_token: string
  name: string
  raw_folder: string
  output_folder: string
  db_path: string
}

interface WrappedProjectContextResponse {
  session_token: string
  project_context: Omit<ProjectContextResponse, 'session_token'>
}

export interface QueueResponse {
  current_batch_queue: Record<string, unknown>[]
  pending_queue: Record<string, unknown>[]
  other_pending_queue?: Record<string, unknown>[]
}

export interface InventoryResponse {
  rows: Record<string, unknown>[]
}

export interface PreflightResponse {
  summary: Record<string, unknown>
}

export interface OllamaModelsResponse {
  ok: boolean
  models: string[]
  message: string
}

export interface CategorySuggestionsResponse {
  workspace_suggestions: { key: string; label: string; evidence_count: number }[]
  company_suggestions: { token: string; workspace_key: string; evidence_count: number }[]
  project_suggestions: { token: string; workspace_key: string; evidence_count: number }[]
  message: string
}

export interface SettingsResponse {
  config: Record<string, unknown>
}

export interface BatchPrepRequest {
  source_folder: string
  output_folder: string
  batch_size: number
  batch_mode: 'fixed' | 'pattern'
  pattern: string
  copy_mode: 'copy' | 'move'
  remove_empty: boolean
  detect_near_empty: boolean
  min_text_chars: number
  create_manifest: boolean
  prepare_for_app: boolean
}

export interface BatchPrepPreviewBatch {
  name: string
  count: number
}

export interface BatchPrepPreviewResponse {
  total_files: number
  usable_files: number
  empty_files: number
  estimated_batches: number
  batches_preview: BatchPrepPreviewBatch[]
  error?: string
}

export interface BatchPrepRunResponse {
  total_files: number
  usable_files: number
  empty_files: number
  batches_created: number
  batch_names: string[]
  manifest_path: string | null
  output_folder: string
  message: string
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(SESSION_KEY)
}

function getSessionToken(): string {
  return getToken() ?? ''
}

function setSessionToken(token: string) {
  if (typeof window === 'undefined') return
  localStorage.setItem(SESSION_KEY, token)
}

function normalizeCandidates(candidates: string[]): string[] {
  return Array.from(new Set(candidates.map((item) => sanitizeBaseUrl(item)).filter(Boolean)))
}

async function fetchWithTimeout(input: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('KIWI API request timed out. Check that the backend is running, then retry.')
    }
    throw err
  } finally {
    window.clearTimeout(timeout)
  }
}

async function isHealthyApiBase(baseUrl: string): Promise<boolean> {
  try {
    const response = await fetchWithTimeout(`${baseUrl}/api/health`, { method: 'GET' }, 1200)
    if (!response.ok) return false
    const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
    if (!contentType.includes('application/json')) return false
    const payload = await response.json().catch(() => ({}))
    return payload?.status === 'ok'
  } catch {
    return false
  }
}

async function resolveApiBaseUrl(forceReprobe = false): Promise<string> {
  if (typeof window === 'undefined') return BASE_URL
  if (!forceReprobe && activeBaseUrl) return activeBaseUrl

  const storedRaw = localStorage.getItem(API_BASE_STORAGE_KEY)
  const stored = storedRaw ? sanitizeBaseUrl(storedRaw) : null
  const candidates = normalizeCandidates([stored ?? '', ...API_BASE_CANDIDATES])
  for (const candidate of candidates) {
    const healthy = await isHealthyApiBase(candidate)
    if (!healthy) continue
    activeBaseUrl = candidate
    localStorage.setItem(API_BASE_STORAGE_KEY, candidate)
    return candidate
  }

  activeBaseUrl = stored || sanitizeBaseUrl(BASE_URL)
  return activeBaseUrl
}

export async function getApiBaseUrl(forceReprobe = false): Promise<string> {
  return resolveApiBaseUrl(forceReprobe)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const shouldRetryRouting = (status: number, contentType: string) =>
    path.startsWith('/api/') && (status === 404 || status === 405 || contentType.includes('text/html'))

  let apiBase = await resolveApiBaseUrl()
  const requestInit: RequestInit = {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {})
    }
  }
  const execute = (base: string) => fetchWithTimeout(`${base}${path}`, requestInit, API_REQUEST_TIMEOUT_MS)

  let res: Response
  try {
    res = await execute(apiBase)
  } catch (initialErr) {
    const reprobedBase = await resolveApiBaseUrl(true)
    if (reprobedBase !== apiBase) {
      apiBase = reprobedBase
      try {
        res = await execute(apiBase)
      } catch {
        throw initialErr
      }
    } else {
      throw initialErr
    }
  }
  let contentType = res.headers.get('content-type')?.toLowerCase() ?? ''

  if (shouldRetryRouting(res.status, contentType)) {
    const reprobedBase = await resolveApiBaseUrl(true)
    if (reprobedBase !== apiBase) {
      apiBase = reprobedBase
      res = await execute(apiBase)
      contentType = res.headers.get('content-type')?.toLowerCase() ?? ''
    }
  }

  const isLikelyHtml = (body: string) => {
    const text = body.trim().toLowerCase()
    return text.startsWith('<!doctype html') || text.startsWith('<html') || text.includes('<body')
  }

  if (!res.ok) {
    let detail = `Request failed: ${res.status}`
    try {
      if (contentType.includes('application/json')) {
        const data = await res.json()
        detail = data?.detail ?? data?.error ?? detail
      } else {
        const body = await res.text()
        if (isLikelyHtml(body)) {
          detail =
            `KIWI API is unreachable at ${apiBase}. ` +
            `A web page responded instead of the FastAPI backend. ` +
            `Start the backend and retry.`
        }
      }
    } catch {
      // Keep default error detail when response isn't json.
    }
    throw new Error(detail)
  }

  if (!contentType.includes('application/json')) {
    const body = await res.text()
    if (isLikelyHtml(body)) {
      throw new Error(
        `KIWI API is unreachable at ${apiBase}. ` +
          `A web page responded instead of the FastAPI backend. ` +
          `Start the backend and retry.`
      )
    }
    throw new Error('Unexpected API response format (expected JSON).')
  }

  return res.json()
}

function normalizeProjectResponse(data: WrappedProjectContextResponse | ProjectContextResponse): ProjectContextResponse {
  if ('project_context' in data) {
    return { session_token: data.session_token, ...data.project_context }
  }
  return data
}

export async function createProject(payload: { name: string; raw_folder: string; output_folder: string }): Promise<ProjectContextResponse> {
  const data = await request<WrappedProjectContextResponse | ProjectContextResponse>('/api/projects/create', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
  const project = normalizeProjectResponse(data)
  setSessionToken(project.session_token)
  return project
}

export async function loadProject(payload: { output_folder: string }): Promise<ProjectContextResponse> {
  const data = await request<WrappedProjectContextResponse | ProjectContextResponse>('/api/projects/load', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
  const project = normalizeProjectResponse(data)
  setSessionToken(project.session_token)
  return project
}

export async function getLastProject(): Promise<ProjectContextResponse | null> {
  const data = await request<WrappedProjectContextResponse | ProjectContextResponse | null>('/api/projects/last')
  if (!data) return null
  const project = normalizeProjectResponse(data)
  setSessionToken(project.session_token)
  return project
}

export async function scanProject(): Promise<{ files_scanned?: number; scanned_count?: number }> {
  const session_token = getSessionToken()
  if (!session_token) throw new Error('Missing session token. Please create or load a project first.')
  return request('/api/scan', {
    method: 'POST',
    body: JSON.stringify({ session_token })
  })
}

export async function getQueue(): Promise<QueueResponse> {
  const session_token = getSessionToken()
  if (!session_token) throw new Error('Missing session token. Please create or load a project first.')
  return request(`/api/queue?session_token=${encodeURIComponent(session_token)}`)
}

export async function getInventory(limit = 5000): Promise<InventoryResponse> {
  const session_token = getSessionToken()
  if (!session_token) throw new Error('Missing session token. Please create or load a project first.')
  return request(`/api/inventory?session_token=${encodeURIComponent(session_token)}&limit=${limit}`)
}

export async function getPreflight(): Promise<PreflightResponse> {
  const session_token = getSessionToken()
  if (!session_token) throw new Error('Missing session token. Please create or load a project first.')
  return request(`/api/monitor/preflight?session_token=${encodeURIComponent(session_token)}`)
}

export async function runExport(export_profile: 'anythingllm' | 'open_webui' | 'both'): Promise<{ results?: Record<string, unknown> }> {
  const session_token = getSessionToken()
  if (!session_token) throw new Error('Missing session token. Please create or load a project first.')
  return request('/api/exports/run', {
    method: 'POST',
    body: JSON.stringify({ session_token, export_profile })
  })
}

export async function fetchOllamaModels(): Promise<OllamaModelsResponse> {
  return request('/api/settings/ollama/models')
}

export async function testOllamaConnection(model: string): Promise<{ ok: boolean; message: string }> {
  return request('/api/settings/ollama/test', {
    method: 'POST',
    body: JSON.stringify({ model })
  })
}

export async function fetchCategorySuggestions(): Promise<CategorySuggestionsResponse> {
  const session_token = getSessionToken()
  if (!session_token) throw new Error('Missing session token. Please create or load a project first.')
  return request(`/api/settings/suggestions?session_token=${encodeURIComponent(session_token)}`)
}

export async function getSettings(): Promise<SettingsResponse> {
  const token = getToken()
  if (!token) throw new Error('No active session.')
  return request(`/api/settings?session_token=${encodeURIComponent(token)}`)
}

export async function saveSettings(config: object): Promise<void> {
  const token = getToken()
  if (!token) throw new Error('No active session. Reload project in Setup.')
  const apiBase = await resolveApiBaseUrl()
  const res = await fetch(`${apiBase}/api/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_token: token, config })
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? 'Settings save failed')
  }
}

export async function updateSettings(config: Record<string, unknown>): Promise<SettingsResponse> {
  const session_token = getSessionToken()
  if (!session_token) throw new Error('No active session. Reload project in Setup.')
  return request('/api/settings', {
    method: 'PUT',
    body: JSON.stringify({ session_token, config })
  })
}

export async function clearQueue(export_profile: 'anythingllm' | 'open_webui' | 'both'): Promise<{ cleared_count: number }> {
  const session_token = getSessionToken()
  if (!session_token) throw new Error('Missing session token. Please create or load a project first.')
  return request('/api/queue/clear', {
    method: 'POST',
    body: JSON.stringify({ session_token, export_profile })
  })
}

export async function previewBatchPrep(payload: BatchPrepRequest): Promise<BatchPrepPreviewResponse> {
  return request('/api/batch-prep/preview', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export async function runBatchPrep(payload: BatchPrepRequest): Promise<BatchPrepRunResponse> {
  return request('/api/batch-prep/run', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export { BASE_URL, SESSION_KEY }
