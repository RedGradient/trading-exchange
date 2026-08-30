import type { TradeSettledEvent } from '../types/api'

type TradesFeedProps = {
  trades: TradeSettledEvent[]
  status: 'connecting' | 'connected' | 'disconnected'
}

export function TradesFeed({ trades, status }: TradesFeedProps) {
  return (
    <section className="trades-feed">
      <h2>
        Recent trades
        <span className={`ws-status ws-status--${status}`}> · {status}</span>
      </h2>

      <ul>
        {trades.length === 0 && <li>No trades yet</li>}
        {trades.map((trade) => (
          <li key={trade.dedup}>
            <span>{trade.symbol}</span>
            <span> · </span>
            <span>{trade.aggressor_side}</span>
            <span> · </span>
            <span>{trade.quantity} @ {trade.price}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}