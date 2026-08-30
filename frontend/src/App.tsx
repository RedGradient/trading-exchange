import { useCallback, useState } from 'react'
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
      <OrderForm onPlaced={refreshBook} />

      <div className="market-grid">
        <OrderBook symbol={SYMBOL} refreshKey={refreshKey} />
        <TradesFeed trades={trades} status={status} />
      </div>
    </main>
  )
}