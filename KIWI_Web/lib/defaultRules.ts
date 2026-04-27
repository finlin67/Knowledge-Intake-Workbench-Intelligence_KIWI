import { ClassificationRules } from '@/types'

export const defaultRules: ClassificationRules = {
  WORKSPACES: {
    unassigned: 'Unassigned',
    operations: 'Operations',
    marketing: 'Marketing',
    finance: 'Finance',
    archive: 'Archive'
  },
  FORCE_RULES: [
    { contains: 'invoice', workspace: 'finance', subfolder: 'invoices', reason: 'Financial document keyword' },
    { contains: 'resume', workspace: 'archive', subfolder: 'resumes', reason: 'Career archive keyword' }
  ],
  COMPANY_MAP: {
    acme: 'operations',
    kiwi: 'marketing'
  },
  PROJECT_MAP: {
    q1: 'marketing',
    q2: 'marketing',
    migration: 'operations'
  },
  DOC_TYPE_PATTERNS: [
    { contains: 'meeting notes', workspace: 'operations', subfolder: 'meetings', reason: 'Meeting pattern' },
    { contains: 'campaign', workspace: 'marketing', subfolder: 'campaigns', reason: 'Campaign pattern' }
  ],
  RULE_CONFIDENCE: {
    force_rule: 0.96,
    company_map: 0.9,
    project_map: 0.85,
    pattern: 0.75,
    fallback: 0.4
  },
  enable_ollama: false,
  ollama_model: 'llama3.2:3b',
  ai_mode: 'rules_only',
  confidence_threshold: 0.65,
  chunk_target_size: 30
}
