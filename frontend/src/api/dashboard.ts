import { useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import type { DashboardOverview } from '@/types/api'

export function useDashboardOverview() {
  return useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: () => apiClient.get<DashboardOverview>('/api/v1/dashboard/overview'),
    refetchInterval: 30_000,
  })
}
