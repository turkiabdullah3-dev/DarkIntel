import { useCallback, useEffect, useState } from 'react'

export function useApi<T>(loader: () => Promise<T>, dependencies: readonly unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const refresh = useCallback(() => {
    setLoading(true); setError(null)
    loader().then(setData).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Request failed'))
      .finally(() => setLoading(false))
  }, dependencies) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(refresh, [refresh])
  return { data, error, loading, refresh }
}
