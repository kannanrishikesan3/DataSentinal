import { Download } from 'lucide-react'
import * as React from 'react'

import { useEndpoints } from '@/api/endpoints'
import { downloadReport, fetchReport } from '@/api/reports'
import { useScans } from '@/api/scans'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const FORMATS = ['json', 'csv', 'html', 'text'] as const
type ReportFormat = (typeof FORMATS)[number]

export function ReportsPage() {
  const { data: scans, isLoading, isError, error, refetch } = useScans()
  const { data: endpoints } = useEndpoints()
  const [format, setFormat] = React.useState<ReportFormat>('json')
  const [downloadingId, setDownloadingId] = React.useState<string | null>(null)

  const endpointName = (endpointId: string) => endpoints?.find((e) => e.id === endpointId)?.name ?? endpointId.slice(0, 8)

  async function handleDownload(scanId: string) {
    setDownloadingId(scanId)
    try {
      const content = await fetchReport(scanId, format)
      downloadReport(scanId, format, content)
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Reports</h1>
          <p className="text-sm text-slate-500">Download a scan summary, findings, and recommendations.</p>
        </div>
        <Select value={format} onValueChange={(value) => setFormat(value as ReportFormat)}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {FORMATS.map((f) => (
              <SelectItem key={f} value={f}>
                {f.toUpperCase()}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}
      {!isLoading && !isError && scans && scans.length === 0 && <EmptyState message="No completed scans yet." />}

      {!isLoading && !isError && scans && scans.length > 0 && (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Endpoint</TableHead>
                <TableHead>Profile</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Findings</TableHead>
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
                  <TableCell className="capitalize text-slate-500">{scan.status.replace('_', ' ')}</TableCell>
                  <TableCell>{(scan.pii_findings + scan.secret_findings).toLocaleString()}</TableCell>
                  <TableCell>
                    <Button size="sm" variant="outline" disabled={downloadingId === scan.id} onClick={() => handleDownload(scan.id)}>
                      <Download className="h-3.5 w-3.5" />
                      {downloadingId === scan.id ? 'Downloading…' : 'Download'}
                    </Button>
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
