import { useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import type { AuditLogEntry } from '@/types/api'

export function useAuditLogs() {
  return useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => apiClient.get<AuditLogEntry[]>('/api/v1/audit-logs'),
  })
}
