export interface AgentVersion {
  agent_name: string
  version: number
  instructions: string
  model: string
  tools: string[]
  created_at: number
}

export interface PlaygroundResult {
  ok: boolean
  room: string
  error: string | null
  join_s: number | null
  ttfa_s: number | null
}

export interface Deployment {
  stable_version: number
  canary_version: number | null
  canary_percent: number
  created_at: number
}

export interface MyOrg {
  org_id: string
  role: string
}

export interface Org {
  org_id: string
  name: string
  created_at: number
}

export interface Member {
  subject: string
  role: string
  created_at: number
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(token: string | null, path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  const resp = await fetch(path, { headers, ...init })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new ApiError(resp.status, body.detail ?? resp.statusText)
  }
  return resp.json() as Promise<T>
}

export const api = {
  listTools: () => request<string[]>(null, '/api/tools'),

  myOrgs: (token: string) => request<MyOrg[]>(token, '/api/me/orgs'),

  createOrg: (token: string, orgId: string, name: string) =>
    request<Org>(token, '/api/orgs', {
      method: 'POST',
      body: JSON.stringify({ org_id: orgId, name }),
    }),

  listMembers: (token: string, org: string) =>
    request<Member[]>(token, `/api/orgs/${org}/members`),

  addMember: (token: string, org: string, subject: string, role: string) =>
    request<Member>(token, `/api/orgs/${org}/members`, {
      method: 'POST',
      body: JSON.stringify({ subject, role }),
    }),

  listVersions: (token: string, org: string, agent: string) =>
    request<AgentVersion[]>(token, `/api/orgs/${org}/agents/${agent}/versions`),

  createVersion: (
    token: string,
    org: string,
    agent: string,
    body: { instructions: string; model: string; tools: string[]; based_on: number },
  ) =>
    request<AgentVersion>(token, `/api/orgs/${org}/agents/${agent}/versions`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  playgroundCall: (
    token: string,
    org: string,
    agent: string,
    questionAudio: string,
    listenS = 20,
  ) =>
    request<PlaygroundResult>(token, `/api/orgs/${org}/agents/${agent}/playground/call`, {
      method: 'POST',
      body: JSON.stringify({ question_audio: questionAudio, listen_s: listenS }),
    }),

  getDeployment: (token: string, org: string, agent: string) =>
    request<Deployment | null>(token, `/api/orgs/${org}/agents/${agent}/deployment`),

  deploy: (
    token: string,
    org: string,
    agent: string,
    body: { stable_version: number; canary_version: number | null; canary_percent: number },
  ) =>
    request<Deployment>(token, `/api/orgs/${org}/agents/${agent}/deployment`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
