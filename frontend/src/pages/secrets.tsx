import { FindingsTable } from '@/components/findings-table'

export function SecretsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Secrets</h1>
        <p className="text-sm text-muted-foreground">
          API keys, credentials, and tokens found on disk. Evidence is always redacted — full values are never
          displayed.
        </p>
      </div>

      <FindingsTable filters={{ is_secret: true }} />
    </div>
  )
}
