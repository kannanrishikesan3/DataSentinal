import * as React from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useLogin } from '@/api/auth'
import { Logo } from '@/components/logo'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/lib/auth-context'

export function LoginPage() {
  const { isAuthenticated, refresh } = useAuth()
  const navigate = useNavigate()
  const login = useLogin()
  const [email, setEmail] = React.useState('')
  const [password, setPassword] = React.useState('')

  if (isAuthenticated) return <Navigate to="/" replace />

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    login.mutate(
      { email, password },
      {
        onSuccess: () => {
          refresh()
          navigate('/')
        },
      },
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-sidebar px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-sidebar-accent">
            <Logo className="h-6 w-6 text-sidebar-accent-foreground" cutoutColor="var(--sidebar-accent)" />
          </div>
          <h1 className="text-lg font-semibold text-sidebar-foreground">DataSentinel</h1>
          <p className="mt-1 text-sm text-sidebar-muted-foreground">Discover. Classify. Protect.</p>
        </div>

        <Card className="border-sidebar-border bg-card shadow-lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-center text-sm text-muted-foreground">Sign in to your account</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit} noValidate>
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  autoFocus
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="analyst@yourorg.com"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
              {login.isError && (
                <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
                  Invalid email or password.
                </p>
              )}
              <Button type="submit" className="w-full" disabled={login.isPending}>
                {login.isPending ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
