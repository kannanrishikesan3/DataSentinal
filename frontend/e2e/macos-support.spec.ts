import { expect, test, type Page } from '@playwright/test'

const ADMIN = { email: 'admin@acme.example.com', password: 'correct horse battery staple' }

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(ADMIN.email)
  await page.getByLabel('Password').fill(ADMIN.password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page).toHaveURL('/')
}

test.describe('Phase 2 — macOS platform support', () => {
  test('Register endpoint dialog offers macOS as a selectable OS', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/endpoints')
    await page.getByRole('button', { name: 'Register endpoint' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()

    await page.getByRole('combobox').click()
    await expect(page.getByRole('option', { name: 'macOS' })).toBeVisible()
    await expect(page.getByRole('option', { name: 'Windows' })).toBeVisible()
    await expect(page.getByRole('option', { name: 'Linux' })).toBeVisible()
  })

  test('Registering a macOS endpoint succeeds and appears in the table', async ({ page }) => {
    // Endpoint hostnames are unique per org (backend UniqueConstraint), and
    // this test runs against a persistent seeded DB across repeated runs —
    // a fixed hostname would 409-conflict on the second run. A per-run
    // suffix keeps this idempotent.
    const hostname = `qa-macbook-${test.info().workerIndex}-${Date.now()}`

    await loginAsAdmin(page)
    await page.goto('/endpoints')
    await page.getByRole('button', { name: 'Register endpoint' }).click()

    await page.getByLabel('Display name').fill(hostname.toUpperCase())
    await page.getByLabel('Hostname').fill(hostname)
    await page.getByRole('combobox').click()
    await page.getByRole('option', { name: 'macOS' }).click()
    await page.getByRole('button', { name: 'Register' }).click()

    // Success view shows the issued API token — proves the backend accepted
    // os="macos" (the whole point of Phase 2's schema regex change).
    await expect(page.getByText('Endpoint registered')).toBeVisible()
    await page.getByRole('button', { name: 'Done' }).click()

    await expect(page.getByText(hostname.toUpperCase()).first()).toBeVisible()
    const row = page.getByRole('row').filter({ hasText: hostname.toUpperCase() })
    await expect(row).toContainText('macOS')
  })

  test('Create enrollment token dialog offers "macOS only" as an allowed-OS option', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/endpoints')
    await page.getByRole('button', { name: 'Create enrollment token' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()

    // Two comboboxes in this dialog — "Allowed OS" comes first in the form,
    // "Auto-assign policy" second.
    await page.getByRole('combobox').first().click()
    await expect(page.getByRole('option', { name: 'macOS only' })).toBeVisible()
  })
})
