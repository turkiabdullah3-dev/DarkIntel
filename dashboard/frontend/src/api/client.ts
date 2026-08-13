import type { ApiError } from '../types'

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) } })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: { message: 'Dashboard request failed.' } })) as ApiError
    throw new Error(body.error?.message ?? 'Dashboard request failed.')
  }
  return response.json() as Promise<T>
}

export const query = (params: Record<string, string | number | boolean | undefined>) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => value !== undefined && value !== '' && search.set(key, String(value)))
  const rendered = search.toString()
  return rendered ? `?${rendered}` : ''
}
