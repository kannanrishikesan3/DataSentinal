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
  active: 'bg-success-bg text-success-fg',
  expired: 'bg-muted text-muted-foreground',
  revoked: 'bg-destructive/10 text-destructive',
  exhausted: 'bg-severity-medium-bg text-severity-medium-fg',
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
          <CardTitle className="text-foreground">Enrollment tokens</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
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
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!isLoading && tokens && tokens.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
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
                  <TableCell className="font-medium text-foreground">{token.name}</TableCell>
                  <TableCell>
                    <Badge className={STATUS_STYLES[token.status]}>{token.status}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {token.current_uses} / {token.max_uses}
                  </TableCell>
                  <TableCell className="capitalize text-muted-foreground">{token.allowed_os ?? 'Any'}</TableCell>
                  <TableCell className="text-muted-foreground">{policyName(token.policy_id)}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(token.expires_at)}</TableCell>
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
