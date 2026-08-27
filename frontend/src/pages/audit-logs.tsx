import * as React from 'react'

import { useAuditLogs } from '@/api/audit'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Pagination } from '@/components/ui/pagination'
import { SearchInput } from '@/components/ui/search-input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDebouncedValue } from '@/hooks/use-debounced-value'

const PAGE_SIZE = 25

export function AuditLogsPage() {
  const [search, setSearch] = React.useState('')
  const [offset, setOffset] = React.useState(0)
  const q = useDebouncedValue(search)

  React.useEffect(() => setOffset(0), [q])

  const { data, isLoading, isError, error, refetch } = useAuditLogs({ q: q || undefined, limit: PAGE_SIZE, offset })
  const logs = data?.items

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Audit Logs</h1>
        <p className="text-sm text-muted-foreground">Every mutating action taken by a user or an endpoint agent.</p>
      </div>

      <SearchInput value={search} onChange={setSearch} placeholder="Search by action or target type…" className="max-w-sm" />

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}
      {!isLoading && !isError && logs && logs.length === 0 && (
        <EmptyState message={q ? `No audit events match "${q}".` : 'No audit events yet.'} />
      )}

      {!isLoading && !isError && logs && logs.length > 0 && (
        <>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">{new Date(log.created_at).toLocaleString()}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {log.actor_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium text-foreground">{log.action}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {log.target_type ? `${log.target_type}:${log.target_id?.slice(0, 8)}` : '—'}
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-xs text-muted-foreground" title={JSON.stringify(log.details)}>
                      {log.details ? JSON.stringify(log.details) : '—'}
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
