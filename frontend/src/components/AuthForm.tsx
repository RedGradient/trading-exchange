import { useEffect, useRef, useState, type SubmitEvent } from 'react'
import { login, register } from '../api/client'

type AuthFormProps = {
  mode: 'login' | 'register'
  onClose: () => void
  onSwitchMode: () => void
  onAuthenticated: () => void
}

export function AuthForm({ mode, onAuthenticated, onClose, onSwitchMode }: AuthFormProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [registered, setRegistered] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const registering = mode === 'register'

  useEffect(() => {
    const dialog = dialogRef.current
    dialog?.showModal()
    return () => dialog?.close()
  }, [])

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault()
    if (submitting) return
    setError(null)
    setSubmitting(true)
    try {
      if (registering && !registered) {
        await register(username, password)
        setRegistered(true)
      }
      await login(username, password)
      setPassword('')
      onAuthenticated()
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : 'Failed to sign in')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <dialog ref={dialogRef} className="auth-dialog" onCancel={onClose} aria-labelledby="auth-title">
      <section className="auth-form panel">
        <button className="auth-close" type="button" onClick={onClose} aria-label="Close authentication form">Close</button>
        <h2 id="auth-title">{registering && !registered ? 'Create account' : 'Sign in'}</h2>
        <p>{registered ? 'Account created. Sign in to start trading.' : 'Sign in or create an account to start trading.'}</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="login-username">Username</label>
          <input
            id="login-username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            minLength={3}
            maxLength={64}
            required
            disabled={submitting || registered}
          />
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete={registering && !registered ? 'new-password' : 'current-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            maxLength={128}
            required
            disabled={submitting}
          />
          <button type="submit" disabled={submitting}>
            {submitting ? 'Please wait…' : registering && !registered ? 'Create account' : 'Sign in'}
          </button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="auth-switch" type="button" onClick={onSwitchMode} disabled={submitting}>
          {registering ? 'Already have an account? Sign in' : 'New here? Create an account'}
        </button>
      </section>
    </dialog>
  )
}
