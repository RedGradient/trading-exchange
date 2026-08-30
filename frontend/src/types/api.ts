export type Side = 'BUY' | 'SELL'

export type OrderType = 'LIMIT' | 'MARKET'

export type OrderStatus = 
    | 'OPEN'
    | 'PARTIALLY_FILLED'
    | 'FILLED'
    | 'CANCELLED'
    | 'REJECTED'

export type OrderCreate = {
    user_id: number
    symbol: string
    side: Side
    type: OrderType
    price?: string | null
    quantity: string
}

export type OrderResponse = {
  id: number
  user_id: number
  symbol: string
  side: Side
  type: OrderType
  price: string | null
  quantity: string
  remaining: string
  status: OrderStatus
  sequence: number
  created_at: string
}

export type OrderBookSnapshot = {
    symbol: string,
    asks: [string, string][],
    bids: [string, string][],
}

export type TradeSettledEvent = {
  event_type: 'trade.settled'
  trade_id: number
  dedup: string
  symbol: string
  price: string
  quantity: string
  maker_order_id: number
  taker_order_id: number
  aggressor_side: Side
  sequence: number
  created_at: string
}

export type TradeSettledMessage = {
  type: 'trade.settled'
  payload: TradeSettledEvent
}