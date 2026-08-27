import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient, buildQueryString } from '@/lib/api-client'
import type { PaginatedScans, ScanRecord } from '@/types/api'

interface ScanListParams {
  endpoint_id?: string
  q?: string
  limit?: number
  offset?: number
}

export function useScans(params: ScanListParams = {}) {
  return useQuery({
    queryKey: ['scans', params],
    queryFn: () => apiClient.get<PaginatedScans>(`/api/v1/scans${buildQueryString({ ...params })}`),
    refetchInterval: 15_000,
  })
}

/** For pages that just need "all recent scans" for a lookup/summary, not a
 * paginated table (Reports page's scan-to-report-from list). */
export function useAllScans() {
  return useScans({ limit: 500 })
}

export function useScan(scanId: string | undefined) {
  return useQuery({
    queryKey: ['scans', 'detail', scanId],
    queryFn: () => apiClient.get<ScanRecord>(`/api/v1/scans/${scanId}`),
    enabled: Boolean(scanId),
  })
}

export function useCancelScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (scanId: string) => apiClient.post<ScanRecord>(`/api/v1/scans/${scanId}/cancel`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scans'] })
    },
  })
}
