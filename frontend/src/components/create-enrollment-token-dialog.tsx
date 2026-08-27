import { Plus } from 'lucide-react'
import * as React from 'react'

import { useCreateEnrollmentToken } from '@/api/enrollment-tokens'
import { usePolicies } from '@/api/policies'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const ANY_OS = '__any__'
const NO_POLICY = '__none__'

export function CreateEnrollmentTokenDialog() {
  const [open, setOpen] = React.useState(false)
  const [name, setName] = React.useState('')
  const [expiresInDays, setExpiresInDays] = React.useState('7')
  const [maxUses, setMaxUses] = React.useState('100')
  const [allowedOs, setAllowedOs] = React.useState(ANY_OS)
  const [policyId, setPolicyId] = React.useState(NO_POLICY)
  const [issuedToken, setIssuedToken] = React.useState<string | null>(null)
  const createToken = useCreateEnrollmentToken()
  const { data: policies } = usePolicies()

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createToken.mutate(
      {
        name,
        expires_in_days: Number(expiresInDays),
        max_uses: Number(maxUses),
        allowed_os: allowedOs === ANY_OS ? undefined : (allowedOs as 'windows' | 'linux' | 'macos'),
        policy_id: policyId === NO_POLICY ? undefined : policyId,
      },
      { onSuccess: (data) => setIssuedToken(data.raw_token) },
    )
  }

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      setName('')
      setExpiresInDays('7')
      setMaxUses('100')
      setAllowedOs(ANY_OS)
      setPolicyId(NO_POLICY)
      setIssuedToken(null)
      createToken.reset()
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus className="h-4 w-4" />
          Create enrollment token
        </Button>
      </DialogTrigger>
      <DialogContent>
        {issuedToken ? (
          <>
            <DialogHeader>
              <DialogTitle>Enrollment token created</DialogTitle>
            </DialogHeader>
            <p className="mb-2 text-sm text-muted-foreground">
              Copy this token and share it with the people deploying agents. It will not be shown again — hand it out
              now, then use <code className="rounded bg-muted px-1">datasentinel enroll</code>{' '}
              (or the equivalent silent-install parameter) on each machine.
            </p>
            <code className="block break-all rounded-md bg-muted p-3 text-xs">{issuedToken}</code>
            <Button className="mt-4 w-full" variant="outline" onClick={() => handleOpenChange(false)}>
              Done
            </Button>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Create enrollment token</DialogTitle>
            </DialogHeader>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-1.5">
                <Label htmlFor="tok-name">Name</Label>
                <Input
                  id="tok-name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Employee Windows Deployment"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="tok-expiry">Expires in (days)</Label>
                  <Input
                    id="tok-expiry"
                    type="number"
                    min={1}
                    max={365}
                    required
                    value={expiresInDays}
                    onChange={(e) => setExpiresInDays(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="tok-max-uses">Maximum uses</Label>
                  <Input
                    id="tok-max-uses"
                    type="number"
                    min={1}
                    required
                    value={maxUses}
                    onChange={(e) => setMaxUses(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Allowed OS</Label>
                <Select value={allowedOs} onValueChange={setAllowedOs}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY_OS}>Any</SelectItem>
                    <SelectItem value="windows">Windows only</SelectItem>
                    <SelectItem value="linux">Linux only</SelectItem>
                    <SelectItem value="macos">macOS only</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Auto-assign policy</Label>
                <Select value={policyId} onValueChange={setPolicyId}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_POLICY}>None (org-wide defaults)</SelectItem>
                    {policies?.map((policy) => (
                      <SelectItem key={policy.id} value={policy.id}>
                        {policy.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Every endpoint that enrolls with this token gets this policy applied automatically.
                </p>
              </div>
              {createToken.isError && <p className="text-sm text-destructive">Could not create the token. Try again.</p>}
              <Button type="submit" className="w-full" disabled={createToken.isPending}>
                {createToken.isPending ? 'Generating…' : 'Generate token'}
              </Button>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
