import * as React from 'react'

import { useCreateExclusionRule } from '@/api/exclusion-rules'
import { useEndpoints } from '@/api/endpoints'
import { useUpdateFindingStatus } from '@/api/findings'
import { useCurrentUser } from '@/api/me'
import { SeverityBadge } from '@/components/severity-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { FindingRecord } from '@/types/api'

const CATEGORY_LABELS: Record<string, string> = {
  aadhaar: 'Aadhaar', pan: 'PAN', ssn: 'SSN', passport: 'Passport', driver_license: 'Driver License',
  credit_card: 'Payment Card', bank_account: 'Bank Account', iban: 'IBAN', swift_bic: 'SWIFT/BIC',
  email: 'Email', phone_number: 'Phone Number', address: 'Address', person: 'Person Name',
  employee_id: 'Employee ID', customer_id: 'Customer ID', username: 'Username',
  date_of_birth: 'Date of Birth', age: 'Age', ipv4: 'IPv4 Address', ipv6: 'IPv6 Address', mac_address: 'MAC Address',
  api_key: 'API Key', access_token: 'Access Token', jwt: 'JWT', aws_credentials: 'AWS Credentials',
  private_key: 'Private Key', ssh_key: 'SSH Key', oauth_token: 'OAuth Token', database_url: 'Database URL',
  connection_string: 'Connection String', password_assignment: 'Password', generic_high_entropy_secret: 'High-Entropy Secret',
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category
}

export function FindingDetailDialog({
  finding,
  open,
  onOpenChange,
}: {
  finding: FindingRecord | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const updateStatus = useUpdateFindingStatus()
  const createExclusionRule = useCreateExclusionRule()
  const { data: endpoints } = useEndpoints()
  const { data: currentUser } = useCurrentUser()
  const [showExclusionForm, setShowExclusionForm] = React.useState(false)
  const [reason, setReason] = React.useState('')
  const canMutate = currentUser?.role !== 'viewer'

  React.useEffect(() => {
    setShowExclusionForm(false)
    setReason('')
  }, [finding?.id])

  if (!finding) return null

  const endpointName = endpoints?.find((endpoint) => endpoint.id === finding.endpoint_id)?.name ?? finding.endpoint_id

  const handleCreateExclusionRule = () => {
    createExclusionRule.mutate(
      { category: finding.category, reason },
      {
        onSuccess: () => {
          setShowExclusionForm(false)
          setReason('')
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Finding #{finding.id.slice(0, 8).toUpperCase()}</DialogTitle>
        </DialogHeader>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <Field label="Severity">
            <SeverityBadge severity={finding.severity} />
          </Field>
          <Field label="Category">
            {categoryLabel(finding.category)}
            {finding.is_secret && <Badge className="ml-1.5 bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900">Secret</Badge>}
          </Field>
          <Field label="Endpoint">{endpointName}</Field>
          <Field label="File" full>
            <span className="break-all font-mono text-xs">{finding.file_path}</span>
          </Field>
          <Field label="Confidence">{Math.round(finding.confidence * 100)}%</Field>
          <Field label="Occurrences">{finding.occurrence_count}</Field>
          <Field label="Detection">{finding.detection_method.replace('_', ' ')}</Field>
          <Field label="Status" className="capitalize">
            {finding.status.replace('_', ' ')}
          </Field>
          {finding.line_number != null && <Field label="Line">{finding.line_number}</Field>}
          {finding.page_number != null && <Field label="Page">{finding.page_number}</Field>}
          {finding.sheet_name && <Field label="Sheet">{finding.sheet_name}</Field>}
          <Field label="Evidence" full>
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">{finding.redacted_evidence}</code>
          </Field>
        </dl>

        <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-200 pt-4 dark:border-slate-800">
          {!canMutate && <p className="text-xs text-slate-400">Viewers cannot change findings.</p>}
          {canMutate && finding.status !== 'false_positive' && (
            <Button
              size="sm"
              variant="outline"
              disabled={updateStatus.isPending}
              onClick={() => updateStatus.mutate({ findingId: finding.id, status: 'false_positive' })}
            >
              Mark as false positive
            </Button>
          )}
          {canMutate && finding.status !== 'suppressed' && (
            <Button
              size="sm"
              variant="outline"
              disabled={updateStatus.isPending}
              onClick={() => updateStatus.mutate({ findingId: finding.id, status: 'suppressed' })}
            >
              Suppress
            </Button>
          )}
          {canMutate && finding.status !== 'open' && (
            <Button
              size="sm"
              disabled={updateStatus.isPending}
              onClick={() => updateStatus.mutate({ findingId: finding.id, status: 'reopened' })}
            >
              Reopen
            </Button>
          )}
          {canMutate && !showExclusionForm && (
            <Button size="sm" variant="outline" onClick={() => setShowExclusionForm(true)}>
              Create exclusion rule
            </Button>
          )}
        </div>

        {canMutate && showExclusionForm && (
          <div className="mt-3 space-y-2 rounded-md border border-slate-200 p-3 dark:border-slate-800">
            <Label htmlFor="exclusion-reason">
              Exclude all "{categoryLabel(finding.category)}" findings — reason
            </Label>
            <Input
              id="exclusion-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="e.g. Known test fixture data"
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={!reason.trim() || createExclusionRule.isPending}
                onClick={handleCreateExclusionRule}
              >
                Confirm
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowExclusionForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function Field({
  label,
  children,
  full,
  className,
}: {
  label: string
  children: React.ReactNode
  full?: boolean
  className?: string
}) {
  return (
    <div className={full ? `col-span-2 ${className ?? ''}` : className}>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-slate-900 dark:text-slate-100">{children}</dd>
    </div>
  )
}
