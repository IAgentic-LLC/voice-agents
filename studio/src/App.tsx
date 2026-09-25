import { useEffect } from 'react'
import './App.css'
import { Sidebar } from './components/Sidebar'
import { VersionHistory } from './components/VersionHistory'
import { VersionEditor } from './components/VersionEditor'
import { Playground } from './components/Playground'
import { EditIcon, HistoryIcon, PlayIcon } from './icons'
import { currentVersionOf, useStudio } from './store'

const TAB_META = {
  history: { label: 'Version history', Icon: HistoryIcon },
  editor: { label: 'Editor', Icon: EditIcon },
  playground: { label: 'Playground', Icon: PlayIcon },
} as const

function App() {
  const state = useStudio()

  useEffect(() => {
    void state.init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selected = state.selected
  const versions = selected ? state.versions[selected] ?? [] : []
  const currentVersion = selected ? currentVersionOf(state, selected) : 0

  const currentVersions: Record<string, number | undefined> = {}
  for (const name of state.agents) {
    currentVersions[name] = currentVersionOf(state, name)
  }

  return (
    <div className="shell">
      <Sidebar
        agents={state.agents}
        currentVersions={currentVersions}
        selected={selected ?? ''}
        onSelect={state.selectAgent}
        onAdd={state.addAgent}
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
        </div>
      </div>
    </div>
  )
}

export default App
