import * as React from 'react'

import { useEndpoints } from '@/api/endpoints'
import { FindingsTable } from '@/components/findings-table'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { FindingListFilters, FindingStatus, Severity } from '@/types/api'

const ALL = '__all__'

const CATEGORY_GROUPS: { label: string; categories: string[] | null; isSecret?: boolean }[] = [
  { label: 'All PII', categories: null },
  { label: 'Emails', categories: ['email'] },
  { label: 'Phone Numbers', categories: ['phone_number'] },
  { label: 'Government IDs', categories: ['aadhaar', 'pan', 'ssn', 'passport', 'driver_license'] },
  { label: 'Financial', categories: ['credit_card', 'bank_account', 'iban', 'swift_bic'] },
  { label: 'Addresses', categories: ['address'] },
  { label: 'Secrets', categories: null, isSecret: true },
]

export function PiiExplorerPage() {
  const { data: endpoints } = useEndpoints()
  const [activeGroup, setActiveGroup] = React.useState(0)
  const [severity, setSeverity] = React.useState<string>(ALL)
  const [status, setStatus] = React.useState<string>(ALL)
  const [endpointId, setEndpointId] = React.useState<string>(ALL)
  const [fileType, setFileType] = React.useState('')
  const [dateFrom, setDateFrom] = React.useState('')
  const [dateTo, setDateTo] = React.useState('')

  const group = CATEGORY_GROUPS[activeGroup]
  const categories = group.categories

  const baseFilters: FindingListFilters = {
    is_secret: group.isSecret ?? false,
    category: categories?.length === 1 ? categories[0] : undefined,
    severity: severity === ALL ? undefined : (severity as Severity),
    status: status === ALL ? undefined : (status as FindingStatus),
    endpoint_id: endpointId === ALL ? undefined : endpointId,
    file_type: fileType.trim() || undefined,
    detected_after: dateFrom ? new Date(dateFrom).toISOString() : undefined,
    detected_before: dateTo ? new Date(`${dateTo}T23:59:59`).toISOString() : undefined,
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">PII Explorer</h1>
        <p className="text-sm text-slate-500">Browse detected personal information and secrets by category.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {CATEGORY_GROUPS.map((groupOption, index) => (
          <button
            key={groupOption.label}
            onClick={() => setActiveGroup(index)}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              index === activeGroup
                ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                : 'border-slate-300 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800',
            )}
          >
            {groupOption.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3">
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

        <div className="flex flex-col gap-1">
          <Label htmlFor="pii-file-type" className="text-xs text-slate-400">
            File type
          </Label>
          <Input
            id="pii-file-type"
            className="w-28"
            placeholder="e.g. csv"
            value={fileType}
            onChange={(event) => setFileType(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="pii-date-from" className="text-xs text-slate-400">
            From
          </Label>
          <Input
            id="pii-date-from"
            type="date"
            className="w-40"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="pii-date-to" className="text-xs text-slate-400">
            To
          </Label>
          <Input
            id="pii-date-to"
            type="date"
            className="w-40"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </div>
      </div>

      <FindingsFilteredByGroup filters={baseFilters} categories={categories} />
    </div>
  )
}

function FindingsFilteredByGroup({ filters, categories }: { filters: FindingListFilters; categories: string[] | null }) {
  if (!categories || categories.length <= 1) {
    return <FindingsTable filters={filters} />
  }
  return <MultiCategoryFindingsTable baseFilters={filters} categories={categories} />
}

function MultiCategoryFindingsTable({ baseFilters, categories }: { baseFilters: FindingListFilters; categories: string[] }) {
  // Render one table per category in the group and let each fetch its own
  // page — simplest correct way to cover an OR-of-categories filter without
  // adding a multi-category query param the backend doesn't support yet.
  return (
    <div className="space-y-6">
      {categories.map((category) => (
        <div key={category}>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{category.replace('_', ' ')}</h2>
          <FindingsTable filters={{ ...baseFilters, category }} />
        </div>
      ))}
    </div>
  )
}
