import { useCurrentUser } from '@/api/me'
import { PageError, PageSkeleton } from '@/components/page-states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/lib/auth-context'

export function SettingsPage() {
  const { data: user, isLoading, isError, error, refetch } = useCurrentUser()
  const { logout } = useAuth()

  return (
    <div className="max-w-lg space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">Your account and session.</p>
      </div>

      {isLoading && <PageSkeleton />}
      {isError && <PageError error={error} onRetry={refetch} />}

      {!isLoading && !isError && user && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Email</span>
              <span className="font-medium text-foreground">{user.email}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Role</span>
              <Badge variant="outline" className="capitalize">
                {user.role}
              </Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Organization ID</span>
              <span className="font-mono text-xs text-muted-foreground">{user.org_id}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Member since</span>
              <span className="text-foreground">{new Date(user.created_at).toLocaleDateString()}</span>
            </div>
            <Button variant="outline" className="w-full" onClick={logout}>
              Sign out
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
