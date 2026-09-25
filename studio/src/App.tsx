import { useAuth0 } from '@auth0/auth0-react'
import './App.css'
import { AuthGate } from './components/AuthGate'
import { Sidebar } from './components/Sidebar'
import { VersionHistory } from './components/VersionHistory'
import { VersionEditor } from './components/VersionEditor'
import { Playground } from './components/Playground'
import { Deploy } from './components/Deploy'
import { DeployIcon, EditIcon, HistoryIcon, PlayIcon } from './icons'
import { currentVersionOf, useStudio } from './store'

const TAB_META = {
  history: { label: 'Version history', Icon: HistoryIcon },
  editor: { label: 'Editor', Icon: EditIcon },
  playground: { label: 'Playground', Icon: PlayIcon },
  deploy: { label: 'Deploy', Icon: DeployIcon },
} as const

function Studio() {
  const state = useStudio()
  const { logout } = useAuth0()

  const selected = state.selected
  const versions = selected ? state.versions[selected] ?? [] : []
  const currentVersion = selected ? currentVersionOf(state, selected) : 0

  const currentVersions: Record<string, number | undefined> = {}
  for (const name of state.agents) {
    currentVersions[name] = currentVersionOf(state, name)
  }

  if (!state.org) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <h1>Create your first organization</h1>
          <p>Every agent you build belongs to an organization.</p>
          <button
            className="auth-button"
            onClick={() => {
              const orgId = window.prompt('Organization id (e.g. acme)')
              if (!orgId) return
              const name = window.prompt('Organization name', orgId) ?? orgId
              void state.createOrg(orgId.trim(), name.trim())
            }}
          >
            Create organization
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="shell">
      <Sidebar
        agents={state.agents}
        currentVersions={currentVersions}
        selected={selected ?? ''}
        onSelect={state.selectAgent}
        onAdd={state.addAgent}
        myOrgs={state.myOrgs}
        org={state.org}
        onSelectOrg={(orgId) => void state.selectOrg(orgId)}
        onCreateOrg={(orgId, name) => void state.createOrg(orgId, name)}
        onLogout={() => logout({ logoutParams: { returnTo: window.location.origin } })}
      />

      <div className="main">
        <div className="topbar">
          <div>
            <h1>{selected ?? 'No agent selected'}</h1>
            <div className="subtitle">
              {currentVersion > 0 && <span className="status-dot" />}
              {currentVersion > 0
                ? `version ${currentVersion} is current`
                : 'no version yet'}
            </div>
          </div>
        </div>

        <div className="tabs">
          {(Object.keys(TAB_META) as Array<keyof typeof TAB_META>).map((tab) => {
            const { label, Icon } = TAB_META[tab]
            return (
              <button
                key={tab}
                className={`tab ${state.tab === tab ? 'active' : ''}`}
                onClick={() => state.setTab(tab)}
              >
                <Icon />
                {label}
              </button>
            )
          })}
        </div>

        <div className="panel">
          {state.tab === 'history' && (
            <VersionHistory versions={versions} loading={state.loadingVersions} />
          )}
          {state.tab === 'editor' && (
            <VersionEditor
              currentVersion={currentVersion}
              allTools={state.allTools}
              onCreate={state.createVersion}
            />
          )}
          {state.tab === 'playground' && (
            <Playground
              onRun={state.runPlayground}
              running={state.playgroundRunning}
              result={state.playgroundResult}
              error={state.playgroundError}
              hasVersion={currentVersion > 0}
            />
          )}
          {state.tab === 'deploy' && (
            <Deploy
              versions={versions}
              deployment={state.deployment}
              error={state.deployError}
              onDeploy={state.setDeployment}
              onRollback={state.rollback}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function App() {
  return (
    <AuthGate>
      <Studio />
    </AuthGate>
  )
}

export default App
