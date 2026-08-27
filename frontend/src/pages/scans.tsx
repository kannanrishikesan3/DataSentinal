import * as React from 'react'

import { useCancelScan, useScans } from '@/api/scans'
import { useAllEndpoints } from '@/api/endpoints'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Pagination } from '@/components/ui/pagination'
import { SearchInput } from '@/components/ui/search-input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import type { ScanStatus } from '@/types/api'

const PAGE_SIZE = 25

const STATUS_VARIANT: Record<ScanStatus, string> = {
  completed: 'bg-success-bg text-success-fg',
  running: 'bg-accent text-accent-foreground',
  pending: 'bg-secondary text-secondary-foreground',
  cancelled: 'bg-muted text-muted-foreground',
  failed: 'bg-destructive/10 text-destructive',
  timed_out: 'bg-severity-high-bg text-severity-high-fg',
}

export function ScansPage() {
  const [search, setSearch] = React.useState('')
  const [offset, setOffset] = React.useState(0)
  const q = useDebouncedValue(search)

  React.useEffect(() => setOffset(0), [q])

  const { data, isLoading, isError, error, refetch } = useScans({ q: q || undefined, limit: PAGE_SIZE, offset })
  const { data: endpointsData } = useAllEndpoints()
  const endpoints = endpointsData?.items
  const cancelScan = useCancelScan()

  const endpointName = (endpointId: string) => endpoints?.find((e) => e.id === endpointId)?.name ?? endpointId.slice(0, 8)
  const scans = data?.items

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Scans</h1>
        <p className="text-sm text-muted-foreground">Every scan reported by an endpoint agent.</p>
      </div>

      <SearchInput value={search} onChange={setSearch} placeholder="Search by endpoint name or hostname…" className="max-w-sm" />

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}
      {!isLoading && !isError && scans && scans.length === 0 && (
        <EmptyState message={q ? `No scans match "${q}".` : 'No scans reported yet.'} />
      )}

      {!isLoading && !isError && scans && scans.length > 0 && (
        <>
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
                    <TableCell className="font-medium text-foreground">{endpointName(scan.endpoint_id)}</TableCell>
                    <TableCell className="capitalize text-muted-foreground">{scan.profile}</TableCell>
                    <TableCell>
                      <Badge className={`capitalize ${STATUS_VARIANT[scan.status]}`}>{scan.status.replace('_', ' ')}</Badge>
                    </TableCell>
                    <TableCell>
                      {scan.files_scanned.toLocaleString()} / {scan.files_discovered.toLocaleString()}
                    </TableCell>
                    <TableCell>{scan.pii_findings.toLocaleString()}</TableCell>
                    <TableCell>{scan.secret_findings.toLocaleString()}</TableCell>
                    <TableCell className="text-muted-foreground">
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
          <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onOffsetChange={setOffset} />
        </>
      )}
    </div>
  )
}
