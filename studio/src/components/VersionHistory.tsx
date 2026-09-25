import type { AgentVersion } from '../api'

interface Props {
  versions: AgentVersion[]
  loading: boolean
}

export function VersionHistory({ versions, loading }: Props) {
  if (loading) return <div className="empty-state">Loading versions…</div>
  if (versions.length === 0) {
    return (
      <div className="empty-state">
        No versions yet. Create the first one in the Editor tab.
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {[...versions].reverse().map((v, i) => (
        <div className="card" key={v.version}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <strong style={{ fontSize: 14 }}>version {v.version}</strong>
              {i === 0 && (
                <span
                  style={{
                    fontSize: 11,
                    padding: '1px 8px',
                    borderRadius: 999,
                    background: 'var(--brand-soft)',
                    color: 'var(--brand-dark)',
                    fontWeight: 600,
                  }}
                >
                  current
                </span>
              )}
            </div>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              {new Date(v.created_at * 1000).toLocaleString()}
            </span>
          </div>
          <p
            style={{
              fontSize: 13.5,
              color: 'var(--text-primary)',
              margin: '10px 0',
              lineHeight: 1.5,
            }}
          >
            {v.instructions}
          </p>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11.5,
                padding: '2px 8px',
                borderRadius: 999,
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                color: 'var(--text-secondary)',
              }}
            >
              {v.model}
            </span>
            {v.tools.map((t) => (
              <span
                key={t}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11.5,
                  padding: '2px 8px',
                  borderRadius: 999,
                  background: 'var(--green-soft)',
                  border: '1px solid var(--green-border)',
                  color: 'var(--green)',
                }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
