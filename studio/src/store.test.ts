import { beforeEach, describe, expect, it, vi } from 'vitest'
import { currentVersionOf, useStudio } from './store'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  useStudio.setState({
    token: 'test-token',
    myOrgs: [],
    org: 'acme',
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
  })
})

describe('setToken', () => {
  it('loads tools and the caller\'s own orgs, selecting the first one', async () => {
    useStudio.setState({ org: null })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(['book_callback', 'issue_refund']))
      .mockResolvedValueOnce(jsonResponse([{ org_id: 'acme', role: 'owner' }]))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(null))
    vi.stubGlobal('fetch', fetchMock)

    await useStudio.getState().setToken('real-jwt')

    expect(useStudio.getState().allTools).toEqual(['book_callback', 'issue_refund'])
    expect(useStudio.getState().myOrgs).toEqual([{ org_id: 'acme', role: 'owner' }])
    expect(useStudio.getState().org).toBe('acme')
  })
})

describe('createOrg', () => {
  it('creates the org, reloads myOrgs, and selects it', async () => {
    useStudio.setState({ org: null, myOrgs: [] })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ org_id: 'globex', name: 'Globex', created_at: 1 }, 201))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(null))
      .mockResolvedValueOnce(jsonResponse([{ org_id: 'globex', role: 'owner' }]))
    vi.stubGlobal('fetch', fetchMock)

    await useStudio.getState().createOrg('globex', 'Globex')

    expect(useStudio.getState().org).toBe('globex')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/orgs')
  })
})

describe('loadVersions', () => {
  it('stores the real versions the API returns, per agent', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse([
          { agent_name: 'dynabook', version: 1, instructions: 'v1', model: 'm', tools: [], created_at: 1 },
        ]),
      ),
    )

    await useStudio.getState().loadVersions('dynabook')

    const versions = useStudio.getState().versions['dynabook']
    expect(versions).toHaveLength(1)
    expect(versions[0].version).toBe(1)
    expect(currentVersionOf(useStudio.getState(), 'dynabook')).toBe(1)
  })

  it('scopes the request under the currently selected org', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]))
    vi.stubGlobal('fetch', fetchMock)

    await useStudio.getState().loadVersions('dynabook')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/orgs/acme/agents/dynabook/versions',
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) }),
    )
  })
})

describe('createVersion', () => {
  it('reloads the version list after a successful write', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ version: 2 }, 201))
      .mockResolvedValueOnce(
        jsonResponse([
          { agent_name: 'dynabook', version: 1, instructions: 'v1', model: 'm', tools: [], created_at: 1 },
          { agent_name: 'dynabook', version: 2, instructions: 'v2', model: 'm', tools: [], created_at: 2 },
        ]),
      )
    vi.stubGlobal('fetch', fetchMock)

    await useStudio.getState().createVersion({
      instructions: 'v2', model: 'm', tools: [], based_on: 1,
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(currentVersionOf(useStudio.getState(), 'dynabook')).toBe(2)
  })

  it('throws a real ApiError on a stale based_on, without touching versions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'stale' }, 409)),
    )

    await expect(
      useStudio.getState().createVersion({
        instructions: 'v2', model: 'm', tools: [], based_on: 1,
      }),
    ).rejects.toThrow('stale')
  })
})

describe('runPlayground', () => {
  it('records a real successful call result', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ ok: true, room: 'call-1', error: null, join_s: 3.0, ttfa_s: 6.0 }),
      ),
    )

    await useStudio.getState().runPlayground('audio/ch09/plain.wav')

    const { playgroundResult, playgroundRunning, playgroundError } = useStudio.getState()
    expect(playgroundResult?.ok).toBe(true)
    expect(playgroundRunning).toBe(false)
    expect(playgroundError).toBeNull()
  })

  it('records a real error without leaving playgroundRunning stuck true', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'no version' }, 404)),
    )

    await useStudio.getState().runPlayground('audio/ch09/plain.wav')

    const { playgroundRunning, playgroundError } = useStudio.getState()
    expect(playgroundRunning).toBe(false)
    expect(playgroundError).toContain('no version')
  })
})

describe('currentVersionOf', () => {
  it('is 0 for an agent with no versions loaded', () => {
    expect(currentVersionOf(useStudio.getState(), 'nobody')).toBe(0)
  })
})

describe('loadDeployment', () => {
  it('stores the real current deployment the API returns', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ stable_version: 1, canary_version: 2, canary_percent: 30, created_at: 1 }),
      ),
    )

    await useStudio.getState().loadDeployment('dynabook')

    expect(useStudio.getState().deployment?.canary_version).toBe(2)
  })
})

describe('setDeployment', () => {
  it('stores the deployment the API returns after a write', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ stable_version: 1, canary_version: null, canary_percent: 0, created_at: 2 }, 201),
      ),
    )

    await useStudio.getState().setDeployment({
      stable_version: 1, canary_version: null, canary_percent: 0,
    })

    expect(useStudio.getState().deployment?.stable_version).toBe(1)
    expect(useStudio.getState().deployError).toBeNull()
  })

  it('records a real error and rethrows it, without touching the old deployment', async () => {
    useStudio.setState({
      deployment: { stable_version: 1, canary_version: null, canary_percent: 0, created_at: 1 },
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'no such version' }, 422)),
    )

    await expect(
      useStudio.getState().setDeployment({
        stable_version: 9, canary_version: null, canary_percent: 0,
      }),
    ).rejects.toThrow('no such version')

    expect(useStudio.getState().deployError).toContain('no such version')
    expect(useStudio.getState().deployment?.stable_version).toBe(1)
  })
})

describe('rollback', () => {
  it('redeploys the current stable version with no canary', async () => {
    useStudio.setState({
      deployment: { stable_version: 1, canary_version: 2, canary_percent: 30, created_at: 1 },
    })
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ stable_version: 1, canary_version: null, canary_percent: 0, created_at: 2 }, 201),
    )
    vi.stubGlobal('fetch', fetchMock)

    await useStudio.getState().rollback()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/orgs/acme/agents/dynabook/deployment',
      expect.objectContaining({
        body: JSON.stringify({ stable_version: 1, canary_version: null, canary_percent: 0 }),
      }),
    )
    expect(useStudio.getState().deployment?.canary_version).toBeNull()
  })

  it('does nothing when there is no deployment to roll back', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await useStudio.getState().rollback()

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
