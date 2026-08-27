import * as React from 'react'

import { useCurrentUser } from '@/api/me'
import { useEndpoints, useUpdateEndpointPolicy } from '@/api/endpoints'
import { usePolicies } from '@/api/policies'
import { EnrollmentTokensSection } from '@/components/enrollment-tokens-section'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { RegisterEndpointDialog } from '@/components/register-endpoint-dialog'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Pagination } from '@/components/ui/pagination'
import { SearchInput } from '@/components/ui/search-input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 25

const NO_POLICY = '__none__'

const OS_LABELS: Record<string, string> = { windows: 'Windows', linux: 'Linux', macos: 'macOS' }

function osLabel(os: string): string {
  return OS_LABELS[os] ?? os
}

function formatDateTime(value: string | null): string {
  if (!value) return 'Never'
  return new Date(value).toLocaleString()
}

const RISK_SCORE_BANDS: { label: string; className: string }[] = [
  { label: 'None', className: 'bg-muted text-muted-foreground' },
  { label: 'Low', className: 'bg-severity-low-bg text-severity-low-fg' },
  { label: 'Medium', className: 'bg-severity-medium-bg text-severity-medium-fg' },
  { label: 'High', className: 'bg-severity-high-bg text-severity-high-fg' },
  { label: 'Critical', className: 'bg-severity-critical-bg text-severity-critical-fg' },
]

function RiskScoreBadge({ riskScore }: { riskScore: number }) {
  const band = RISK_SCORE_BANDS[Math.min(Math.max(riskScore, 0), RISK_SCORE_BANDS.length - 1)]
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', band.className)}>
      {band.label}
    </span>
  )
}

function PolicyCell({ endpointId, policyId }: { endpointId: string; policyId: string | null }) {
  const { data: currentUser } = useCurrentUser()
  const { data: policies } = usePolicies()
  const updatePolicy = useUpdateEndpointPolicy()
  const isAdmin = currentUser?.role === 'admin'

  if (!isAdmin) {
    return <span className="text-muted-foreground">{policies?.find((p) => p.id === policyId)?.name ?? '—'}</span>
  }

  return (
    <Select
      value={policyId ?? NO_POLICY}
      onValueChange={(value) =>
        updatePolicy.mutate({ endpointId, policyId: value === NO_POLICY ? null : value })
      }
    >
      <SelectTrigger className="h-8 w-40">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NO_POLICY}>None (org-wide)</SelectItem>
        {policies?.map((policy) => (
          <SelectItem key={policy.id} value={policy.id}>
            {policy.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export function EndpointsPage() {
  const [search, setSearch] = React.useState('')
  const [offset, setOffset] = React.useState(0)
  const q = useDebouncedValue(search)

  React.useEffect(() => setOffset(0), [q])

  const { data, isLoading, isError, error, refetch } = useEndpoints({ q: q || undefined, limit: PAGE_SIZE, offset })
  const endpoints = data?.items

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Endpoints</h1>
          <p className="text-sm text-muted-foreground">Devices enrolled for discovery scanning.</p>
        </div>
        <RegisterEndpointDialog />
      </div>

      <SearchInput value={search} onChange={setSearch} placeholder="Search by name or hostname…" className="max-w-sm" />

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}
      {!isLoading && !isError && endpoints && endpoints.length === 0 && (
        <EmptyState message={q ? `No endpoints match "${q}".` : 'No endpoints registered yet. Register one to start scanning.'} />
      )}

      {!isLoading && !isError && endpoints && endpoints.length > 0 && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Hostname</TableHead>
                <TableHead>OS</TableHead>
                <TableHead>Agent version</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last seen</TableHead>
                <TableHead>Last scan</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Policy</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {endpoints.map((endpoint) => (
                <TableRow key={endpoint.id}>
                  <TableCell className="font-medium text-foreground">{endpoint.name}</TableCell>
                  <TableCell className="text-muted-foreground">{endpoint.hostname}</TableCell>
                  <TableCell>
                    {osLabel(endpoint.os)} {endpoint.os_version}
                  </TableCell>
                  <TableCell>{endpoint.agent_version ?? '—'}</TableCell>
                  <TableCell>
                    <Badge variant={endpoint.status === 'active' ? 'default' : 'outline'} className="capitalize">
                      {endpoint.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(endpoint.last_seen_at)}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(endpoint.last_scan)}</TableCell>
                  <TableCell>
                    <RiskScoreBadge riskScore={endpoint.risk_score} />
                  </TableCell>
                  <TableCell>
                    <PolicyCell endpointId={endpoint.id} policyId={endpoint.policy_id} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
      {!isLoading && !isError && data && endpoints && endpoints.length > 0 && (
        <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onOffsetChange={setOffset} />
      )}

      <EnrollmentTokensSection />
    </div>
  )
}
