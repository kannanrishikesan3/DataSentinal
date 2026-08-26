import { useCancelScan, useScans } from '@/api/scans'
import { useEndpoints } from '@/api/endpoints'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { ScanStatus } from '@/types/api'

const STATUS_VARIANT: Record<ScanStatus, string> = {
  completed: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400',
  running: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400',
  pending: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
  cancelled: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-500',
  failed: 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400',
  timed_out: 'bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-400',
}

export function ScansPage() {
  const { data: scans, isLoading, isError, error, refetch } = useScans()
  const { data: endpoints } = useEndpoints()
  const cancelScan = useCancelScan()

  const endpointName = (endpointId: string) => endpoints?.find((e) => e.id === endpointId)?.name ?? endpointId.slice(0, 8)

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Scans</h1>
        <p className="text-sm text-slate-500">Every scan reported by an endpoint agent.</p>
      </div>

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}
      {!isLoading && !isError && scans && scans.length === 0 && <EmptyState message="No scans reported yet." />}

      {!isLoading && !isError && scans && scans.length > 0 && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Endpoint</TableHead>
                <TableHead>Profile</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Files scanned</TableHead>
                <TableHead>PII</TableHead>
                <TableHead>Secrets</TableHead>
                <TableHead>Started</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {scans.map((scan) => (
                <TableRow key={scan.id}>
                  <TableCell className="font-medium text-slate-900 dark:text-slate-100">
                    {endpointName(scan.endpoint_id)}
                  </TableCell>
                  <TableCell className="capitalize text-slate-500">{scan.profile}</TableCell>
                  <TableCell>
                    <Badge className={`capitalize ${STATUS_VARIANT[scan.status]}`}>{scan.status.replace('_', ' ')}</Badge>
                  </TableCell>
                  <TableCell>
                    {scan.files_scanned.toLocaleString()} / {scan.files_discovered.toLocaleString()}
                  </TableCell>
                  <TableCell>{scan.pii_findings.toLocaleString()}</TableCell>
                  <TableCell>{scan.secret_findings.toLocaleString()}</TableCell>
                  <TableCell className="text-slate-500">
                    {scan.started_at ? new Date(scan.started_at).toLocaleString() : '—'}
                  </TableCell>
                  <TableCell>
                    {scan.status === 'running' || scan.status === 'pending' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={cancelScan.isPending}
                        onClick={() => cancelScan.mutate(scan.id)}
                      >
                        Cancel
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  )
}
