interface Props {
  agents: string[]
  currentVersions: Record<string, number | undefined>
  selected: string
  onSelect: (name: string) => void
  onAdd: (name: string) => void
}

export function Sidebar({ agents, currentVersions, selected, onSelect, onAdd }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark" />
        <span className="brand-name">Voice Agent Studio</span>
      </div>
      <div className="sidebar-label">Agents</div>
      <ul className="agent-list">
        {agents.map((name) => {
          const version = currentVersions[name]
          return (
            <li key={name}>
              <button
                className={`agent-item ${name === selected ? 'active' : ''}`}
                onClick={() => onSelect(name)}
              >
                <span className="agent-item-name">
                  <span
                    className="agent-dot"
                    style={{ background: version ? 'var(--green)' : 'var(--ink-500)' }}
                  />
                  {name}
                </span>
                {version !== undefined && <span className="badge">v{version}</span>}
              </button>
            </li>
          )
        })}
      </ul>
      <button
        className="new-agent-button"
        onClick={() => {
          const name = window.prompt('New agent name')
          if (name) onAdd(name.trim())
        }}
      >
        <span style={{ fontSize: 15, lineHeight: 1 }}>+</span> New agent
      </button>
      <div className="sidebar-footer">
        Chapter 32 &middot; backed by the real runtime
      </div>
    </aside>
  )
}
