import { useQuery } from '@tanstack/react-query'

import { apiClient, buildQueryString } from '@/lib/api-client'
import type { PaginatedAuditLogs } from '@/types/api'

interface AuditLogListParams {
  q?: string
  limit?: number
  offset?: number
}

export function useAuditLogs(params: AuditLogListParams = {}) {
  return useQuery({
    queryKey: ['audit-logs', params],
    queryFn: () => apiClient.get<PaginatedAuditLogs>(`/api/v1/audit-logs${buildQueryString({ ...params })}`),
  })
}
