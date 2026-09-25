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

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new ApiError(resp.status, body.detail ?? resp.statusText)
  }
  return resp.json() as Promise<T>
}

export const api = {
  listTools: () => request<string[]>('/api/tools'),

  listVersions: (agent: string) =>
    request<AgentVersion[]>(`/api/agents/${agent}/versions`),

  createVersion: (
    agent: string,
    body: { instructions: string; model: string; tools: string[]; based_on: number },
  ) =>
    request<AgentVersion>(`/api/agents/${agent}/versions`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  playgroundCall: (agent: string, questionAudio: string, listenS = 20) =>
    request<PlaygroundResult>(`/api/agents/${agent}/playground/call`, {
      method: 'POST',
      body: JSON.stringify({ question_audio: questionAudio, listen_s: listenS }),
    }),
}
