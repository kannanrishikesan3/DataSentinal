import { expect, test, type Page } from '@playwright/test'

const CREDS = {
  admin: { email: 'admin@acme.example.com', password: 'correct horse battery staple' },
  analyst: { email: 'analyst@acme.example.com', password: 'correct horse battery staple' },
  viewer: { email: 'viewer@acme.example.com', password: 'correct horse battery staple' },
}

async function loginAs(page: Page, role: keyof typeof CREDS) {
  const { email, password } = CREDS[role]
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page).toHaveURL('/')
}

test.describe('RBAC — Policies page', () => {
  test('admin sees the create form and delete buttons', async ({ page }) => {
    await loginAs(page, 'admin')
    await page.goto('/policies')
    await expect(page.getByRole('heading', { name: 'New policy' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Delete' }).first()).toBeVisible()
    expect(await page.locator('body').innerText()).not.toContain('Only admins can create')
  })

  test('viewer sees neither the create form nor delete buttons', async ({ page }) => {
    await loginAs(page, 'viewer')
    await page.goto('/policies')
    await expect(page.getByText(/known test fixtures|kiosk-quick-scan/i)).toBeVisible()
    await expect(page.getByRole('heading', { name: 'New policy' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0)
    await expect(page.getByText('Only admins can create, edit, or delete policies.')).toBeVisible()
  })

  test('analyst also cannot create or delete a policy', async ({ page }) => {
    await loginAs(page, 'analyst')
    await page.goto('/policies')
    await expect(page.getByRole('heading', { name: 'New policy' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0)
  })
})

test.describe('RBAC — Finding detail dialog', () => {
  async function openFirstFinding(page: Page) {
    await page.goto('/findings')
    await page.getByRole('row').nth(1).click()
    await expect(page.getByRole('dialog')).toBeVisible()
  }

  test('viewer cannot change finding status or create an exclusion rule', async ({ page }) => {
    await loginAs(page, 'viewer')
    await openFirstFinding(page)
    await expect(page.getByText('Viewers cannot change findings.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Mark as false positive' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Suppress' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Create exclusion rule' })).toHaveCount(0)
  })

  test('analyst can change a finding status', async ({ page }) => {
    // Idempotent across repeated runs against the same seeded backend: the
    // finding may already be in any status from a prior run, so act on
    // whichever mutation button is currently offered rather than assuming a
    // fixed starting state, then verify via the dialog's own Status field
    // (button visibility toggles on status !== 'that value', which is an
    // asymmetric check — e.g. clicking "Reopen" sets status to 'reopened',
    // not 'open', so the button legitimately stays visible afterwards too).
    await loginAs(page, 'analyst')
    await openFirstFinding(page)

    const options: { button: string; expectedStatusText: string }[] = [
      { button: 'Mark as false positive', expectedStatusText: 'false positive' },
      { button: 'Suppress', expectedStatusText: 'suppressed' },
      { button: 'Reopen', expectedStatusText: 'reopened' },
    ]

    for (const { button, expectedStatusText } of options) {
      const locator = page.getByRole('button', { name: button })
      if (await locator.isVisible()) {
        await locator.click()
        await expect(page.locator('div.capitalize dd')).toHaveText(expectedStatusText)
        return
      }
    }
    throw new Error('No status-change button was visible for the analyst role')
  })
})

test.describe('RBAC — Endpoint policy assignment', () => {
  test('admin can assign a policy to an endpoint from the Endpoints page', async ({ page }) => {
    await loginAs(page, 'admin')
    await page.goto('/endpoints')
    await expect(page.getByText('FIN-LAPTOP-01').first()).toBeVisible()

    const policySelect = page.getByRole('combobox').last()
    await policySelect.click()
    await page.getByRole('option', { name: 'kiosk-quick-scan' }).click()

    await expect(page.getByRole('combobox').last()).toContainText('kiosk-quick-scan')
  })

  test('viewer sees the assigned policy as read-only text, not a select', async ({ page }) => {
    await loginAs(page, 'viewer')
    await page.goto('/endpoints')
    await expect(page.getByText('FIN-LAPTOP-01').first()).toBeVisible()
    // Viewer must not get an editable combobox on this page at all.
    await expect(page.getByRole('combobox')).toHaveCount(0)
  })
})
