'use client'

import { useEffect, useMemo, useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Toggle } from '@/components/ui/Toggle'
import { fetchCategorySuggestions, fetchOllamaModels, getSettings, getToken, saveSettings, testOllamaConnection } from '@/lib/api'

type Tab = 'Workspaces' | 'Companies' | 'Projects' | 'Keywords'
type RulesConfig = Record<string, any>
const cardClass = '!rounded-xl !border-[var(--kiwi-border)] !bg-white shadow-sm'
const sectionHeaderClass =
  'border-b border-[var(--kiwi-border)] pb-2 mb-4 text-[0.65rem] font-bold uppercase tracking-widest text-[var(--kiwi-text-3)]'
const inputClass =
  '!h-10 !rounded-[var(--kiwi-radius-sm)] !border-[var(--kiwi-border)] !bg-white !px-3 !py-2 !text-sm !text-[var(--kiwi-text)] placeholder:!text-[var(--kiwi-text-3)] focus:!border-[var(--kiwi-blue)] focus:!ring-1 focus:!ring-[var(--kiwi-blue)]'
const selectClass =
  '!h-10 !rounded-[var(--kiwi-radius-sm)] !border-[var(--kiwi-border)] !bg-white !px-3 !py-2 !text-sm !text-[var(--kiwi-text)] focus:!border-[var(--kiwi-blue)] focus:!ring-1 focus:!ring-[var(--kiwi-blue)]'
const labelClass = 'text-xs font-semibold text-[var(--kiwi-text-2)]'
const helpClass = 'text-xs text-[var(--kiwi-text-3)]'
const primaryButtonClass =
  '!rounded-[var(--kiwi-radius)] !bg-[var(--kiwi-blue)] !px-4 !py-2 !text-sm !font-semibold !text-white transition-colors duration-150 hover:!bg-[#2f4ac5]'
const secondaryButtonClass =
  '!rounded-[var(--kiwi-radius)] !border !border-[var(--kiwi-border)] !bg-white !px-4 !py-2 !text-sm !font-medium !text-[var(--kiwi-text-2)] hover:!border-[var(--kiwi-blue)] hover:!bg-[var(--kiwi-blue-pale)] hover:!text-[var(--kiwi-blue)]'
const dangerButtonClass =
  '!rounded-[var(--kiwi-radius)] !border !border-[#ffc9c9] !bg-white !px-4 !py-2 !text-sm !font-medium !text-[var(--kiwi-red)] hover:!bg-[var(--kiwi-red-light)]'

