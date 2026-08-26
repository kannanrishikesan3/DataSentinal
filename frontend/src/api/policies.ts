import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import type { PolicyRecord } from '@/types/api'

export function usePolicies() {
  return useQuery({
    queryKey: ['policies'],
    queryFn: () => apiClient.get<PolicyRecord[]>('/api/v1/policies'),
  })
}

export function useCreatePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { name: string; config: Record<string, unknown> }) =>
      apiClient.post<PolicyRecord>('/api/v1/policies', input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['policies'] })
    },
  })
}

export function useDeletePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (policyId: string) => apiClient.delete<void>(`/api/v1/policies/${policyId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['policies'] })
    },
  })
}
