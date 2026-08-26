import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient, buildQueryString } from '@/lib/api-client'
import type { ScanRecord } from '@/types/api'

export function useScans(endpointId?: string) {
  return useQuery({
    queryKey: ['scans', endpointId],
    queryFn: () =>
      apiClient.get<ScanRecord[]>(`/api/v1/scans${buildQueryString({ endpoint_id: endpointId })}`),
    refetchInterval: 15_000,
  })
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
