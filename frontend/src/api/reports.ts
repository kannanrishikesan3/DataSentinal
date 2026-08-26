import { getStoredToken } from '@/lib/auth-storage'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/** Reports aren't always JSON (csv/html/text), so this bypasses the JSON
 * api-client and returns the raw body — used to drive a client-side
 * download rather than a TanStack Query cache entry. */
export async function fetchReport(scanId: string, format: 'text' | 'json' | 'csv' | 'html'): Promise<string> {
  const token = getStoredToken()
  const response = await fetch(`${API_BASE_URL}/api/v1/reports/${scanId}?format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch report: ${response.statusText}`)
  }
  return response.text()
}

export function downloadReport(scanId: string, format: 'text' | 'json' | 'csv' | 'html', content: string) {
  const extensions: Record<typeof format, string> = { text: 'txt', json: 'json', csv: 'csv', html: 'html' }
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `datasentinel-report-${scanId}.${extensions[format]}`
  link.click()
  URL.revokeObjectURL(url)
}
