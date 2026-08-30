import type { OrderBookSnapshot, OrderCreate, OrderResponse } from "../types/api"

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    return JSON.stringify(body.detail ?? body)
  } catch {
    return response.statusText || `HTTP ${response.status}`
  }
}

export async function getOrderBook(
    symbol: string,
    depth = 10,
): Promise<OrderBookSnapshot> {
    const response = await fetch(
        `/api/order_book/${encodeURIComponent(symbol)}?depth=${depth}`
    )

    if (!response.ok) {
        throw new Error(await readError(response))
    }

    return response.json()
}


export async function placeOrder(body: OrderCreate): Promise<OrderResponse> {
    const response = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })

    if (!response.ok) {
        throw new Error(await readError(response))
    }


    return response.json()
}

export async function cancelOrder(orderId: number): Promise<OrderResponse> {
  const response = await fetch(`/api/orders/${orderId}/cancel`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(await readError(response))
  }

  return response.json()
}