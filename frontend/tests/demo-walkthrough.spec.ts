// Full P1-8 demo walkthrough — CISO scenario
import { test, expect } from '@playwright/test'

const MOCK_SUMMARY = {
  intercepts_today: 42, intercepts_7d: 300, intercepts_30d: 1200,
  allow_count_today: 35, deny_count_today: 5, review_count_today: 2,
  deny_rate_today: 11.9, active_sessions: 3, pending_reviews: 2,
  active_agents: 4, active_policies: 7, top_tools: [], decisions_by_hour: [],
}
const MOCK_AUDIT = { events: [], total: 0, limit: 50, offset: 0 }
const MOCK_EMPTY: never[] = []

test.beforeEach(async ({ page }) => {
  await page.route('http://localhost:8001/dashboard/summary*', route =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_SUMMARY) }))
  await page.route('http://localhost:8001/audit-events*', route =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_AUDIT) }))
  await page.route('http://localhost:8001/policies*', route =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_EMPTY) }))
  await page.route('http://localhost:8001/warnings*', route =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_EMPTY) }))
  await page.route('http://localhost:8001/agents*', route =>
    route.fulfill({ status: 200, body: JSON.stringify(MOCK_EMPTY) }))
  await page.goto('/login')
  await page.evaluate(() => {
    sessionStorage.setItem('ac_auth', JSON.stringify({
      email: 'admin@aicontrol.dev', role: 'admin', token: 'demo-token',
    }))
  })
})

test.describe('P1-8 Demo Walkthrough', () => {

  test('1. Login via email OTP', async ({ page }) => {
    await page.route('**/auth/request-code', route =>
      route.fulfill({ status: 200, body: JSON.stringify({ message: 'Code sent' }) }))
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await page.fill('input[type="email"]', 'admin@aicontrol.dev')
    await page.click('button[type="submit"]')
    await expect(page.getByText('Check your email')).toBeVisible({ timeout: 10000 })
    await page.goto('/overview')
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  })

  test('2. Overview — stat cards visible, live feed running', async ({ page }) => {
    await page.goto('/overview')
    await expect(page.getByText('Intercepts today')).toBeVisible()
    await expect(page.getByText('Deny rate', { exact: true })).toBeVisible()
    await expect(page.getByText('Active sessions')).toBeVisible()
    await expect(page.getByText('Pending reviews', { exact: true })).toBeVisible()
    await expect(page.getByText('Live intercepts')).toBeVisible()
  })

  test('3. Audit Log — filter by deny, see results', async ({ page }) => {
    await page.goto('/audit-log')
    await expect(page.getByRole('heading', { name: 'Agent activity' })).toBeVisible()
    await page.selectOption('select', 'deny')
    await page.getByRole('button', { name: 'Apply' }).click()
    await expect(page.locator('select')).toHaveValue('deny')
  })

  test('4. Policies — table and drift warnings section visible', async ({ page }) => {
    await page.goto('/policies')
    await expect(page.getByRole('heading', { name: 'Policies' })).toBeVisible()
    await expect(page.getByText('New policy')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Policy Drift Warnings' })).toBeVisible()
  })

  test('5. Agents — registry visible', async ({ page }) => {
    await page.goto('/agents')
    await expect(page.getByRole('heading', { name: 'Agents' })).toBeVisible()
  })

  test('6. Enterprise features are locked (community install)', async ({ page }) => {
    await page.goto('/sessions')
    await expect(page.getByText('Sessions — Enterprise Feature')).toBeVisible({ timeout: 5000 })

    await page.goto('/reviews')
    await expect(page.getByText('Review Queue — Enterprise Feature')).toBeVisible({ timeout: 5000 })

    await page.goto('/health')
    await expect(page.getByText('OPA Health Monitor — Enterprise')).toBeVisible({ timeout: 5000 })

    await page.goto('/reports')
    await expect(page.getByText('Compliance Reports — Enterprise')).toBeVisible({ timeout: 5000 })
  })

  test('7. Sidebar — all nav sections visible', async ({ page }) => {
    await page.goto('/overview')
    await expect(page.getByText('Activity', { exact: true })).toBeVisible()
    await expect(page.getByText('Governance', { exact: true })).toBeVisible()
    await expect(page.getByText('Manual Reviews', { exact: true })).toBeVisible()
    await expect(page.getByText('Intelligence', { exact: true })).toBeVisible()
    await expect(page.getByText('Reports', { exact: true })).toBeVisible()
  })

  test('8. Settings — license and auth info visible', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByText('License')).toBeVisible()
    await expect(page.getByText('Authentication')).toBeVisible()
    await expect(page.getByText('Email OTP')).toBeVisible()
  })

  test('9. Logout redirects to login', async ({ page }) => {
    await page.goto('/overview')
    await page.getByText('admin@aicontrol.dev').click()
    await page.locator('[data-testid="logout-btn"]').click()
    await expect(page).toHaveURL(/\/login/)
  })

})
