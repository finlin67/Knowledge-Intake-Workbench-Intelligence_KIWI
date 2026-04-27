import { RunStatus } from '@/types'

const runState: Record<number, RunStatus> = {}

export const getRunState = (projectId: number): RunStatus | undefined => runState[projectId]

export const setRunState = (projectId: number, state: RunStatus): RunStatus => {
  runState[projectId] = state
  return runState[projectId]
}

export const updateRunState = (projectId: number, updater: (state: RunStatus) => RunStatus): RunStatus | undefined => {
  const current = runState[projectId]
  if (!current) return undefined
  runState[projectId] = updater(current)
  return runState[projectId]
}

export const clearRunState = (projectId: number): void => {
  delete runState[projectId]
}
