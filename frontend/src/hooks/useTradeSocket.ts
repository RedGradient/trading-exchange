import { useEffect, useState } from "react"
import { getOrderBook } from "../api/client"
import type { OrderBookSnapshot, OrderBookSnapshotMessage, TradeSettledEvent, TradeSettledMessage } from "../types/api"

type WsStatus = 'connecting' | 'connected' | 'disconnected'

export function useTradeSocket(symbol: string) {
    const [trades, setTrades] = useState<TradeSettledEvent[]>([])
    const [book, setBook] = useState<OrderBookSnapshot | null>(null)
    const [bookError, setBookError] = useState<string | null>(null)
    const [status, setStatus] = useState<WsStatus>('connecting')

    useEffect(() => {
        let ws: WebSocket | null = null
        let reconnectTimer: number | undefined
        let unmounted = false

        let bookRequest = 0

        const loadBook = async () => {
            const request = ++bookRequest
            try {
                const snapshot = await getOrderBook(symbol)
                if (unmounted || request !== bookRequest) return
                setBook(snapshot)
                setBookError(null)
            } catch (error: unknown) {
                if (unmounted || request !== bookRequest) return
                setBookError(error instanceof Error ? error.message : 'Failed to load order book')
            }
        }

        const connect = () => {
            if (unmounted) return

            setStatus('connecting')

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

            ws.onopen = () => {
                if (unmounted) {
                    ws!.onclose = null
                    ws!.close()
                    return
                }
                setStatus('connected')
                void loadBook()
            }

            ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data) as TradeSettledMessage | OrderBookSnapshotMessage
                    if (unmounted) return

                    if (message.type === 'trade.settled' && message.payload) {
                        setTrades((prev) => [message.payload, ...prev].slice(0, 50))
                    } else if (message.type === 'order_book.snapshot' && message.payload?.symbol === symbol) {
                        // A live snapshot supersedes any pending HTTP response.
                        bookRequest++
                        setBook(message.payload)
                        setBookError(null)
                    }
                } catch {
                    // ignoring invalid messages
                }

            }

            ws.onclose = () => {
                if (unmounted) return
                bookRequest++
                setStatus('disconnected')
                reconnectTimer = window.setTimeout(connect, 2000)
            }
        }

        void loadBook()
        connect()

        return () => {
            unmounted = true
            if (reconnectTimer) window.clearTimeout(reconnectTimer)
            if (ws) {
                ws.onclose = null
                if (ws.readyState === WebSocket.OPEN) {
                    ws.close()
                }
            }
        }
    }, [symbol])

    return { trades, status, book, bookError }
}