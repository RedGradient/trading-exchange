import { useState } from 'react'
import './App.css'
import { AuthForm } from './components/AuthForm'
import { OrderBook } from './components/OrderBook'
import { OrderForm } from './components/OrderForm'
import { TradesFeed } from './components/TradesFeed'
import { useTradeSocket } from './hooks/useTradeSocket'
import { SYMBOL } from './constants'

export default function App() {
  const [authMode, setAuthMode] = useState<'login' | 'register' | null>(null)
  const [sessionVersion, setSessionVersion] = useState(0)
  const { trades, status, book, bookError, placeOrder, requiresLogin } = useTradeSocket(SYMBOL, sessionVersion)

  return (
    <main className="app">
      <header className="app-header">
        <div>
          <h1>Trading Exchange</h1>
          <p>{SYMBOL}</p>
        </div>
        {requiresLogin && <button className="auth-open" type="button" onClick={() => setAuthMode('login')}>Sign in / Register</button>}
      </header>

      {requiresLogin && (
        <p className="auth-notice" role="status">
          Register an account or sign in to place orders and trade.
        </p>
      )}
      <div className="layout-grid">
        <OrderBook book={book} error={bookError} />
        {!requiresLogin && <TradesFeed trades={trades} status={status} />}
        {!requiresLogin && <OrderForm placeOrder={placeOrder} connected={status === 'connected'} />}
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