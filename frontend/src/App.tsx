import './App.css'
import { OrderBook } from './components/OrderBook'
import { OrderForm } from './components/OrderForm'
import { TradesFeed } from './components/TradesFeed'
import { useTradeSocket } from './hooks/useTradeSocket'
import { SYMBOL } from './constants'

export default function App() {
  const { trades, status, book, bookError, placeOrder } = useTradeSocket(SYMBOL)

  return (
    <main className="app">
      <header className="app-header">
        <h1>Trading Exchange</h1>
        <p>{SYMBOL}</p>
      </header>

      <div className="layout-grid">
        <OrderBook book={book} error={bookError} />
        <TradesFeed trades={trades} status={status} />
        <OrderForm placeOrder={placeOrder} connected={status === 'connected'} />
      </div>
    </main>
  )
}