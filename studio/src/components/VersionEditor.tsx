import { useState } from 'react'
import { ApiError } from '../api'

interface Props {
  currentVersion: number
  allTools: string[]
  onCreate: (body: {
    instructions: string
    model: string
    tools: string[]
    based_on: number
  }) => Promise<void>
}

const MODELS = ['gemini-3.5-flash-lite', 'gemini-3.8-live']

export function VersionEditor({ currentVersion, allTools, onCreate }: Props) {
  const [instructions, setInstructions] = useState('')
  const [model, setModel] = useState(MODELS[0])
  const [tools, setTools] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const toggleTool = (name: string) =>
    setTools((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name],
    )

  const submit = async () => {
    setError(null)
    setSaving(true)
    try {
      await onCreate({ instructions, model, tools, based_on: currentVersion })
      setInstructions('')
      setTools([])
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(
          'Someone else already wrote a newer version. Reload and try again.',
        )
      } else {
        setError(err instanceof Error ? err.message : 'Could not save.')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <label style={labelStyle}>Instructions</label>
        <textarea
          className="mono"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          rows={5}
          placeholder="You are a support assistant who..."
          style={textareaStyle}
        />
      </div>

      <div>
        <label style={labelStyle}>Model</label>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          style={selectStyle}
        >
          {MODELS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label style={labelStyle}>Tools</label>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {allTools.map((t) => (
            <label key={t} style={toolLabelStyle}>
              <input
                type="checkbox"
                checked={tools.includes(t)}
                onChange={() => toggleTool(t)}
              />
              <code style={{ fontSize: 12.5 }}>{t}</code>
            </label>
          ))}
        </div>
      </div>

      {error && (
        <div
          style={{
            background: 'var(--red-soft)',
            border: '1px solid var(--red-border)',
            color: 'var(--red)',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={submit}
          disabled={saving || !instructions.trim()}
          style={primaryButtonStyle}
        >
          {saving ? 'Saving…' : `Create version ${currentVersion + 1}`}
        </button>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          based on version {currentVersion}
        </span>
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

const textareaStyle: React.CSSProperties = {
  width: '100%',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '10px 12px',
  fontSize: 13.5,
  resize: 'vertical',
}

const selectStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '8px 12px',
  fontSize: 13.5,
  fontFamily: 'var(--font-mono)',
  background: 'var(--card)',
}

const toolLabelStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '6px 10px',
  cursor: 'pointer',
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
}
