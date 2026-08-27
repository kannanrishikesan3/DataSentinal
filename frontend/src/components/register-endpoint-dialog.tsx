import { Plus } from 'lucide-react'
import * as React from 'react'

import { useRegisterEndpoint } from '@/api/endpoints'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export function RegisterEndpointDialog() {
  const [open, setOpen] = React.useState(false)
  const [name, setName] = React.useState('')
  const [hostname, setHostname] = React.useState('')
  const [os, setOs] = React.useState<'windows' | 'linux' | 'macos'>('linux')
  const [issuedToken, setIssuedToken] = React.useState<string | null>(null)
  const register = useRegisterEndpoint()

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    register.mutate(
      { name, hostname, os },
      { onSuccess: (data) => setIssuedToken(data.api_token) },
    )
  }

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      setName('')
      setHostname('')
      setIssuedToken(null)
      register.reset()
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="h-4 w-4" />
          Register endpoint
        </Button>
      </DialogTrigger>
      <DialogContent>
        {issuedToken ? (
          <>
            <DialogHeader>
              <DialogTitle>Endpoint registered</DialogTitle>
            </DialogHeader>
            <p className="mb-2 text-sm text-muted-foreground">
              Copy this API token into the agent's <code className="rounded bg-muted px-1">.env</code> as{' '}
              <code className="rounded bg-muted px-1">DATASENTINEL_ENDPOINT_TOKEN</code>. It will not be
              shown again.
            </p>
            <code className="block break-all rounded-md bg-muted p-3 text-xs">{issuedToken}</code>
            <Button className="mt-4 w-full" variant="outline" onClick={() => handleOpenChange(false)}>
              Done
            </Button>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Register a new endpoint</DialogTitle>
            </DialogHeader>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-1.5">
                <Label htmlFor="ep-name">Display name</Label>
                <Input id="ep-name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="WIN-LAPTOP-023" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ep-hostname">Hostname</Label>
                <Input id="ep-hostname" required value={hostname} onChange={(e) => setHostname(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Operating system</Label>
                <Select value={os} onValueChange={(value) => setOs(value as 'windows' | 'linux' | 'macos')}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="linux">Linux</SelectItem>
                    <SelectItem value="windows">Windows</SelectItem>
                    <SelectItem value="macos">macOS</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {register.isError && <p className="text-sm text-destructive">Registration failed. Try a different hostname.</p>}
              <Button type="submit" className="w-full" disabled={register.isPending}>
                {register.isPending ? 'Registering…' : 'Register'}
              </Button>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
