interface OrgOption {
  org_id: string
  role: string
}

interface Props {
  agents: string[]
  currentVersions: Record<string, number | undefined>
  selected: string
  onSelect: (name: string) => void
  onAdd: (name: string) => void
  myOrgs: OrgOption[]
  org: string
  onSelectOrg: (orgId: string) => void
  onCreateOrg: (orgId: string, name: string) => void
  onLogout: () => void
}

export function Sidebar({
  agents, currentVersions, selected, onSelect, onAdd,
  myOrgs, org, onSelectOrg, onCreateOrg, onLogout,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark" />
        <span className="brand-name">Voice Agent Studio</span>
      </div>

      <div className="org-switcher">
        <select
          value={org}
          onChange={(e) => {
            if (e.target.value === '__new__') {
              const orgId = window.prompt('New organization id (e.g. acme)')
              if (!orgId) return
              const name = window.prompt('Organization name', orgId) ?? orgId
              onCreateOrg(orgId.trim(), name.trim())
            } else {
              onSelectOrg(e.target.value)
            }
          }}
        >
          {myOrgs.map((o) => (
            <option key={o.org_id} value={o.org_id}>
              {o.org_id} ({o.role})
            </option>
          ))}
          <option value="__new__">+ New organization…</option>
        </select>
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
        <button className="new-agent-button" onClick={onLogout} style={{ marginTop: 0 }}>
          Log out
        </button>
      </div>
    </aside>
  )
}
