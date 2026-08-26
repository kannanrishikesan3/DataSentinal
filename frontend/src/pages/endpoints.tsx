import { useCurrentUser } from '@/api/me'
import { useEndpoints, useUpdateEndpointPolicy } from '@/api/endpoints'
import { usePolicies } from '@/api/policies'
import { EnrollmentTokensSection } from '@/components/enrollment-tokens-section'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { RegisterEndpointDialog } from '@/components/register-endpoint-dialog'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'

const NO_POLICY = '__none__'

function formatDateTime(value: string | null): string {
  if (!value) return 'Never'
  return new Date(value).toLocaleString()
}

const RISK_SCORE_BANDS: { label: string; className: string }[] = [
  { label: 'None', className: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400' },
  { label: 'Low', className: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400' },
  { label: 'Medium', className: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-950/40 dark:text-yellow-400' },
  { label: 'High', className: 'bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-400' },
  { label: 'Critical', className: 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400' },
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
    return <span className="text-slate-500">{policies?.find((p) => p.id === policyId)?.name ?? '—'}</span>
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
  const { data: endpoints, isLoading, isError, error, refetch } = useEndpoints()

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Endpoints</h1>
          <p className="text-sm text-slate-500">Devices enrolled for discovery scanning.</p>
        </div>
        <RegisterEndpointDialog />
      </div>

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}
      {!isLoading && !isError && endpoints && endpoints.length === 0 && (
        <EmptyState message="No endpoints registered yet. Register one to start scanning." />
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
                  <TableCell className="font-medium text-slate-900 dark:text-slate-100">{endpoint.name}</TableCell>
                  <TableCell className="text-slate-500">{endpoint.hostname}</TableCell>
                  <TableCell className="capitalize">
                    {endpoint.os} {endpoint.os_version}
                  </TableCell>
                  <TableCell>{endpoint.agent_version ?? '—'}</TableCell>
                  <TableCell>
                    <Badge variant={endpoint.status === 'active' ? 'default' : 'outline'} className="capitalize">
                      {endpoint.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-slate-500">{formatDateTime(endpoint.last_seen_at)}</TableCell>
                  <TableCell className="text-slate-500">{formatDateTime(endpoint.last_scan)}</TableCell>
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

      <EnrollmentTokensSection />
    </div>
  )
}
