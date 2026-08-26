import { useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'

export interface CurrentUser {
  id: string
  org_id: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  created_at: string
}

export function useCurrentUser() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => apiClient.get<CurrentUser>('/api/v1/auth/me'),
  })
}
