import * as React from 'react'

import { useCurrentUser } from '@/api/me'
import { useCreatePolicy, useDeletePolicy, usePolicies } from '@/api/policies'
import { EmptyState, PageError, PageSkeleton } from '@/components/page-states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export function PoliciesPage() {
  const { data: policies, isLoading, isError, error, refetch } = usePolicies()
  const { data: currentUser } = useCurrentUser()
  const createPolicy = useCreatePolicy()
  const deletePolicy = useDeletePolicy()
  const [name, setName] = React.useState('')
  const [configText, setConfigText] = React.useState('{\n  "aggregation_category_threshold": 3\n}')
  const [jsonError, setJsonError] = React.useState<string | null>(null)
  const isAdmin = currentUser?.role === 'admin'

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    try {
      const config = JSON.parse(configText) as Record<string, unknown>
      setJsonError(null)
      createPolicy.mutate(
        { name, config },
        { onSuccess: () => setName('') },
      )
    } catch {
      setJsonError('Config must be valid JSON.')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Policies</h1>
        <p className="text-sm text-slate-500">
          Named risk-engine overrides (scan thresholds, exclusion rules) pushed to agents. Agents fall back to their
          local defaults when none apply.
        </p>
        {!isAdmin && (
          <p className="mt-1 text-xs text-slate-400">Only admins can create, edit, or delete policies.</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {isLoading && <PageSkeleton />}
          {isError && <PageError error={error} onRetry={refetch} />}
          {!isLoading && !isError && policies && policies.length === 0 && (
            <EmptyState message="No policies defined yet." />
          )}
          {!isLoading && !isError && policies && policies.length > 0 && (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Config</TableHead>
                    <TableHead>Updated</TableHead>
                    {isAdmin && <TableHead />}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {policies.map((policy) => (
                    <TableRow key={policy.id}>
                      <TableCell className="font-medium text-slate-900 dark:text-slate-100">{policy.name}</TableCell>
                      <TableCell className="max-w-xs truncate font-mono text-xs text-slate-500">
                        {JSON.stringify(policy.config)}
                      </TableCell>
                      <TableCell className="text-slate-500">{new Date(policy.updated_at).toLocaleDateString()}</TableCell>
                      {isAdmin && (
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={deletePolicy.isPending}
                            onClick={() => deletePolicy.mutate(policy.id)}
                          >
                            Delete
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </div>

        {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="text-slate-700 dark:text-slate-300">New policy</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={handleSubmit}>
              <div className="space-y-1.5">
                <Label htmlFor="policy-name">Name</Label>
                <Input id="policy-name" required value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="policy-config">Config (JSON)</Label>
                <textarea
                  id="policy-config"
                  className="h-32 w-full rounded-md border border-slate-300 bg-white p-2 font-mono text-xs text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={configText}
                  onChange={(e) => setConfigText(e.target.value)}
                />
              </div>
              {jsonError && <p className="text-xs text-red-600">{jsonError}</p>}
              {createPolicy.isError && <p className="text-xs text-red-600">Failed to save — name may already exist.</p>}
              <Button type="submit" className="w-full" disabled={createPolicy.isPending}>
                {createPolicy.isPending ? 'Saving…' : 'Create policy'}
              </Button>
            </form>
          </CardContent>
        </Card>
        )}
      </div>
    </div>
  )
}