export default function SettingsPage() {
  const [provider, setProvider] = useState('ollama')
  const [aiMode, setAiMode] = useState('rules_only')
  const [tab, setTab] = useState<Tab>('Workspaces')
  const [threshold, setThreshold] = useState(0.65)
  const [autoAssign, setAutoAssign] = useState(true)
  const [rules, setRules] = useState<any>(null)
  const [ollamaModel, setOllamaModel] = useState('llama3.2:3b')
  const [ollamaModels, setOllamaModels] = useState<string[]>(['llama3.2:3b'])
  const [ollamaStatus, setOllamaStatus] = useState('Not checked')
  const [ollamaLoading, setOllamaLoading] = useState(false)
  const [suggestionStatus, setSuggestionStatus] = useState('')
  const [suggestionLoading, setSuggestionLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<{
    workspace_suggestions: { key: string; label: string; evidence_count: number }[]
    company_suggestions: { token: string; workspace_key: string; evidence_count: number }[]
    project_suggestions: { token: string; workspace_key: string; evidence_count: number }[]
  }>({ workspace_suggestions: [], company_suggestions: [], project_suggestions: [] })
  const [selectedWorkspaceKeys, setSelectedWorkspaceKeys] = useState<string[]>([])
  const [selectedCompanyTokens, setSelectedCompanyTokens] = useState<string[]>([])
  const [selectedProjectTokens, setSelectedProjectTokens] = useState<string[]>([])
  const [companyWorkspaceMap, setCompanyWorkspaceMap] = useState<Record<string, string>>({})
  const [projectWorkspaceMap, setProjectWorkspaceMap] = useState<Record<string, string>>({})
  const [saveStatus, setSaveStatus] = useState('')
  const [aiSaveStatus, setAiSaveStatus] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [newFolderName, setNewFolderName] = useState('')
  const [workspaceError, setWorkspaceError] = useState('')
  const [saving, setSaving] = useState(false)
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [importBasePath, setImportBasePath] = useState('C:\\Users\\YourName\\Documents\\KIWI\\import')
  const [exportBasePath, setExportBasePath] = useState('C:\\Users\\YourName\\Documents\\KIWI\\export')
  const [lastSavedFingerprint, setLastSavedFingerprint] = useState('')
  const [lastSavedModel, setLastSavedModel] = useState('')

  const syncAiLocalStorage = (config: RulesConfig) => {
    localStorage.setItem('kiwi_ai_provider', String(config?.ai_provider ?? provider))
    localStorage.setItem('kiwi_provider', String(config?.ai_provider ?? provider))
    localStorage.setItem('kiwi_ai_model', String(config?.ollama_model ?? ollamaModel))
    localStorage.setItem('kiwi_ollama_model', String(config?.ollama_model ?? ollamaModel))
    localStorage.setItem('kiwi_model', String(config?.ollama_model ?? ollamaModel))
    localStorage.setItem('kiwi_ai_mode', String(config?.ai_mode ?? aiMode))
    localStorage.setItem('kiwi_mode', String(config?.ai_mode ?? aiMode))
    localStorage.setItem('kiwi_confidence_threshold', String(config?.confidence_threshold ?? threshold))
    localStorage.setItem('kiwi_threshold', String(config?.confidence_threshold ?? threshold))
    localStorage.setItem('kiwi_auto_assign_workspace', String(config?.auto_assign_workspace ?? autoAssign))
    localStorage.setItem('kiwi_auto_assign', String(config?.auto_assign_workspace ?? autoAssign))
  }

  const applyConfigToUi = (config: RulesConfig) => {
    const nextProvider = String(config?.ai_provider ?? provider)
    const nextModel = String(config?.ollama_model ?? ollamaModel)
    const nextMode = String(config?.ai_mode ?? aiMode)
    const rawThreshold = Number(config?.confidence_threshold ?? threshold)
    const nextThreshold = Number.isFinite(rawThreshold) ? rawThreshold : threshold
    const rawAutoAssign = String(config?.auto_assign_workspace ?? autoAssign).toLowerCase()
    const nextAutoAssign = ['1', 'true', 'yes', 'on'].includes(rawAutoAssign)

    setProvider(nextProvider)
    setOllamaModel(nextModel)
    setAiMode(nextMode)
    setThreshold(nextThreshold)
    setAutoAssign(nextAutoAssign)
  }

  const buildConfigForSave = (baseConfig: RulesConfig): RulesConfig => ({
    ...(baseConfig ?? {}),
    ai_provider: provider,
    ollama_model: ollamaModel,
    ai_mode: aiMode,
    confidence_threshold: threshold,
    auto_assign_workspace: autoAssign
  })

  const createSettingsFingerprint = (
    config: RulesConfig | null,
    nextProvider: string,
    nextModel: string,
    nextAiMode: string,
    nextThreshold: number,
    nextAutoAssign: boolean
  ) =>
    JSON.stringify({
      config: config ?? {},
      provider: nextProvider,
      model: nextModel,
      aiMode: nextAiMode,
      threshold: Number(nextThreshold.toFixed(4)),
      autoAssign: nextAutoAssign
    })

  const currentFingerprint = useMemo(
    () => createSettingsFingerprint(rules, provider, ollamaModel, aiMode, threshold, autoAssign),
    [rules, provider, ollamaModel, aiMode, threshold, autoAssign]
  )
  const hasUnsavedChanges =
    !!sessionToken && !!rules && lastSavedFingerprint.length > 0 && currentFingerprint !== lastSavedFingerprint

  const refreshSettings = async () => {
    const data = await getSettings()
    setRules(data.config)
    applyConfigToUi(data.config)
    syncAiLocalStorage(data.config)
    const nextProvider = String(data.config?.ai_provider ?? provider)
    const nextModel = String(data.config?.ollama_model ?? ollamaModel)
    const nextMode = String(data.config?.ai_mode ?? aiMode)
    const rawThreshold = Number(data.config?.confidence_threshold ?? threshold)
    const nextThreshold = Number.isFinite(rawThreshold) ? rawThreshold : threshold
    const rawAutoAssign = String(data.config?.auto_assign_workspace ?? autoAssign).toLowerCase()
    const nextAutoAssign = ['1', 'true', 'yes', 'on'].includes(rawAutoAssign)
    setLastSavedModel(nextModel)
    setLastSavedFingerprint(
      createSettingsFingerprint(data.config, nextProvider, nextModel, nextMode, nextThreshold, nextAutoAssign)
    )
  }

  const syncWorkspaceNames = (config: RulesConfig) => {
    const names = Object.keys(config?.WORKSPACES ?? {})
    localStorage.setItem('kiwi_workspaces', JSON.stringify(names))
  }

  useEffect(() => {
    const token = getToken()
    setSessionToken(token)
    if (!token) {
      setSaveStatus('No active project. Go to Setup and create or load a project first.')
      return
    }
    refreshSettings()
      .catch((err: any) => setSaveStatus(err?.message ?? 'Failed to load settings.'))

    const detectedUsername = navigator.userAgent.includes('Windows')
      ? (localStorage.getItem('kiwi_username') ?? 'YourName')
      : 'YourName'
    const defaultImport = `C:\\Users\\${detectedUsername}\\Documents\\KIWI\\import`
    const defaultExport = `C:\\Users\\${detectedUsername}\\Documents\\KIWI\\export`
    const storedImport = localStorage.getItem('kiwi_import_base') ?? defaultImport
    const storedExport = localStorage.getItem('kiwi_export_base') ?? defaultExport
    if (!localStorage.getItem('kiwi_import_base')) localStorage.setItem('kiwi_import_base', storedImport)
    if (!localStorage.getItem('kiwi_export_base')) localStorage.setItem('kiwi_export_base', storedExport)
    setImportBasePath(storedImport)
    setExportBasePath(storedExport)
  }, [])
  useEffect(() => {
    if (provider === 'ollama') {
      refreshOllamaModels()
    }
  }, [provider])

  const refreshOllamaModels = async () => {
    setOllamaLoading(true)
    try {
      const data = await fetchOllamaModels()
      if (data.models.length) {
        setOllamaModels(data.models)
        if (!data.models.includes(ollamaModel)) {
          setOllamaModel(data.models[0])
        }
      }
      setOllamaStatus(data.message)
    } catch (err: any) {
      setOllamaStatus(err?.message ?? 'Failed to refresh models.')
    } finally {
      setOllamaLoading(false)
    }
  }

  const handleTestOllama = async () => {
    setOllamaLoading(true)
    try {
      const data = await testOllamaConnection(ollamaModel)
      setOllamaStatus(data.message)
    } catch (err: any) {
      setOllamaStatus(err?.message ?? 'Failed to test connection.')
    } finally {
      setOllamaLoading(false)
    }
  }

  const runSuggestCategories = async () => {
    setSuggestionLoading(true)
    setSuggestionStatus('')
    try {
      const data = await fetchCategorySuggestions()
      setSuggestions({
        workspace_suggestions: data.workspace_suggestions ?? [],
        company_suggestions: data.company_suggestions ?? [],
        project_suggestions: data.project_suggestions ?? []
      })
      const companyDefaults: Record<string, string> = {}
      for (const item of data.company_suggestions ?? []) {
        companyDefaults[item.token] = item.workspace_key || 'operations'
      }
      const projectDefaults: Record<string, string> = {}
      for (const item of data.project_suggestions ?? []) {
        projectDefaults[item.token] = item.workspace_key || 'operations'
      }
      setCompanyWorkspaceMap(companyDefaults)
      setProjectWorkspaceMap(projectDefaults)
      setSelectedWorkspaceKeys((data.workspace_suggestions ?? []).map((item) => item.key))
      setSelectedCompanyTokens((data.company_suggestions ?? []).map((item) => item.token))
      setSelectedProjectTokens((data.project_suggestions ?? []).map((item) => item.token))
      setSuggestionStatus(data.message)
    } catch (err: any) {
      setSuggestionStatus(err?.message ?? 'Failed to generate suggestions.')
    } finally {
      setSuggestionLoading(false)
    }
  }

  const persistAndRefresh = async (config: RulesConfig, successMessage: string) => {
    setSaving(true)
    setSaveStatus('')
    await saveSettings(config)
    syncWorkspaceNames(config)
    syncAiLocalStorage(config)
    await refreshSettings()
    setSaveStatus(successMessage)
    setSaving(false)
  }

  const handleBackToHome = () => {
    if (hasUnsavedChanges) {
      const shouldLeave = window.confirm('You have unsaved settings changes. Leave this page without saving?')
      if (!shouldLeave) return
    }
    window.location.href = '/'
  }

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [hasUnsavedChanges])

  useEffect(() => {
    if (!aiSaveStatus) return
    const id = window.setTimeout(() => {
      setAiSaveStatus('')
    }, 3000)
    return () => window.clearTimeout(id)
  }, [aiSaveStatus])

  const applySuggestionsToRules = async () => {
    if (!rules) return
    try {
      const next = { ...(rules ?? {}) }
      next.WORKSPACES = { ...(next.WORKSPACES ?? {}) }
      next.COMPANY_MAP = { ...(next.COMPANY_MAP ?? {}) }
      next.PROJECT_MAP = { ...(next.PROJECT_MAP ?? {}) }
      let appliedCount = 0

      for (const ws of suggestions.workspace_suggestions) {
        if (!selectedWorkspaceKeys.includes(ws.key)) continue
        if (!next.WORKSPACES[ws.key]) {
          next.WORKSPACES[ws.key] = ws.label
          appliedCount += 1
        }
      }
      for (const company of suggestions.company_suggestions) {
        if (!selectedCompanyTokens.includes(company.token)) continue
        if (!next.COMPANY_MAP[company.token]) {
          next.COMPANY_MAP[company.token] = companyWorkspaceMap[company.token] || company.workspace_key || 'operations'
          appliedCount += 1
        }
      }
      for (const project of suggestions.project_suggestions) {
        if (!selectedProjectTokens.includes(project.token)) continue
        if (!next.PROJECT_MAP[project.token]) {
          next.PROJECT_MAP[project.token] = projectWorkspaceMap[project.token] || project.workspace_key || 'operations'
          appliedCount += 1
        }
      }

      await persistAndRefresh(next, `${appliedCount} suggestions applied and saved`)
      setSuggestionStatus(`${appliedCount} suggestions applied and saved`)
    } catch (err: any) {
      setSuggestionStatus(err?.message ?? 'Failed to apply suggestions.')
      setSaveStatus(err?.message ?? 'Failed to apply suggestions.')
      setSaving(false)
    }
  }

  const workspaceOptions = Array.from(new Set([
    ...Object.keys(rules?.WORKSPACES ?? {}),
    ...suggestions.workspace_suggestions.map((w) => w.key),
    'operations'
  ])).sort((a, b) => a.localeCompare(b))

  const saveCategories = async () => {
    if (!rules) {
      setSaveStatus('Nothing to save yet.')
      return
    }
    try {
      await persistAndRefresh(buildConfigForSave(rules), 'Settings saved')
    } catch (err: any) {
      setSaveStatus(err?.message ?? 'Failed to save categories.')
      setSaving(false)
    }
  }

  const saveAiSettings = async () => {
    setAiSaveStatus('')
    if (!rules) {
      setSaveStatus('Nothing to save yet.')
      setAiSaveStatus('Nothing to save yet.')
      return
    }
    try {
      await persistAndRefresh(buildConfigForSave(rules), 'AI settings saved')
      setAiSaveStatus('AI settings saved')
    } catch (err: any) {
      const message = err?.message ?? 'Failed to save AI settings.'
      setSaveStatus(message)
      setAiSaveStatus(message)
      setSaving(false)
    }
  }

  const workspaceEntries = Object.entries(rules?.WORKSPACES ?? {}) as [string, string][]

  const addWorkspace = async () => {
    if (!rules || !newLabel.trim() || !newFolderName.trim()) return
    const key = newFolderName.trim().toLowerCase()
    const labelExists = Object.values(rules.WORKSPACES ?? {}).some(
      (value) => String(value).toLowerCase() === newLabel.trim().toLowerCase()
    )
    if (rules.WORKSPACES?.[key] || labelExists) {
      setWorkspaceError('Workspace label already exists.')
      return
    }
    setWorkspaceError('')
    const updated = {
      ...rules,
      WORKSPACES: {
        ...(rules.WORKSPACES ?? {}),
        [key]: newLabel.trim()
      }
    }
    try {
      await persistAndRefresh(updated, 'Settings saved')
      setRules(updated)
      setNewLabel('')
      setNewFolderName('')
    } catch (err: any) {
      setSaveStatus(err?.message ?? 'Failed to add workspace.')
      setSaving(false)
    }
  }

  const removeWorkspace = async (workspaceKey: string) => {
    if (!rules) return
    const nextWorkspaces = { ...(rules.WORKSPACES ?? {}) }
    delete nextWorkspaces[workspaceKey]
    const updated = { ...rules, WORKSPACES: nextWorkspaces }
    try {
      await persistAndRefresh(updated, 'Settings saved')
      setRules(updated)
    } catch (err: any) {
      setSaveStatus(err?.message ?? 'Failed to remove workspace.')
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 bg-[var(--kiwi-bg)]">
      <button type="button" onClick={handleBackToHome} className="mb-6 inline-flex items-center gap-1.5 text-sm text-[#3b5bdb] hover:underline">
        ← Back to Home
      </button>
      <PageHeader title="Settings" />
      <Card className={`${cardClass} space-y-4`}>
        <h2 className={sectionHeaderClass}>Default Paths</h2>
        <p className="text-sm text-[var(--kiwi-text-2)]">
          Set the initial import/export base paths used on the Setup page.
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className={labelClass}>Import base path</label>
            <Input
              className={`${inputClass} font-mono`}
              value={importBasePath}
              onChange={(e) => {
                const value = e.target.value
                setImportBasePath(value)
                localStorage.setItem('kiwi_import_base', value)
              }}
            />
          </div>
          <div className="space-y-2">
            <label className={labelClass}>Export base path</label>
            <Input
              className={`${inputClass} font-mono`}
              value={exportBasePath}
              onChange={(e) => {
                const value = e.target.value
                setExportBasePath(value)
                localStorage.setItem('kiwi_export_base', value)
              }}
            />
          </div>
        </div>
        <p className={helpClass}>These values save automatically and are used as defaults in Setup.</p>
      </Card>
      <Card className={`${cardClass} space-y-4`}>
        <h2 className={sectionHeaderClass}>AI Configuration</h2>
        <div className="flex items-center gap-2">
          <span className={labelClass}>Provider</span>
          <Select className={`w-52 ${selectClass}`} value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="ollama">Ollama</option>
            <option value="claude">Claude (Anthropic)</option>
            <option value="openai">OpenAI</option>
          </Select>
        </div>
        {provider === 'ollama' ? (
          <div className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
            <Select className={selectClass} value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)}>
              {ollamaModels.map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
            </Select>
            <Button variant="secondary" className={secondaryButtonClass} onClick={refreshOllamaModels} disabled={ollamaLoading}>
              {ollamaLoading ? 'Refreshing...' : 'Refresh Models'}
            </Button>
            <Button variant="secondary" className={secondaryButtonClass} onClick={handleTestOllama} disabled={ollamaLoading}>
              Test Connection
            </Button>
            <p className="md:col-span-3 text-sm text-[var(--kiwi-text-2)]">{ollamaStatus}</p>
          </div>
        ) : (
          <div className="space-y-3">
            <Input className={inputClass} type="password" placeholder="API Key" />
            <Select className={selectClass}>{provider === 'claude' ? <><option>claude-sonnet-4-5</option><option>claude-haiku-4-5-20251001</option></> : <><option>gpt-4o</option><option>gpt-4o-mini</option></>}</Select>
          </div>
        )}
        <div>
          <Select className={selectClass} value={aiMode} onChange={(e) => setAiMode(e.target.value)}>
            <option>rules_only</option>
            <option>ai_only_unclassified</option>
            <option>ai_all</option>
          </Select>
        </div>
        <div className="flex justify-end">
          <Button className={primaryButtonClass} onClick={saveAiSettings} disabled={!sessionToken || saving || !rules}>
            {saving ? 'Saving...' : 'Save AI Settings'}
          </Button>
        </div>
        {aiSaveStatus ? (
          <p className={`text-xs ${aiSaveStatus.toLowerCase().includes('failed') ? 'text-[var(--kiwi-red)]' : 'text-[var(--kiwi-green)]'}`}>
            {aiSaveStatus}
          </p>
        ) : null}
        <p className={helpClass}>Last saved model: {lastSavedModel || 'Not saved yet'}</p>
        {hasUnsavedChanges ? <p className="text-xs text-[var(--kiwi-amber)]">You have unsaved changes.</p> : null}
      </Card>

      <Card className={`${cardClass} space-y-4`}>
        <h2 className={sectionHeaderClass}>Workspaces &amp; Classification</h2>
        <p className="text-sm text-[var(--kiwi-text-2)]">Teach KIWI about your projects and companies</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" className={secondaryButtonClass} onClick={runSuggestCategories} disabled={suggestionLoading}>
            {suggestionLoading ? 'Analyzing scanned files...' : 'Suggest Categories from Scanned Files'}
          </Button>
          <Button variant="secondary" className={secondaryButtonClass} onClick={applySuggestionsToRules} disabled={!suggestions.workspace_suggestions.length && !suggestions.company_suggestions.length && !suggestions.project_suggestions.length}>
            Apply Suggestions
          </Button>
        </div>
        {suggestionStatus ? <p className={helpClass}>{suggestionStatus}</p> : null}
        {(suggestions.workspace_suggestions.length || suggestions.company_suggestions.length || suggestions.project_suggestions.length) ? (
          <div className="space-y-4 rounded-[var(--kiwi-radius)] border border-[var(--kiwi-border)] bg-white p-4 text-xs text-[var(--kiwi-text-2)]">
            <div className="flex items-center justify-between">
              <p className="font-medium text-[var(--kiwi-text)]">Suggestion Checklist</p>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  className={secondaryButtonClass}
                  onClick={() => {
                    setSelectedWorkspaceKeys(suggestions.workspace_suggestions.map((w) => w.key))
                    setSelectedCompanyTokens(suggestions.company_suggestions.map((c) => c.token))
                    setSelectedProjectTokens(suggestions.project_suggestions.map((p) => p.token))
                  }}
                >
                  Select All
                </Button>
                <Button
                  variant="secondary"
                  className={secondaryButtonClass}
                  onClick={() => {
                    setSelectedWorkspaceKeys([])
                    setSelectedCompanyTokens([])
                    setSelectedProjectTokens([])
                  }}
                >
                  Clear
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-[var(--kiwi-text)]">Workspace suggestions</p>
              {suggestions.workspace_suggestions.length ? suggestions.workspace_suggestions.map((item) => (
                <label key={item.key} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedWorkspaceKeys.includes(item.key)}
                    onChange={(e) =>
                      setSelectedWorkspaceKeys((prev) =>
                        e.target.checked ? [...prev, item.key] : prev.filter((x) => x !== item.key)
                      )
                    }
                  />
                  <span>{item.key} ({item.evidence_count})</span>
                </label>
              )) : <p>None</p>}
            </div>

            <div className="space-y-2">
              <p className="text-[var(--kiwi-text)]">Company token suggestions</p>
              {suggestions.company_suggestions.length ? suggestions.company_suggestions.map((item) => (
                <div key={`company-${item.token}`} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedCompanyTokens.includes(item.token)}
                    onChange={(e) =>
                      setSelectedCompanyTokens((prev) =>
                        e.target.checked ? [...prev, item.token] : prev.filter((x) => x !== item.token)
                      )
                    }
                  />
                  <span className="min-w-[180px]">{item.token} ({item.evidence_count})</span>
                  <Select
                    className={`max-w-[220px] ${selectClass}`}
                    value={companyWorkspaceMap[item.token] || item.workspace_key || 'operations'}
                    onChange={(e) =>
                      setCompanyWorkspaceMap((prev) => ({ ...prev, [item.token]: e.target.value }))
                    }
                  >
                    {workspaceOptions.map((workspaceKey) => (
                      <option key={`company-opt-${item.token}-${workspaceKey}`} value={workspaceKey}>
                        {workspaceKey}
                      </option>
                    ))}
                  </Select>
                </div>
              )) : <p>None</p>}
            </div>

            <div className="space-y-2">
              <p className="text-[var(--kiwi-text)]">Project token suggestions</p>
              {suggestions.project_suggestions.length ? suggestions.project_suggestions.map((item) => (
                <div key={`project-${item.token}`} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedProjectTokens.includes(item.token)}
                    onChange={(e) =>
                      setSelectedProjectTokens((prev) =>
                        e.target.checked ? [...prev, item.token] : prev.filter((x) => x !== item.token)
                      )
                    }
                  />
                  <span className="min-w-[180px]">{item.token} ({item.evidence_count})</span>
                  <Select
                    className={`max-w-[220px] ${selectClass}`}
                    value={projectWorkspaceMap[item.token] || item.workspace_key || 'operations'}
                    onChange={(e) =>
                      setProjectWorkspaceMap((prev) => ({ ...prev, [item.token]: e.target.value }))
                    }
                  >
                    {workspaceOptions.map((workspaceKey) => (
                      <option key={`project-opt-${item.token}-${workspaceKey}`} value={workspaceKey}>
                        {workspaceKey}
                      </option>
                    ))}
                  </Select>
                </div>
              )) : <p>None</p>}
            </div>
          </div>
        ) : null}
        <div className="flex border-b border-[var(--kiwi-border)]">
          {(['Workspaces', 'Companies', 'Projects', 'Keywords'] as Tab[]).map((item) => (
            <button key={item} className={`px-3 py-2 text-sm ${tab === item ? 'border-b-2 border-[var(--kiwi-blue)] text-[var(--kiwi-text)]' : 'text-[var(--kiwi-text-3)] hover:text-[var(--kiwi-text-2)]'}`} onClick={() => setTab(item)}>{item}</button>
          ))}
        </div>
        <div className="max-h-[240px] overflow-y-auto rounded-[var(--kiwi-radius)] border border-[var(--kiwi-border)] bg-white">
          {tab === 'Workspaces' ? (
            workspaceEntries.length ? workspaceEntries.map(([key, label]) => (
              <div key={key} className="group flex items-center justify-between border-b border-[var(--kiwi-border)] bg-white px-4 py-2 text-sm hover:bg-[var(--kiwi-blue-pale)]">
                <span>{label} {'->'} {key}</span>
                <button type="button" className="invisible text-xs text-[var(--kiwi-red)] group-hover:visible" onClick={() => removeWorkspace(key)} disabled={saving}>Remove</button>
              </div>
            )) : <p className="p-4 text-sm text-[var(--kiwi-text-3)]">No workspaces configured.</p>
          ) : (
            <p className="p-4 text-sm text-[var(--kiwi-text-3)]">Editing for this tab is not implemented yet.</p>
          )}
        </div>
        {tab === 'Workspaces' ? (
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input
                className={inputClass}
                placeholder="Workspace label"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
              />
              <Input
                className={inputClass}
                placeholder="Folder key (example: operations)"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
              />
              <Button className={primaryButtonClass} onClick={addWorkspace} disabled={!newLabel.trim() || !newFolderName.trim() || saving}>Add Workspace</Button>
            </div>
            {workspaceError ? <p className="text-xs text-[var(--kiwi-red)]">{workspaceError}</p> : null}
          </div>
        ) : (
          <div className="flex gap-2">
            <Input className={inputClass} placeholder={`Add ${tab.toLowerCase()} value`} />
            <Input className={inputClass} placeholder="workspace" />
            <Button className={secondaryButtonClass} disabled>Add</Button>
          </div>
        )}
        <p className={helpClass}>Rules are saved into your project classification rules file.</p>
        <p className={helpClass}>Starter workspaces: Operations, Marketing, Finance, Archive, Unassigned. You can add your own project/company categories.</p>
        {saveStatus ? <p className={helpClass}>{saveStatus}</p> : null}
        <Button className={`w-full ${primaryButtonClass}`} onClick={saveCategories} disabled={!sessionToken || saving}>{saving ? 'Saving...' : 'Save Categories'}</Button>
      </Card>

      <Card className={`${cardClass} space-y-4`}>
        <h2 className={sectionHeaderClass}>PROCESSING BEHAVIOR</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className={labelClass}>Confidence threshold: {threshold.toFixed(2)}</label>
            <input type="range" min={0.5} max={0.95} step={0.01} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} className="w-full" />
          </div>
          <div><Select className={selectClass}><option>rules_only</option><option>always_ai</option><option>ai_only_unclassified</option></Select></div>
          <div className="flex items-center gap-2"><span className="text-sm text-[var(--kiwi-text-2)]">Auto-assign workspace</span><Toggle checked={autoAssign} onChange={setAutoAssign} /></div>
          <div><Select className={selectClass}><option>rename</option><option>skip</option><option>overwrite</option></Select></div>
          <Input className={inputClass} type="number" placeholder="Chunk target size" />
          <Input className={inputClass} type="number" placeholder="Min chunk size" />
        </div>
        <p className={helpClass}>Start with confidence 0.65. Raise to send more files to review.</p>
        <hr className="my-4 border-[var(--kiwi-border)]" />
        <div className="flex gap-2"><Button variant="danger" className={dangerButtonClass}>Reset to Defaults</Button><Button className={primaryButtonClass} onClick={saveCategories} disabled={!sessionToken || saving}>{saving ? 'Saving...' : 'Save Settings'}</Button></div>
      </Card>
    </div>
  )
}
