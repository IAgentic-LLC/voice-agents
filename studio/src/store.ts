import { create } from 'zustand'
import {
  api,
  type AgentVersion,
  type Deployment,
  type MyOrg,
  type PlaygroundResult,
} from './api'

type Tab = 'history' | 'editor' | 'playground' | 'deploy'

interface StudioState {
  token: string | null
  myOrgs: MyOrg[]
  org: string | null
  agents: string[]
  selected: string | null
  versions: Record<string, AgentVersion[]>
  loadingVersions: boolean
  allTools: string[]
  tab: Tab
  playgroundResult: PlaygroundResult | null
  playgroundRunning: boolean
  playgroundError: string | null
  deployment: Deployment | null
  loadingDeployment: boolean
  deployError: string | null

  setToken: (token: string) => Promise<void>
  loadMyOrgs: () => Promise<void>
  createOrg: (orgId: string, name: string) => Promise<void>
  selectOrg: (orgId: string) => Promise<void>
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
  loadDeployment: (name: string) => Promise<void>
  setDeployment: (body: {
    stable_version: number
    canary_version: number | null
    canary_percent: number
  }) => Promise<void>
  rollback: () => Promise<void>
}

export const useStudio = create<StudioState>((set, get) => ({
  token: null,
  myOrgs: [],
  org: null,
  agents: ['dynabook'],
  selected: 'dynabook',
  versions: {},
  loadingVersions: false,
  allTools: [],
  tab: 'history',
  playgroundResult: null,
  playgroundRunning: false,
  playgroundError: null,
  deployment: null,
  loadingDeployment: false,
  deployError: null,

  setToken: async (token) => {
    set({ token })
    const allTools = await api.listTools()
    set({ allTools })
    await get().loadMyOrgs()
  },

  loadMyOrgs: async () => {
    const token = get().token
    if (!token) return
    const myOrgs = await api.myOrgs(token)
    set({ myOrgs })
    if (myOrgs.length > 0 && !get().org) {
      await get().selectOrg(myOrgs[0].org_id)
    }
  },

  createOrg: async (orgId, name) => {
    const token = get().token
    if (!token) return
    await api.createOrg(token, orgId, name)
    await get().selectOrg(orgId)
    void get().loadMyOrgs()
  },

  selectOrg: async (orgId) => {
    set({
      org: orgId, versions: {}, deployment: null, playgroundResult: null,
    })
    const selected = get().selected
    if (selected) {
      await Promise.all([get().loadVersions(selected), get().loadDeployment(selected)])
    }
  },

  selectAgent: (name) => {
    set({ selected: name, playgroundResult: null, deployment: null })
    void get().loadVersions(name)
    void get().loadDeployment(name)
  },

  addAgent: (name) => {
    set((s) => ({
      agents: s.agents.includes(name) ? s.agents : [...s.agents, name],
    }))
    get().selectAgent(name)
  },

  setTab: (tab) => set({ tab }),

  loadVersions: async (name) => {
    const { token, org } = get()
    if (!token || !org) return
    set({ loadingVersions: true })
    const versions = await api.listVersions(token, org, name)
    set((s) => ({
      versions: { ...s.versions, [name]: versions },
      loadingVersions: false,
    }))
  },

  createVersion: async (body) => {
    const { token, org, selected } = get()
    if (!token || !org || !selected) return
    await api.createVersion(token, org, selected, body)
    await get().loadVersions(selected)
  },

  runPlayground: async (questionAudio) => {
    const { token, org, selected } = get()
    if (!token || !org || !selected) return
    set({ playgroundRunning: true, playgroundResult: null, playgroundError: null })
    try {
      const result = await api.playgroundCall(token, org, selected, questionAudio)
      set({ playgroundResult: result })
    } catch (err) {
      set({ playgroundError: err instanceof Error ? err.message : String(err) })
    } finally {
      set({ playgroundRunning: false })
    }
  },

  loadDeployment: async (name) => {
    const { token, org } = get()
    if (!token || !org) return
    set({ loadingDeployment: true })
    const deployment = await api.getDeployment(token, org, name)
    set({ deployment, loadingDeployment: false })
  },

  setDeployment: async (body) => {
    const { token, org, selected } = get()
    if (!token || !org || !selected) return
    set({ deployError: null })
    try {
      const deployment = await api.deploy(token, org, selected, body)
      set({ deployment })
    } catch (err) {
      set({ deployError: err instanceof Error ? err.message : String(err) })
      throw err
    }
  },

  rollback: async () => {
    const deployment = get().deployment
    if (!deployment) return
    await get().setDeployment({
      stable_version: deployment.stable_version,
      canary_version: null,
      canary_percent: 0,
    })
  },
}))

export function currentVersionOf(state: StudioState, name: string): number {
  const versions = state.versions[name]
  return versions && versions.length ? versions[versions.length - 1].version : 0
}
