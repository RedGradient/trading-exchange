import { useCallback, useEffect, useRef, useState } from "react"
import { getOrderBook } from "../api/client"
import type { OrderBookSnapshot, OrderBookSnapshotMessage, OrderCreate, OrderPlaceMessage, OrderPlacedMessage, OrderResponse, TradeSettledEvent, TradeSettledMessage, WsErrorMessage } from "../types/api"

type PendingOrder = {
    resolve: (order: OrderResponse) => void
    reject: (error: Error) => void
    timer: number
}

const ORDER_RESPONSE_TIMEOUT_MS = 15000

type WsStatus = 'connecting' | 'connected' | 'disconnected'

export function useTradeSocket(symbol: string) {
    const [trades, setTrades] = useState<TradeSettledEvent[]>([])
    const [book, setBook] = useState<OrderBookSnapshot | null>(null)
    const [bookError, setBookError] = useState<string | null>(null)
    const [status, setStatus] = useState<WsStatus>('connecting')

    const socketRef = useRef<WebSocket | null>(null)
    const pendingOrders = useRef(new Map<string, PendingOrder>())

    const placeOrder = useCallback((payload: OrderCreate): Promise<OrderResponse> => {
        const socket = socketRef.current
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            return Promise.reject(new Error('WebSocket is disconnected. Wait for reconnection.'))
        }

        const id = crypto.randomUUID()
        const message: OrderPlaceMessage = { type: 'order.place', id, payload }
        return new Promise((resolve, reject) => {
            const timer = window.setTimeout(() => {
                pendingOrders.current.delete(id)
                reject(new Error('Order confirmation timed out. The order may have been placed. Check its status before retrying.'))
            }, ORDER_RESPONSE_TIMEOUT_MS)
            pendingOrders.current.set(id, { resolve, reject, timer })
            try {
                socket.send(JSON.stringify(message))
            } catch (error: unknown) {
                window.clearTimeout(timer)
                pendingOrders.current.delete(id)
                reject(error instanceof Error ? error : new Error('Failed to send order'))
            }
        })
    }, [])

    useEffect(() => {
        const requests = pendingOrders.current
        const rejectPendingOrders = () => {
            for (const request of requests.values()) {
                window.clearTimeout(request.timer)
                request.reject(new Error('Connection closed before order confirmation. The order may have been placed. Check its status before retrying.'))
            }
            requests.clear()
        }
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

            socketRef.current = ws

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
                    const message = JSON.parse(event.data) as TradeSettledMessage | OrderBookSnapshotMessage | OrderPlacedMessage | WsErrorMessage
                    if (unmounted) return

                    if ((message.type === 'order.placed' || message.type === 'error') && message.id) {
                        const request = requests.get(message.id)
                        if (!request) return
                        window.clearTimeout(request.timer)
                        requests.delete(message.id)
                        if (message.type === 'error') {
                            request.reject(new Error(message.detail))
                        } else {
                            request.resolve(message.payload)
                        }
                    } else if (message.type === 'trade.settled' && message.payload) {
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
                socketRef.current = null
                rejectPendingOrders()
                bookRequest++
                setStatus('disconnected')
                reconnectTimer = window.setTimeout(connect, 2000)
            }
        }

        void loadBook()
        connect()

        return () => {
            unmounted = true
            socketRef.current = null
            rejectPendingOrders()
            if (reconnectTimer) window.clearTimeout(reconnectTimer)
            if (ws) {
                ws.onclose = null
                if (ws.readyState === WebSocket.OPEN) {
                    ws.close()
                }
            }
        }
    }, [symbol])

    return { trades, status, book, bookError, placeOrder }
}