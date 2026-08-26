import * as React from 'react'

import { useEndpoints } from '@/api/endpoints'
import { FindingsTable } from '@/components/findings-table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { FindingListFilters, FindingStatus, Severity } from '@/types/api'

const ALL = '__all__'

export function FindingsPage() {
  const { data: endpoints } = useEndpoints()
  const [severity, setSeverity] = React.useState<string>(ALL)
  const [status, setStatus] = React.useState<string>(ALL)
  const [endpointId, setEndpointId] = React.useState<string>(ALL)

  const filters: FindingListFilters = {
    severity: severity === ALL ? undefined : (severity as Severity),
    status: status === ALL ? undefined : (status as FindingStatus),
    endpoint_id: endpointId === ALL ? undefined : endpointId,
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Findings</h1>
        <p className="text-sm text-slate-500">Every PII and secret detection across your organization.</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <Select value={severity} onValueChange={setSeverity}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All severities</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
            <SelectItem value="informational">Informational</SelectItem>
          </SelectContent>
        </Select>

        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="false_positive">False positive</SelectItem>
            <SelectItem value="suppressed">Suppressed</SelectItem>
            <SelectItem value="reopened">Reopened</SelectItem>
          </SelectContent>
        </Select>

        <Select value={endpointId} onValueChange={setEndpointId}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Endpoint" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All endpoints</SelectItem>
            {endpoints?.map((endpoint) => (
              <SelectItem key={endpoint.id} value={endpoint.id}>
                {endpoint.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <FindingsTable filters={filters} />
    </div>
  )
}
