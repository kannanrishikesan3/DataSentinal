import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient, buildQueryString } from '@/lib/api-client'
import type { EndpointRecord, EndpointRegisterResponse, PaginatedEndpoints } from '@/types/api'

interface RegisterEndpointInput {
  name: string
  hostname: string
  os: 'windows' | 'linux' | 'macos'
  os_version?: string
  agent_version?: string
}

interface EndpointListParams {
  q?: string
  limit?: number
  offset?: number
}

// Every registered endpoint's org membership makes this list naturally
// bounded in practice; used by dropdowns/lookups (finding detail, PII
// Explorer, filters) that need "effectively all" rather than one page.
const LOOKUP_LIMIT = 500

export function useEndpoints(params: EndpointListParams = {}) {
  return useQuery({
    queryKey: ['endpoints', params],
    queryFn: () =>
      apiClient.get<PaginatedEndpoints>(`/api/v1/endpoints${buildQueryString({ ...params })}`),
  })
}

/** For dropdowns/lookups that need every endpoint, not one paginated page. */
export function useAllEndpoints() {
  return useEndpoints({ limit: LOOKUP_LIMIT })
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
