import { useState } from 'react'
import './App.css'
import { logout } from './api/client'
import { AuthForm } from './components/AuthForm'
import { OrderBook } from './components/OrderBook'
import { OrderForm } from './components/OrderForm'
import { TradesFeed } from './components/TradesFeed'
import { useTradeSocket } from './hooks/useTradeSocket'
import { SYMBOL } from './constants'

export default function App() {
  const [authMode, setAuthMode] = useState<'login' | 'register' | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const [sessionVersion, setSessionVersion] = useState(0)
  const { trades, status, book, bookError, placeOrder, requiresLogin } = useTradeSocket(SYMBOL, sessionVersion)

  async function handleLogout() {
    if (loggingOut) return
    setLoggingOut(true)
    setLogoutError(null)
    try {
      await logout()
      setAuthMode(null)
      setSessionVersion((version) => version + 1)
    } catch (error: unknown) {
      setLogoutError(error instanceof Error ? error.message : 'Failed to sign out')
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <main className="app">
      <header className="app-header">
        <div>
          <h1>Trading Exchange</h1>
          <p>{SYMBOL}</p>
        </div>
        {requiresLogin ? (
          <button className="auth-open" type="button" onClick={() => setAuthMode('login')}>Sign in / Register</button>
        ) : (
          <button className="auth-open" type="button" onClick={handleLogout} disabled={loggingOut}>
            {loggingOut ? 'Signing out…' : 'Sign out'}
          </button>
        )}
      </header>

      {logoutError && <p className="error" role="alert">{logoutError}</p>}
      {requiresLogin && (
        <p className="auth-notice" role="status">
          Register an account or sign in to place orders and trade.
        </p>
      )}
      <div className="layout-grid">
        <OrderBook book={book} error={bookError} />
        {!requiresLogin && <TradesFeed trades={trades} status={status} />}
        {!requiresLogin && <OrderForm placeOrder={placeOrder} connected={status === 'connected' && !loggingOut} />}
      </div>
      {authMode && (
        <AuthForm
          key={authMode}
          mode={authMode}
          onClose={() => setAuthMode(null)}
          onSwitchMode={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
          onAuthenticated={() => {
            setAuthMode(null)
            setSessionVersion((version) => version + 1)
          }}
        />
      )}
    </main>
  )
}