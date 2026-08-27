import { AlertTriangle, Cpu, FileWarning, KeyRound, ShieldAlert, Users } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { useDashboardOverview } from '@/api/dashboard'
import { SEVERITY_CHART_COLORS, SEVERITY_ORDER } from '@/components/severity-badge'
import { Card, CardContent, CardHeader, CardTitle, CardValue } from '@/components/ui/card'
import { PageError, PageSkeleton } from '@/components/page-states'

const SEVERITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  informational: 'Informational',
}

const CHART_ACCENT = 'var(--primary)'

export function OverviewPage() {
  const { data, isLoading, isError, error, refetch } = useDashboardOverview()

  if (isLoading) return <PageSkeleton />
  if (isError || !data) return <PageError error={error} onRetry={refetch} />

  const severityData = SEVERITY_ORDER.map((severity) => ({
    severity,
    label: SEVERITY_LABELS[severity],
    count: data.findings_by_severity[severity] ?? 0,
  }))

  const categoryData = Object.entries(data.findings_by_category)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([category, count]) => ({ category, count }))

  const endpointData = Object.entries(data.findings_by_endpoint)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([endpoint, count]) => ({ endpoint, count }))

  const fileTypeData = Object.entries(data.findings_by_file_type)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([fileType, count]) => ({ fileType, count }))

  const overTimeData = data.findings_over_time.map((point) => ({
    date: point.date,
    count: point.count,
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Overview</h1>
        <p className="text-sm text-muted-foreground">Organization-wide risk posture across all endpoints.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        <StatTile icon={Cpu} label="Endpoints" value={data.endpoints_total} />
        <StatTile icon={FileWarning} label="Files Scanned" value={data.files_scanned_total} />
        <StatTile icon={Users} label="PII Findings" value={data.pii_findings_total} />
        <StatTile icon={KeyRound} label="Secrets" value={data.secret_findings_total} />
        <StatTile icon={ShieldAlert} label="Critical" value={data.critical_findings} accent="text-severity-critical" />
        <StatTile icon={AlertTriangle} label="High" value={data.high_findings} accent="text-severity-high" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Findings by severity">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={severityData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border" />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {severityData.map((entry) => (
                  <Cell key={entry.severity} fill={SEVERITY_CHART_COLORS[entry.severity]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Findings by category">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={categoryData} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} className="stroke-border" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
              <YAxis
                dataKey="category"
                type="category"
                width={100}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="count" fill={CHART_ACCENT} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Findings by endpoint" className="lg:col-span-2">
          {endpointData.length === 0 ? (
            <EmptyChartState />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={endpointData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border" />
                <XAxis dataKey="endpoint" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="count" fill={CHART_ACCENT} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Findings by file type">
          {fileTypeData.length === 0 ? (
            <EmptyChartState />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={fileTypeData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border" />
                <XAxis dataKey="fileType" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="count" fill={CHART_ACCENT} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Findings over time">
          {overTimeData.length === 0 ? (
            <EmptyChartState />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={overTimeData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border" />
                <XAxis dataKey="date" tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
                <Tooltip content={<ChartTooltip />} />
                <Line type="monotone" dataKey="count" stroke={CHART_ACCENT} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>
    </div>
  )
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-1.5 text-xs text-popover-foreground shadow-md">
      <p className="font-medium">{label}</p>
      <p className="text-muted-foreground">{payload[0].value.toLocaleString()} findings</p>
    </div>
  )
}

function StatTile({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: number
  accent?: string
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-0">
        <CardTitle>{label}</CardTitle>
        <Icon className={`h-4 w-4 text-muted-foreground ${accent ?? ''}`} />
      </CardHeader>
      <CardContent>
        <CardValue className={accent}>{value.toLocaleString()}</CardValue>
      </CardContent>
    </Card>
  )
}

function ChartCard({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function EmptyChartState() {
  return <p className="py-10 text-center text-sm text-muted-foreground">No data yet — run a scan to populate this chart.</p>
}
