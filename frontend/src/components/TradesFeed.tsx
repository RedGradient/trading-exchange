import type { TradeSettledEvent } from '../types/api'
import { formatDecimal } from '../utils/format'

type TradesFeedProps = {
  trades: TradeSettledEvent[]
  status: 'connecting' | 'connected' | 'disconnected'
}

export function TradesFeed({ trades, status }: TradesFeedProps) {
  return (
    <section className="trades-feed panel">
      <h2>
        Recent trades
        <span className={`ws-status ws-status--${status}`}> · {status}</span>
      </h2>

      <div className="trades-feed-table">
        <div className="trades-feed-header">
          <span>Symbol</span>
          <span>Side</span>
          <span>Size</span>
          <span>Price</span>
        </div>

        <ul>
          {trades.length === 0 && <li className="empty">No trades yet</li>}
          {trades.map((trade) => (
            <li key={trade.dedup}>
              <span>{trade.symbol}</span>
              <span className={`trades-feed-side trades-feed-side--${trade.aggressor_side.toLowerCase()}`}>
                {trade.aggressor_side}
              </span>
              <span>{trade.quantity}</span>
              <span>{formatDecimal(trade.price)}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}