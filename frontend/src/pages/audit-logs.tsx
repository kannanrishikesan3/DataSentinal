import { useAuditLogs } from '@/api/audit'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export function AuditLogsPage() {
  const { data: logs, isLoading, isError, error, refetch } = useAuditLogs()

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Audit Logs</h1>
        <p className="text-sm text-slate-500">Every mutating action taken by a user or an endpoint agent.</p>
      </div>

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}
      {!isLoading && !isError && logs && logs.length === 0 && <EmptyState message="No audit events yet." />}

      {!isLoading && !isError && logs && logs.length > 0 && (
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
                  <TableCell className="whitespace-nowrap text-slate-500">{new Date(log.created_at).toLocaleString()}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">
                      {log.actor_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-medium text-slate-900 dark:text-slate-100">{log.action}</TableCell>
                  <TableCell className="text-slate-500">
                    {log.target_type ? `${log.target_type}:${log.target_id?.slice(0, 8)}` : '—'}
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-xs text-slate-400" title={JSON.stringify(log.details)}>
                    {log.details ? JSON.stringify(log.details) : '—'}
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
