import { useMutation } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { setStoredToken } from '@/lib/auth-storage'
import type { TokenResponse } from '@/types/api'

interface LoginInput {
  email: string
  password: string
}

export function useLogin() {
  return useMutation({
    mutationFn: (input: LoginInput) =>
      apiClient.post<TokenResponse>('/api/v1/auth/login', input, { auth: false }),
    onSuccess: (data) => {
      setStoredToken(data.access_token)
    },
  })
}
