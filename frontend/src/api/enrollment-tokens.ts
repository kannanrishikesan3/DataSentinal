import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { toast } from '@/components/ui/toast'
import { apiClient } from '@/lib/api-client'
import type { BulkImportResponse, EnrollmentTokenCreateResponse, EnrollmentTokenRecord } from '@/types/api'

interface CreateEnrollmentTokenInput {
  name: string
  expires_in_days: number
  max_uses: number
  allowed_os?: 'windows' | 'linux' | 'macos'
  policy_id?: string
}

export function useEnrollmentTokens() {
  return useQuery({
    queryKey: ['enrollment-tokens'],
    queryFn: () => apiClient.get<EnrollmentTokenRecord[]>('/api/v1/enrollment-tokens'),
  })
}

export function useCreateEnrollmentToken() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateEnrollmentTokenInput) =>
      apiClient.post<EnrollmentTokenCreateResponse>('/api/v1/enrollment-tokens', input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['enrollment-tokens'] })
      toast.success('Enrollment token created')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create enrollment token')
    },
  })
}

export function useRevokeEnrollmentToken() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (tokenId: string) =>
      apiClient.post<EnrollmentTokenRecord>(`/api/v1/enrollment-tokens/${tokenId}/revoke`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['enrollment-tokens'] })
      toast.success('Enrollment token revoked')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to revoke enrollment token')
    },
  })
}

export function useDownloadImportTemplate() {
  return useMutation({
    mutationFn: async () => {
      const { blob, filename } = await apiClient.getBlob('/api/v1/endpoints/import-template')
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename ?? 'datasentinel-endpoint-import-template.xlsx'
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to download template')
    },
  })
}

export function useBulkImportEndpoints() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return apiClient.postForm<BulkImportResponse>('/api/v1/endpoints/bulk-import', formData)
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['endpoints'] })
      if (result.failed === 0) {
        toast.success(`Imported ${result.created} endpoint${result.created === 1 ? '' : 's'}`)
      } else {
        toast.error(`Imported ${result.created}, ${result.failed} row${result.failed === 1 ? '' : 's'} failed — see details below`)
      }
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Import failed')
    },
  })
}
