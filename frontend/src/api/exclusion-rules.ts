import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { toast } from '@/components/ui/toast'
import type { ExclusionRuleRecord } from '@/types/api'

interface CreateExclusionRuleInput {
  category?: string
  path_pattern?: string
  reason: string
}

export function useCreateExclusionRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateExclusionRuleInput) =>
      apiClient.post<ExclusionRuleRecord>('/api/v1/exclusion-rules', input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['exclusion-rules'] })
      toast.success('Exclusion rule created')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create exclusion rule')
    },
  })
}
