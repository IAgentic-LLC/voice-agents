import { useState } from 'react'
import type { DialResult, PlaygroundResult } from '../api'

interface Props {
  onRun: (questionAudio: string) => void
  running: boolean
  result: PlaygroundResult | null
  error: string | null
  hasVersion: boolean
  onDial: (number: string) => void
  dialRunning: boolean
  dialResult: DialResult | null
  dialError: string | null
}

const QUESTIONS = [
  { label: 'Book a callback', file: 'audio/ch09/plain.wav' },
  { label: 'Ask for a refund', file: 'audio/ch20_refund_ask.wav' },
]

export function Playground({
  onRun, running, result, error, hasVersion,
  onDial, dialRunning, dialResult, dialError,
}: Props) {
  const [question, setQuestion] = useState(QUESTIONS[0].file)
  const [number, setNumber] = useState('')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
          Places a real live call against the current version, through a
          worker that is already running for this agent.
        </p>

        <select
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          style={{
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: 13.5,
          }}
        >
          {QUESTIONS.map((q) => (
            <option key={q.file} value={q.file}>
              {q.label}
            </option>
          ))}
        </select>

        <button
          onClick={() => onRun(question)}
          disabled={running || !hasVersion}
          style={primaryButtonStyle}
        >
          {running ? 'Calling…' : 'Run call'}
        </button>

        {!hasVersion && (
          <p style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>
            Create a version first, in the Editor tab.
          </p>
        )}

        {error && <div style={errorStyle}>{error}</div>}

        {result && (
          <div
            style={{
              background: result.ok ? 'var(--green-soft)' : 'var(--amber-soft)',
              border: `1px solid ${result.ok ? 'var(--green-border)' : 'var(--amber)'}`,
              borderRadius: 8,
              padding: '12px 14px',
              fontSize: 13,
              fontFamily: 'var(--font-mono)',
            }}
          >
            <div>room: {result.room}</div>
            <div>ok: {String(result.ok)}</div>
            {result.join_s !== null && <div>join_s: {result.join_s}</div>}
            {result.ttfa_s !== null && <div>ttfa_s: {result.ttfa_s}</div>}
            {result.error && <div>error: {result.error}</div>}
          </div>
        )}
      </div>

      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
          Places a real outbound call, through the self-hosted server,
          to a real phone. This rings an actual number.
        </p>

        <input
          type="tel"
          value={number}
          onChange={(e) => setNumber(e.target.value)}
          placeholder="+49..."
          style={{
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: 13.5,
            fontFamily: 'var(--font-mono)',
          }}
        />

        <button
          onClick={() => onDial(number)}
          disabled={dialRunning || !hasVersion || !number.trim()}
          style={{ ...primaryButtonStyle, background: 'var(--red)' }}
        >
          {dialRunning ? 'Dialing…' : 'Call this real number'}
        </button>

        {dialError && <div style={errorStyle}>{dialError}</div>}

        {dialResult && (
          <div
            style={{
              background: dialResult.ok ? 'var(--green-soft)' : 'var(--amber-soft)',
              border: `1px solid ${dialResult.ok ? 'var(--green-border)' : 'var(--amber)'}`,
              borderRadius: 8,
              padding: '12px 14px',
              fontSize: 13,
              fontFamily: 'var(--font-mono)',
            }}
          >
            <div>room: {dialResult.room}</div>
            <div>ok: {String(dialResult.ok)}</div>
            {dialResult.call_id && <div>call_id: {dialResult.call_id}</div>}
            {dialResult.error && <div>error: {dialResult.error}</div>}
          </div>
        )}
      </div>
    </div>
  )
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

const errorStyle: React.CSSProperties = {
  background: 'var(--red-soft)',
  border: '1px solid var(--red-border)',
  color: 'var(--red)',
  borderRadius: 8,
  padding: '8px 12px',
  fontSize: 13,
}
