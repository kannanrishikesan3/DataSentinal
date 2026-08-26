import { Download, Upload } from 'lucide-react'
import * as React from 'react'

import { useBulkImportEndpoints, useDownloadImportTemplate } from '@/api/enrollment-tokens'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { BulkImportResponse } from '@/types/api'

export function BulkImportEndpointsDialog() {
  const [open, setOpen] = React.useState(false)
  const [result, setResult] = React.useState<BulkImportResponse | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const downloadTemplate = useDownloadImportTemplate()
  const bulkImport = useBulkImportEndpoints()

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      setResult(null)
      bulkImport.reset()
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    bulkImport.mutate(file, { onSuccess: setResult })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Upload className="h-4 w-4" />
          Import from Excel
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Bulk-import endpoints</DialogTitle>
        </DialogHeader>

        <p className="text-sm text-slate-500">
          For a known list of devices (e.g. an IT asset inventory) — download the template, fill in one row per
          device, then upload it. Each successfully created endpoint gets its own API token, shown once below.
        </p>

        <Button variant="outline" size="sm" onClick={() => downloadTemplate.mutate()} disabled={downloadTemplate.isPending}>
          <Download className="h-4 w-4" />
          {downloadTemplate.isPending ? 'Downloading…' : 'Download template (.xlsx)'}
        </Button>

        <div className="space-y-1.5">
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            onChange={handleFileChange}
            disabled={bulkImport.isPending}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-800 dark:text-slate-400 dark:file:bg-slate-100 dark:file:text-slate-900"
          />
          {bulkImport.isPending && <p className="text-xs text-slate-400">Importing…</p>}
        </div>

        {result && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {result.created} created, {result.failed} failed
            </p>
            <div className="max-h-64 overflow-y-auto rounded-md border border-slate-200 dark:border-slate-800">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Row</TableHead>
                    <TableHead>Hostname</TableHead>
                    <TableHead>Result</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.rows.map((row) => (
                    <TableRow key={row.row}>
                      <TableCell>{row.row}</TableCell>
                      <TableCell className="font-mono text-xs">{row.hostname}</TableCell>
                      <TableCell>
                        {row.status === 'created' ? (
                          <code className="break-all rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">
                            {row.api_token}
                          </code>
                        ) : (
                          <span className="text-xs text-red-600">{row.error}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <p className="text-xs text-slate-400">
              Copy each token now — like a single registration, none of these are shown again after you close this
              dialog.
            </p>
          </div>
        )}

        <Button variant="outline" className="w-full" onClick={() => handleOpenChange(false)}>
          {result ? 'Done' : 'Cancel'}
        </Button>
      </DialogContent>
    </Dialog>
  )
}
