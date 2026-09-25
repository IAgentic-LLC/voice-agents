import { useAuth0 } from '@auth0/auth0-react'
import { useEffect, useState } from 'react'
import { useStudio } from '../store'

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { isLoading, isAuthenticated, loginWithRedirect, getAccessTokenSilently, error } =
    useAuth0()
  const [ready, setReady] = useState(false)
  const setToken = useStudio((s) => s.setToken)

  useEffect(() => {
    if (!isAuthenticated) return
    let cancelled = false
    void getAccessTokenSilently().then((token) => {
      if (cancelled) return
      void setToken(token).then(() => setReady(true))
    })
    return () => {
      cancelled = true
    }
  }, [isAuthenticated, getAccessTokenSilently, setToken])

  if (isLoading) {
    return <div className="auth-screen">Loading…</div>
  }

  if (error) {
    return <div className="auth-screen">Sign-in failed: {error.message}</div>
  }

  if (!isAuthenticated) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <div className="brand-mark" style={{ margin: '0 auto 16px' }} />
          <h1>Voice Agent Studio</h1>
          <p>Sign in to manage your organization's agents.</p>
          <button className="auth-button" onClick={() => void loginWithRedirect()}>
            Log in
          </button>
        </div>
      </div>
    )
  }

  if (!ready) {
    return <div className="auth-screen">Signing in…</div>
  }

  return <>{children}</>
}
