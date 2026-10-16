import { useQuery } from '@tanstack/react-query'

import { api } from './client'

export type ServerStatus =
  { state: 'ok'; version: string } | { state: 'degraded'; version: string } | { state: 'offline' }

export async function fetchServerStatus(): Promise<ServerStatus> {
  try {
    const { data, error } = await api.GET('/api/health')
    if (data) {
      return { state: 'ok', version: data.version }
    }
    if (error && 'version' in error) {
      return { state: 'degraded', version: error.version }
    }
    return { state: 'offline' }
  } catch {
    return { state: 'offline' }
  }
}

export function useServerStatus() {
  return useQuery({
    queryKey: ['server-status'],
    queryFn: fetchServerStatus,
    refetchInterval: 60_000,
  })
}
