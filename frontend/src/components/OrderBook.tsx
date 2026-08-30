import { useEffect, useState } from "react"
import type { OrderBookSnapshot } from "../types/api"
import { getOrderBook } from "../api/client"

type OrderBookProps = {
    symbol: string
    refreshKey?: number
}

export function OrderBook({ symbol, refreshKey = 0}: OrderBookProps) {
    const [book, setBook] = useState<OrderBookSnapshot | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false

        getOrderBook(symbol)
            .then((data) => {
                if (!cancelled) {
                    setBook(data)
                    setError(null)
                }
            })
            .catch((err: unknown) => {
                if (!cancelled) {
                    setError(err instanceof Error ? err.message : 'Failed to load order book')
                }
            })
        
        return () => {
            cancelled = true
        }
    }, [symbol, refreshKey])

    if (error) {
        return <div className="order-book error">{error}</div>
    }

    if (!book) {
        return <div className="order-book">Loading…</div>
    }

    return (
        <section className="order-book">
        <h2>Order book · {book.symbol}</h2>
        <div className="order-book-columns">
            <div className="asks">
            <h3>Asks</h3>
            <ul>
                {book.asks.length === 0 && <li>Empty</li>}
                {book.asks.map(([price, quantity]) => (
                <li key={`ask-${price}`}>
                    <span>{price}</span>
                    <span> · </span>
                    <span>{quantity}</span>
                </li>
                ))}
            </ul>
            </div>
            <div className="bids">
            <h3>Bids</h3>
            <ul>
                {book.bids.length === 0 && <li>Empty</li>}
                {book.bids.map(([price, quantity]) => (
                <li key={`bid-${price}`}>
                    <span>{price}</span>
                    <span> · </span>
                    <span>{quantity}</span>
                </li>
                ))}
            </ul>
            </div>
        </div>
        </section>
    )
}