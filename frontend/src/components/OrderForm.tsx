import { useState, type SubmitEvent } from 'react'
import { placeOrder } from '../api/client'
import type { OrderType, Side } from '../types/api'
import { SYMBOL, USER_ID } from '../constants'

const PRICE_STEP = 1
const QUANTITY_STEP = 1

function parseNumber(value: string): number {
  const n = parseFloat(value)
  return Number.isFinite(n) ? n : 0
}

function formatPrice(value: number): string {
  return Math.max(0, value).toFixed(2)
}

function formatQuantity(value: number): string {
  return String(Math.max(0, Math.round(value)))
}

function handleNumericChange(value: string, setValue: (next: string) => void) {
  if (value === '') {
    setValue('')
    return
  }

  if (!/^\d*\.?\d*$/.test(value)) {
    return
  }

  const parsed = parseFloat(value)
  if (value !== '.' && Number.isNaN(parsed)) {
    return
  }

  if (!Number.isNaN(parsed) && parsed < 0) {
    return
  }

  setValue(value)
}

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

  const priceValue = parseNumber(price)
  const quantityValue = parseNumber(quantity)
  const canDecreasePrice = priceValue > 0
  const canDecreaseQuantity = quantityValue > 0

  function handlePriceChange(value: string) {
    handleNumericChange(value, setPrice)
  }

  function handlePriceBlur() {
    setPrice(formatPrice(parseNumber(price)))
  }

  function adjustPrice(delta: number) {
    setPrice(formatPrice(priceValue + delta * PRICE_STEP))
  }

  function handleQuantityChange(value: string) {
    handleNumericChange(value, setQuantity)
  }

  function handleQuantityBlur() {
    setQuantity(formatQuantity(parseNumber(quantity)))
  }

  function adjustQuantity(delta: number) {
    setQuantity(formatQuantity(quantityValue + delta * QUANTITY_STEP))
  }

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
        price: type === 'LIMIT' ? formatPrice(parseNumber(price)) : undefined,
        quantity: formatQuantity(parseNumber(quantity)),
      })
      onPlaced()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to place order')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="order-form panel">
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
            <div className="spin-input">
              <input
                inputMode="decimal"
                value={price}
                onChange={(e) => handlePriceChange(e.target.value)}
                onBlur={handlePriceBlur}
              />
              <div className="spin-input__stepper">
                <button
                  type="button"
                  className="spin-input__step"
                  onClick={() => adjustPrice(1)}
                  aria-label="Increase price"
                >
                  ▲
                </button>
                <button
                  type="button"
                  className="spin-input__step"
                  onClick={() => adjustPrice(-1)}
                  disabled={!canDecreasePrice}
                  aria-label="Decrease price"
                >
                  ▼
                </button>
              </div>
            </div>
          </label>
        )}

        <label>
          Quantity
          <div className="spin-input">
            <input
              inputMode="numeric"
              value={quantity}
              onChange={(e) => handleQuantityChange(e.target.value)}
              onBlur={handleQuantityBlur}
            />
            <div className="spin-input__stepper">
              <button
                type="button"
                className="spin-input__step"
                onClick={() => adjustQuantity(1)}
                aria-label="Increase quantity"
              >
                ▲
              </button>
              <button
                type="button"
                className="spin-input__step"
                onClick={() => adjustQuantity(-1)}
                disabled={!canDecreaseQuantity}
                aria-label="Decrease quantity"
              >
                ▼
              </button>
            </div>
          </div>
        </label>

        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting…' : 'Submit'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}
    </section>
  )
}