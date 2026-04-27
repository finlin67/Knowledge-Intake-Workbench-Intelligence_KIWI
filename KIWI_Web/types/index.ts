export interface Project {
  id: number
  name: string
  sourceFolder: string
  outputFolder: string
  exportProfile: 'anythingllm' | 'open_webui' | 'both'
  status: 'idle' | 'scanning' | 'running' | 'paused' | 'complete'
  createdAt: string
  updatedAt: string
}

export interface FileRecord {
  id: number
  projectId: number
  filename: string
  filepath: string
  fileSize: number
  fileExt: string
  nextStage: 'classify' | 'export' | 'skip' | 'review'
  status: 'new' | 'processing' | 'exported' | 'failed' | 'skipped' | 'review'
  workspace: string
  subfolder: string
  matchedBy: 'force_rule' | 'company_map' | 'project_map' | 'pattern' | 'ai' | 'fallback' | 'manual'
  confidence: number
  priority: 'High' | 'Low'
  signals: string
  createdAt: string
  updatedAt: string
}

export interface ClassificationRules {
  WORKSPACES: Record<string, string>
  FORCE_RULES: ForceRule[]
  COMPANY_MAP: Record<string, string>
  PROJECT_MAP: Record<string, string>
  DOC_TYPE_PATTERNS: ForceRule[]
  RULE_CONFIDENCE: Record<string, number>
  enable_ollama: boolean
  ollama_model: string
  ai_mode: string
  confidence_threshold: number
  chunk_target_size: number
}

export interface ForceRule {
  contains: string
  workspace: string
  subfolder: string
  reason: string
}

export interface RunStatus {
  projectId: number
  status: 'idle' | 'running' | 'paused' | 'complete' | 'failed'
  total: number
  processed: number
  exported: number
  failed: number
  currentFile: string
  elapsedSeconds: number
  log: LogEntry[]
}

export interface LogEntry {
  timestamp: string
  status: 'success' | 'failed' | 'skipped'
  workspace: string
  filename: string
}

export interface TriageSummary {
  totalUnassigned: number
  ruleGaps: number
  highPriority: number
  aiSessions: number
  safeToSkip: number
  files: FileRecord[]
}
