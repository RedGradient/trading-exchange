import { useEffect, useState } from "react"
import type { TradeSettledEvent } from "../types/api"

type WsStatus = 'connecting' | 'connected' | 'disconnected'

export function useTradeSocket(onTrade?: () => void) {
    const [trades, setTrades] = useState<TradeSettledEvent[]>([])
    const [status, setStatus] = useState<WsStatus>('connecting')

    useEffect(() => {
        let ws: WebSocket | null = null
        let reconnectTimer: number | undefined
        let unmounted = false

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
            }

            ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data)

                    if (message.type === 'trade.settled' && message.payload) {
                        setTrades((prev) => [message.payload, ...prev].slice(0, 50))
                        onTrade?.()
                    }
                } catch {
                    // ignoring invalid messages
                }

            }

            ws.onclose = () => {
                if (unmounted) return
                setStatus('disconnected')
                reconnectTimer = window.setTimeout(connect, 2000)
            }
        }

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
    }, [onTrade])

    return { trades, status }
}