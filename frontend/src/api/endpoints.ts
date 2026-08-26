import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import type { EndpointRecord, EndpointRegisterResponse } from '@/types/api'

interface RegisterEndpointInput {
  name: string
  hostname: string
  os: 'windows' | 'linux'
  os_version?: string
  agent_version?: string
}

export function useEndpoints() {
  return useQuery({
    queryKey: ['endpoints'],
    queryFn: () => apiClient.get<EndpointRecord[]>('/api/v1/endpoints'),
  })
}

export function useRegisterEndpoint() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: RegisterEndpointInput) =>
      apiClient.post<EndpointRegisterResponse>('/api/v1/endpoints/register', input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['endpoints'] })
    },
  })
}

export function useUpdateEndpointPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ endpointId, policyId }: { endpointId: string; policyId: string | null }) =>
      apiClient.patch<EndpointRecord>(`/api/v1/endpoints/${endpointId}`, { policy_id: policyId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['endpoints'] })
    },
  })
}
