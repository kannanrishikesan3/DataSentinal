// Mirrors backend/datasentinel_backend/api/v1/schemas.py — keep in sync.

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'informational'

export type FindingStatus = 'open' | 'false_positive' | 'suppressed' | 'reopened'

export type ScanStatus = 'pending' | 'running' | 'completed' | 'cancelled' | 'failed' | 'timed_out'

export interface EndpointRecord {
  id: string
  name: string
  hostname: string
  os: string
  os_version: string | null
  agent_version: string | null
  status: string
  last_seen_at: string | null
  registered_at: string
  last_scan: string | null
  risk_score: number
  policy_id: string | null
}

export interface EndpointRegisterResponse {
  endpoint: EndpointRecord
  api_token: string
}

export interface PaginatedEndpoints {
  total: number
  items: EndpointRecord[]
}

export interface ScanRecord {
  id: string
  endpoint_id: string
  profile: string
  status: ScanStatus
  scan_paths: string[]
  started_at: string | null
  completed_at: string | null
  files_discovered: number
  files_scanned: number
  files_skipped: number
  pii_findings: number
  secret_findings: number
  severity_counts: Partial<Record<Severity, number>>
}

export interface PaginatedScans {
  total: number
  items: ScanRecord[]
}

export interface FindingRecord {
  id: string
  endpoint_id: string
  scan_id: string
  file_id: string | null
  file_path: string
  file_hash: string | null
  category: string
  is_secret: boolean
  severity: Severity
  confidence: number
  occurrence_count: number
  page_number: number | null
  line_number: number | null
  sheet_name: string | null
  detection_method: string
  redacted_evidence: string
  detected_at: string
  status: FindingStatus
}

export interface PaginatedFindings {
  total: number
  items: FindingRecord[]
}

export interface FindingsOverTimePoint {
  date: string
  count: number
}

export interface DashboardOverview {
  endpoints_total: number
  files_scanned_total: number
  pii_findings_total: number
  secret_findings_total: number
  critical_findings: number
  high_findings: number
  findings_by_severity: Partial<Record<Severity, number>>
  findings_by_category: Record<string, number>
  findings_by_endpoint: Record<string, number>
  findings_by_file_type: Record<string, number>
  findings_over_time: FindingsOverTimePoint[]
}

export interface AuditLogEntry {
  id: string
  actor_type: string
  actor_id: string | null
  action: string
  target_type: string | null
  target_id: string | null
  details: Record<string, unknown> | null
  created_at: string
}

export interface PaginatedAuditLogs {
  total: number
  items: AuditLogEntry[]
}

export interface PolicyRecord {
  id: string
  name: string
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in_minutes: number
}

export interface FindingListFilters {
  endpoint_id?: string
  scan_id?: string
  severity?: Severity
  category?: string
  status?: FindingStatus
  is_secret?: boolean
  file_type?: string
  detected_after?: string
  detected_before?: string
  q?: string
  limit?: number
  offset?: number
}

export interface ExclusionRuleRecord {
  id: string
  category: string | null
  path_pattern: string | null
  created_by: string
  reason: string
  created_at: string
}

export type EnrollmentTokenStatus = 'active' | 'expired' | 'revoked' | 'exhausted'

export interface EnrollmentTokenRecord {
  id: string
  name: string
  status: EnrollmentTokenStatus
  max_uses: number
  current_uses: number
  allowed_os: 'windows' | 'linux' | null
  expires_at: string
  created_at: string
  policy_id: string | null
}

export interface EnrollmentTokenCreateResponse {
  token: EnrollmentTokenRecord
  raw_token: string
}

export interface BulkImportRow {
  row: number
  name: string
  hostname: string
  status: 'created' | 'error'
  api_token: string | null
  error: string | null
}

export interface BulkImportResponse {
  created: number
  failed: number
  rows: BulkImportRow[]
}
