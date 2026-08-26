import * as React from 'react'

import { useFindings } from '@/api/findings'
import { categoryLabel, FindingDetailDialog } from '@/components/finding-detail-dialog'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { SeverityBadge } from '@/components/severity-badge'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { FindingListFilters } from '@/types/api'

export function FindingsTable({ filters }: { filters: FindingListFilters }) {
  const { data, isLoading, isError, error, refetch } = useFindings(filters)
  const [selectedId, setSelectedId] = React.useState<string | null>(null)

  const selected = data?.items.find((f) => f.id === selectedId) ?? null

  if (isLoading) return <PageSkeleton />
  if (isError) return <PageError error={error} onRetry={refetch} />
  if (!data || data.items.length === 0) return <EmptyState message="No findings match these filters." />

  return (
    <>
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Severity</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>File</TableHead>
              <TableHead>Confidence</TableHead>
              <TableHead>Occurrences</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Detected</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((finding) => (
              <TableRow key={finding.id} className="cursor-pointer" onClick={() => setSelectedId(finding.id)}>
                <TableCell>
                  <SeverityBadge severity={finding.severity} />
                </TableCell>
                <TableCell>
                  {categoryLabel(finding.category)}
                  {finding.is_secret && (
                    <Badge className="ml-1.5 bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900">Secret</Badge>
                  )}
                </TableCell>
                <TableCell className="max-w-xs truncate font-mono text-xs text-slate-500" title={finding.file_path}>
                  {finding.file_path}
                </TableCell>
                <TableCell>{Math.round(finding.confidence * 100)}%</TableCell>
                <TableCell>{finding.occurrence_count}</TableCell>
                <TableCell className="capitalize text-slate-500">{finding.status.replace('_', ' ')}</TableCell>
                <TableCell className="text-slate-500">{new Date(finding.detected_at).toLocaleDateString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
      <p className="text-xs text-slate-400">
        Showing {data.items.length} of {data.total.toLocaleString()} findings
      </p>
      <FindingDetailDialog finding={selected} open={Boolean(selected)} onOpenChange={(open) => !open && setSelectedId(null)} />
    </>
  )
}
