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
    accessToken?: string,
): Promise<OrderBookSnapshot> {
    const response = await fetch(
        `/api/order_book/${encodeURIComponent(symbol)}?depth=${depth}`,
        { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} }
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

export class AuthenticationError extends Error {}

export async function refreshAccessToken(): Promise<string> {
  const response = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'same-origin' })
  if (response.status === 401) {
    throw new AuthenticationError('Your session has expired. Sign in again.')
  }
  if (response.status === 403) throw new AuthenticationError(await readError(response))
  if (!response.ok) throw new Error(await readError(response))
  const token = await response.json()
  return token.access_token
}


export async function login(username: string, password: string): Promise<void> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw new Error(await readError(response))
}


export async function register(username: string, password: string): Promise<void> {
  const response = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw new Error(await readError(response))
}


export async function logout(): Promise<void> {
  const response = await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
  })
  if (!response.ok) throw new Error(await readError(response))
}
