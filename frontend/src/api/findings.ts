import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient, buildQueryString } from '@/lib/api-client'
import type { FindingListFilters, FindingRecord, FindingStatus, PaginatedFindings } from '@/types/api'

export function useFindings(filters: FindingListFilters) {
  return useQuery({
    queryKey: ['findings', filters],
    queryFn: () =>
      apiClient.get<PaginatedFindings>(
        `/api/v1/findings${buildQueryString({ ...filters, is_secret: filters.is_secret })}`,
      ),
  })
}

export function useFinding(findingId: string | undefined) {
  return useQuery({
    queryKey: ['findings', 'detail', findingId],
    queryFn: () => apiClient.get<FindingRecord>(`/api/v1/findings/${findingId}`),
    enabled: Boolean(findingId),
  })
}

export function useUpdateFindingStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ findingId, status }: { findingId: string; status: FindingStatus }) =>
      apiClient.patch<FindingRecord>(`/api/v1/findings/${findingId}`, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['findings'] })
    },
  })
}
