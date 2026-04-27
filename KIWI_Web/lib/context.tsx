'use client'

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react'
import { getLastProject, SESSION_KEY } from '@/lib/api'

const PROJECT_KEY = 'kiwi_project'

export interface ProjectState {
  session_token: string
  name: string
  raw_folder: string
  output_folder: string
}

interface ProjectContextValue {
  project: ProjectState | null
  setProject: (nextProject: ProjectState | null) => void
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined)

function readInitialProject(): ProjectState | null {
  if (typeof window === 'undefined') return null
  const storedProject = localStorage.getItem(PROJECT_KEY)
  if (!storedProject) return null

  try {
    return JSON.parse(storedProject) as ProjectState
  } catch {
    localStorage.removeItem(PROJECT_KEY)
    return null
  }
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProjectState] = useState<ProjectState | null>(null)

  useEffect(() => {
    setProjectState(readInitialProject())
    getLastProject()
      .then((project) => {
        if (!project) return
        setProject({
          session_token: project.session_token,
          name: project.name,
          raw_folder: project.raw_folder,
          output_folder: project.output_folder
        })
      })
      .catch(() => {
        // Keep existing local state if API is unavailable.
      })
  }, [])

  const setProject = (nextProject: ProjectState | null) => {
    setProjectState(nextProject)
    if (typeof window === 'undefined') return

    if (nextProject) {
      localStorage.setItem(PROJECT_KEY, JSON.stringify(nextProject))
      localStorage.setItem(SESSION_KEY, nextProject.session_token)
      return
    }

    localStorage.removeItem(PROJECT_KEY)
    localStorage.removeItem(SESSION_KEY)
  }

  const value = useMemo(() => ({ project, setProject }), [project])

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
}

export function useProjectContext() {
  const context = useContext(ProjectContext)
  if (!context) throw new Error('useProjectContext must be used inside ProjectProvider')
  return context
}
