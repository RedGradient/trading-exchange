import { useEffect, useState } from "react"
import type { OrderBookSnapshot } from "../types/api"
import { getOrderBook } from "../api/client"
import { formatDecimal } from "../utils/format"

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
        return <div className="order-book panel error">{error}</div>
    }

    if (!book) {
        return <div className="order-book panel loading">Loading…</div>
    }

    const askLevels = [...book.asks].reverse()
    const isEmpty = book.asks.length === 0 && book.bids.length === 0

    return (
        <section className="order-book panel">
            <h2>Order book</h2>
            <div className="order-book-table">
                <div className="order-book-header">
                    <span>Price</span>
                    <span>Size</span>
                </div>

                {isEmpty ? (
                    <div className="order-book-body">
                        <div className="order-book-row order-book-row--empty">
                            <span>Empty</span>
                        </div>
                    </div>
                ) : (
                    <div className="order-book-body">
                        <div className="order-book-spacer" aria-hidden="true" />
                        <div className="order-book-asks">
                            {askLevels.map(([price, quantity], index) => {
                                const isBestAsk = index === askLevels.length - 1
                                return (
                                    <div
                                        className={`order-book-row order-book-row--ask${
                                            book.bids.length > 0 && isBestAsk
                                                ? ' order-book-row--spread'
                                                : ''
                                        }${isBestAsk ? ' order-book-row--best-ask' : ''}`}
                                        key={`ask-${price}`}
                                    >
                                        <span>{formatDecimal(price)}</span>
                                        <span>{quantity}</span>
                                    </div>
                                )
                            })}
                        </div>
                        <div className="order-book-bids">
                            {book.bids.map(([price, quantity], index) => (
                                <div
                                    className={`order-book-row order-book-row--bid${
                                        index === 0 ? ' order-book-row--best-bid' : ''
                                    }`}
                                    key={`bid-${price}`}
                                >
                                    <span>{formatDecimal(price)}</span>
                                    <span>{quantity}</span>
                                </div>
                            ))}
                        </div>
                        <div className="order-book-spacer" aria-hidden="true" />
                    </div>
                )}
            </div>
        </section>
    )
}
