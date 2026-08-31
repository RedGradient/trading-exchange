import { useCallback, useState } from 'react'
import './App.css'
import { OrderBook } from './components/OrderBook'
import { OrderForm } from './components/OrderForm'
import { TradesFeed } from './components/TradesFeed'
import { useTradeSocket } from './hooks/useTradeSocket'
import { SYMBOL } from './constants'

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0)

  const refreshBook = useCallback(() => {
    setRefreshKey((k) => k + 1)
  }, [])

  const { trades, status } = useTradeSocket(refreshBook)

  return (
    <main className="app">
      <header className="app-header">
        <h1>Trading Exchange</h1>
        <p>{SYMBOL}</p>
      </header>

      <div className="layout-grid">
        <OrderBook symbol={SYMBOL} refreshKey={refreshKey} />
        <TradesFeed trades={trades} status={status} />
        <OrderForm onPlaced={refreshBook} />
      </div>
    </main>
  )
}