import { useState, type SubmitEvent } from 'react'
import { placeOrder } from '../api/client'
import type { OrderType, Side } from '../types/api'
import { SYMBOL, USER_ID } from '../constants'

type OrderFormProps = {
  onPlaced: () => void
}

export function OrderForm({ onPlaced }: OrderFormProps) {
  const [side, setSide] = useState<Side>('BUY')
  const [type, setType] = useState<OrderType>('LIMIT')
  const [price, setPrice] = useState('100.00')
  const [quantity, setQuantity] = useState('1')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      await placeOrder({
        user_id: USER_ID,
        symbol: SYMBOL,
        side,
        type,
        price: type === 'LIMIT' ? price : undefined,
        quantity,
      })
      onPlaced()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to place order')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="order-form">
      <h2>Place order</h2>

      <form onSubmit={handleSubmit}>
        <label>
          Side
          <select value={side} onChange={(e) => setSide(e.target.value as Side)}>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </label>

        <label>
          Type
          <select value={type} onChange={(e) => setType(e.target.value as OrderType)}>
            <option value="LIMIT">LIMIT</option>
            <option value="MARKET">MARKET</option>
          </select>
        </label>

        {type === 'LIMIT' && (
          <label>
            Price
            <input value={price} onChange={(e) => setPrice(e.target.value)} />
          </label>
        )}

        <label>
          Quantity
          <input value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </label>

        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting…' : 'Submit'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}
    </section>
  )
}