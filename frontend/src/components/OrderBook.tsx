import type { OrderBookSnapshot } from "../types/api"
import { formatDecimal } from "../utils/format"

type OrderBookProps = {
    book: OrderBookSnapshot | null
    error: string | null
}

export function OrderBook({ book, error }: OrderBookProps) {
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
