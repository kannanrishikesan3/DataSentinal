import { useEnrollmentTokens, useRevokeEnrollmentToken } from '@/api/enrollment-tokens'
import { usePolicies } from '@/api/policies'
import { BulkImportEndpointsDialog } from '@/components/bulk-import-endpoints-dialog'
import { CreateEnrollmentTokenDialog } from '@/components/create-enrollment-token-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { EnrollmentTokenStatus } from '@/types/api'

const STATUS_STYLES: Record<EnrollmentTokenStatus, string> = {
  active: 'bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-400',
  expired: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
  revoked: 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400',
  exhausted: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-950/40 dark:text-yellow-400',
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString()
}

export function EnrollmentTokensSection() {
  const { data: tokens, isLoading } = useEnrollmentTokens()
  const { data: policies } = usePolicies()
  const revoke = useRevokeEnrollmentToken()

  function policyName(policyId: string | null): string {
    if (!policyId) return '—'
    return policies?.find((policy) => policy.id === policyId)?.name ?? 'Unknown policy'
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-slate-700 dark:text-slate-300">Enrollment tokens</CardTitle>
          <p className="mt-1 text-xs text-slate-400">
            Reusable, expiring tokens for self-service agent deployment — hand one to many people instead of
            registering each endpoint by hand.
          </p>
        </div>
        <div className="flex gap-2">
          <BulkImportEndpointsDialog />
          <CreateEnrollmentTokenDialog />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
        {!isLoading && tokens && tokens.length === 0 && (
          <p className="py-6 text-center text-sm text-slate-400">
            No enrollment tokens yet. Create one to deploy the agent to multiple machines at once.
          </p>
        )}
        {!isLoading && tokens && tokens.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Uses</TableHead>
                <TableHead>Allowed OS</TableHead>
                <TableHead>Policy</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {tokens.map((token) => (
                <TableRow key={token.id}>
                  <TableCell className="font-medium text-slate-900 dark:text-slate-100">{token.name}</TableCell>
                  <TableCell>
                    <Badge className={STATUS_STYLES[token.status]}>{token.status}</Badge>
                  </TableCell>
                  <TableCell className="text-slate-500">
                    {token.current_uses} / {token.max_uses}
                  </TableCell>
                  <TableCell className="capitalize text-slate-500">{token.allowed_os ?? 'Any'}</TableCell>
                  <TableCell className="text-slate-500">{policyName(token.policy_id)}</TableCell>
                  <TableCell className="text-slate-500">{formatDateTime(token.expires_at)}</TableCell>
                  <TableCell className="text-right">
                    {token.status === 'active' && (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={revoke.isPending}
                        onClick={() => revoke.mutate(token.id)}
                      >
                        Revoke
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
