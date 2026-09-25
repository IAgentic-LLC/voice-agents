import { create } from 'zustand'
import { api, type AgentVersion, type PlaygroundResult } from './api'

type Tab = 'history' | 'editor' | 'playground'

interface StudioState {
  agents: string[]
  selected: string | null
  versions: Record<string, AgentVersion[]>
  loadingVersions: boolean
  allTools: string[]
  tab: Tab
  playgroundResult: PlaygroundResult | null
  playgroundRunning: boolean
  playgroundError: string | null

  init: () => Promise<void>
  selectAgent: (name: string) => void
  addAgent: (name: string) => void
  setTab: (tab: Tab) => void
  loadVersions: (name: string) => Promise<void>
  createVersion: (body: {
    instructions: string
    model: string
    tools: string[]
    based_on: number
  }) => Promise<void>
  runPlayground: (questionAudio: string) => Promise<void>
}

export const useStudio = create<StudioState>((set, get) => ({
  agents: ['dynabook'],
  selected: 'dynabook',
  versions: {},
  loadingVersions: false,
  allTools: [],
  tab: 'history',
  playgroundResult: null,
  playgroundRunning: false,
  playgroundError: null,

  init: async () => {
    const allTools = await api.listTools()
    set({ allTools })
    const selected = get().selected
    if (selected) await get().loadVersions(selected)
  },

  selectAgent: (name) => {
    set({ selected: name, playgroundResult: null })
    void get().loadVersions(name)
  },

  addAgent: (name) => {
    set((s) => ({
      agents: s.agents.includes(name) ? s.agents : [...s.agents, name],
    }))
    get().selectAgent(name)
  },

  setTab: (tab) => set({ tab }),

  loadVersions: async (name) => {
    set({ loadingVersions: true })
    const versions = await api.listVersions(name)
    set((s) => ({
      versions: { ...s.versions, [name]: versions },
      loadingVersions: false,
    }))
  },

  createVersion: async (body) => {
    const selected = get().selected
    if (!selected) return
    await api.createVersion(selected, body)
    await get().loadVersions(selected)
  },

  runPlayground: async (questionAudio) => {
    const selected = get().selected
    if (!selected) return
    set({ playgroundRunning: true, playgroundResult: null, playgroundError: null })
    try {
      const result = await api.playgroundCall(selected, questionAudio)
      set({ playgroundResult: result })
    } catch (err) {
      set({ playgroundError: err instanceof Error ? err.message : String(err) })
    } finally {
      set({ playgroundRunning: false })
    }
  },
}))

export function currentVersionOf(state: StudioState, name: string): number {
  const versions = state.versions[name]
  return versions && versions.length ? versions[versions.length - 1].version : 0
}
