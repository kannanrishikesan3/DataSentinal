import * as React from 'react'

import { useFindings } from '@/api/findings'
import { categoryLabel, FindingDetailDialog } from '@/components/finding-detail-dialog'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { SeverityBadge } from '@/components/severity-badge'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Pagination } from '@/components/ui/pagination'
import { SearchInput } from '@/components/ui/search-input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import type { FindingListFilters } from '@/types/api'

const PAGE_SIZE = 25

export function FindingsTable({ filters }: { filters: FindingListFilters }) {
  const [search, setSearch] = React.useState('')
  const [offset, setOffset] = React.useState(0)
  const q = useDebouncedValue(search)
  const filterKey = JSON.stringify(filters)

  // Any change to the incoming filters (severity/status/endpoint/category/…)
  // or the search term restarts pagination — staying on page 3 of a now
  // different result set would be confusing.
  React.useEffect(() => setOffset(0), [filterKey, q])

  const { data, isLoading, isError, error, refetch } = useFindings({
    ...filters,
    q: q || undefined,
    limit: PAGE_SIZE,
    offset,
  })
  const [selectedId, setSelectedId] = React.useState<string | null>(null)

  const selected = data?.items.find((f) => f.id === selectedId) ?? null

  return (
    <div className="space-y-4">
      <SearchInput value={search} onChange={setSearch} placeholder="Search by file path…" className="max-w-sm" />

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}
      {!isLoading && !isError && (!data || data.items.length === 0) && (
        <EmptyState message={q ? `No findings match "${q}".` : 'No findings match these filters.'} />
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
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
                        <Badge className="ml-1.5 bg-foreground text-background">Secret</Badge>
                      )}
                    </TableCell>
                    <TableCell className="max-w-xs truncate font-mono text-xs text-muted-foreground" title={finding.file_path}>
                      {finding.file_path}
                    </TableCell>
                    <TableCell>{Math.round(finding.confidence * 100)}%</TableCell>
                    <TableCell>{finding.occurrence_count}</TableCell>
                    <TableCell className="capitalize text-muted-foreground">{finding.status.replace('_', ' ')}</TableCell>
                    <TableCell className="text-muted-foreground">{new Date(finding.detected_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onOffsetChange={setOffset} />
        </>
      )}

      <FindingDetailDialog finding={selected} open={Boolean(selected)} onOpenChange={(open) => !open && setSelectedId(null)} />
    </div>
  )
}
