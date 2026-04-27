import { ClassificationRules, FileRecord } from '@/types'

type ClassificationResult = {
  workspace: string
  subfolder: string
  matchedBy: FileRecord['matchedBy']
  confidence: number
  priority: 'High' | 'Low'
  signals: string
}

const getPriority = (confidence: number, threshold: number): 'High' | 'Low' =>
  confidence >= threshold ? 'Low' : 'High'

export function classifyFile(filename: string, contentPreview: string, rules: ClassificationRules): ClassificationResult {
  const file = filename.toLowerCase()
  const preview = contentPreview.toLowerCase()
  const threshold = rules.confidence_threshold ?? 0.65

  for (const rule of rules.FORCE_RULES) {
    const token = rule.contains.toLowerCase()
    if (file.includes(token) || preview.includes(token)) {
      const confidence = 0.96
      return {
        workspace: rule.workspace,
        subfolder: rule.subfolder,
        matchedBy: 'force_rule',
        confidence,
        priority: getPriority(confidence, threshold),
        signals: `force:${rule.contains}`
      }
    }
  }

  for (const [key, workspace] of Object.entries(rules.COMPANY_MAP)) {
    if (file.includes(key.toLowerCase())) {
      const confidence = 0.9
      return {
        workspace,
        subfolder: '',
        matchedBy: 'company_map',
        confidence,
        priority: getPriority(confidence, threshold),
        signals: `company:${key}`
      }
    }
  }

  for (const [key, workspace] of Object.entries(rules.PROJECT_MAP)) {
    if (file.includes(key.toLowerCase())) {
      const confidence = 0.85
      return {
        workspace,
        subfolder: '',
        matchedBy: 'project_map',
        confidence,
        priority: getPriority(confidence, threshold),
        signals: `project:${key}`
      }
    }
  }

  for (const rule of rules.DOC_TYPE_PATTERNS) {
    const token = rule.contains.toLowerCase()
    if (file.includes(token) || preview.includes(token)) {
      const confidence = 0.75
      return {
        workspace: rule.workspace,
        subfolder: rule.subfolder,
        matchedBy: 'pattern',
        confidence,
        priority: getPriority(confidence, threshold),
        signals: `pattern:${rule.contains}`
      }
    }
  }

  const confidence = 0.4
  return {
    workspace: 'unassigned',
    subfolder: '',
    matchedBy: 'fallback',
    confidence,
    priority: 'High',
    signals: 'fallback:no_match'
  }
}
