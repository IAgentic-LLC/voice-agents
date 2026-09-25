import { useState } from 'react'
import type { AgentVersion, Deployment } from '../api'

interface Props {
  versions: AgentVersion[]
  deployment: Deployment | null
  error: string | null
  onDeploy: (body: {
    stable_version: number
    canary_version: number | null
    canary_percent: number
  }) => Promise<void>
  onRollback: () => Promise<void>
}

export function Deploy({ versions, deployment, error, onDeploy, onRollback }: Props) {
  const [stable, setStable] = useState<number | null>(null)
  const [canary, setCanary] = useState<string>('none')
  const [percent, setPercent] = useState(20)
  const [busy, setBusy] = useState(false)

  if (versions.length === 0) {
    return (
      <div className="empty-state">
        No versions yet. Create one in the Editor tab before deploying.
      </div>
    )
  }

  const stableVersion = stable ?? deployment?.stable_version ?? versions[versions.length - 1].version
  const canaryOptions = versions.filter((v) => v.version !== stableVersion)

  const submit = async () => {
    setBusy(true)
    try {
      await onDeploy({
        stable_version: stableVersion,
        canary_version: canary === 'none' ? null : Number(canary),
        canary_percent: canary === 'none' ? 0 : percent,
      })
      setCanary('none')
    } catch {
      // error is already surfaced from the store's own deployError
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card">
        <div style={labelStyle}>Current deployment</div>
        {deployment === null ? (
          <p style={{ fontSize: 13.5, margin: '6px 0 0' }}>
            Nothing deployed. The worker falls back to the latest version.
          </p>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
            <span style={pillStyle('green')}>stable v{deployment.stable_version}</span>
            {deployment.canary_version !== null && (
              <>
                <span style={pillStyle('amber')}>
                  canary v{deployment.canary_version} · {deployment.canary_percent}%
                </span>
                <button onClick={() => void onRollback()} style={rollbackButtonStyle}>
                  Reject canary, roll back
                </button>
              </>
            )}
          </div>
        )}
      </div>

      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <label style={labelStyle}>Stable version</label>
          <select
            value={stableVersion}
            onChange={(e) => setStable(Number(e.target.value))}
            style={selectStyle}
          >
            {versions.map((v) => (
              <option key={v.version} value={v.version}>
                version {v.version}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={labelStyle}>Canary version</label>
          <select value={canary} onChange={(e) => setCanary(e.target.value)} style={selectStyle}>
            <option value="none">none</option>
            {canaryOptions.map((v) => (
              <option key={v.version} value={v.version}>
                version {v.version}
              </option>
            ))}
          </select>
        </div>

        {canary !== 'none' && (
          <div>
            <label style={labelStyle}>Canary traffic: {percent}%</label>
            <input
              type="range"
              min={1}
              max={99}
              value={percent}
              onChange={(e) => setPercent(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
        )}

        {error && (
          <div style={errorStyle}>{error}</div>
        )}

        <button onClick={submit} disabled={busy} style={primaryButtonStyle}>
          {busy ? 'Deploying…' : 'Deploy'}
        </button>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 12.5,
  fontWeight: 600,
  color: 'var(--text-secondary)',
  marginBottom: 6,
}

const selectStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '8px 12px',
  fontSize: 13.5,
  fontFamily: 'var(--font-mono)',
  background: 'var(--card)',
}

const errorStyle: React.CSSProperties = {
  background: 'var(--red-soft)',
  border: '1px solid var(--red-border)',
  color: 'var(--red)',
  borderRadius: 8,
  padding: '8px 12px',
  fontSize: 13,
}

const primaryButtonStyle: React.CSSProperties = {
  background: 'var(--brand)',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  padding: '9px 16px',
  fontSize: 13.5,
  fontWeight: 600,
  cursor: 'pointer',
  alignSelf: 'flex-start',
}

function pillStyle(color: 'green' | 'amber'): React.CSSProperties {
  return {
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    padding: '3px 10px',
    borderRadius: 999,
    background: `var(--${color}-soft)`,
    border: `1px solid ${color === 'green' ? 'var(--green-border)' : 'var(--amber)'}`,
    color: `var(--${color})`,
  }
}

const rollbackButtonStyle: React.CSSProperties = {
  background: 'var(--red-soft)',
  color: 'var(--red)',
  border: '1px solid var(--red-border)',
  borderRadius: 8,
  padding: '6px 12px',
  fontSize: 12.5,
  fontWeight: 600,
  cursor: 'pointer',
}
