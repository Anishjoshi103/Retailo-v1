import { expect, test } from '@playwright/test';

const ownerEmail = 'owner@retailo-demo.local';
const ownerPassword = 'Retailo-E2E-Password-2026';
const productName = 'E2E Test Product';
const productSku = 'E2E-TEST-001';

test('registration request can be submitted and shows the privacy-preserving response', async ({ page }) => {
  await page.goto('/auth/register');
  await page.getByLabel('Store or business name').fill('E2E Registration Store');
  await page.getByLabel('Work email').fill('e2e-registration@example.test');
  await page.getByLabel('Password', { exact: true }).fill('E2E-Registration-Password-2026');
  await page.getByLabel('Confirm password').fill('E2E-Registration-Password-2026');
  await page.getByRole('button', { name: 'Create workspace' }).click();
  await expect(page.getByRole('status')).toContainText('registration request was received');
});

test('owner can configure GST, create product, receive stock, split-pay sale, return, print, export and invite staff', async ({ page }) => {
  await page.goto('/auth/login');
  await page.getByLabel('Work email').fill(ownerEmail);
  await page.getByLabel('Password').fill(ownerPassword);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/$/);

  // Exercise branch GST state editing, then restore the demo branch's original state.
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Branches & GST' })).toBeVisible();
  const mainBranch = page.locator('article.card').filter({ hasText: 'Main Store' });
  const stateSelect = mainBranch.getByLabel('GST state');
  await stateSelect.selectOption('29');
  await mainBranch.getByRole('button', { name: 'Save' }).click();
  await expect(mainBranch.getByText('Saved')).toBeVisible();
  await stateSelect.selectOption('27');
  await mainBranch.getByRole('button', { name: 'Save' }).click();
  await expect(mainBranch.getByText('Saved')).toBeVisible();

  // Create a product through the real catalogue UI.
  await page.goto('/catalog');
  await page.getByRole('button', { name: 'Add product' }).click();
  await page.getByLabel('Product name').fill(productName);
  await page.getByLabel('SKU').fill(productSku);
  await page.getByLabel('Unit').selectOption('each');
  await page.getByLabel('HSN code').fill('19053100');
  await page.getByLabel('GST rate (%)').fill('5.00');
  await page.getByLabel('Selling price (₹)').fill('100.00');
  await page.getByLabel('Purchase price (₹)').fill('70.00');
  await page.getByRole('button', { name: 'Save product' }).click();
  await expect(page.getByText(productName)).toBeVisible();

  // Receive goods for the newly-created product.
  await page.goto('/purchases');
  await page.getByLabel('Saved supplier').selectOption({ label: 'Demo Wholesale Supplier' });
  await page.getByPlaceholder('Barcode, SKU or name').fill(productSku);
  await page.getByRole('button', { name: 'Find' }).click();
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await page.getByLabel('Quantity of ' + productName).fill('10');
  await page.getByLabel('Cost per unit of ' + productName).fill('70.00');
  await page.getByRole('button', { name: 'Receive goods' }).click();
  await expect(page.getByRole('heading', { name: 'Goods received' })).toBeVisible();

  // Make a split payment sale and retain the invoice id for return.
  await page.goto('/pos');
  await page.getByPlaceholder('Barcode, SKU or name').fill(productSku);
  await page.getByRole('button', { name: 'Find' }).click();
  await expect(page.getByText(productName)).toBeVisible();
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  const paymentRows = page.locator('.payment-row');
  await page.getByRole('button', { name: /Split payment/i }).click();
  await expect(paymentRows).toHaveCount(2);
  const firstPayment = paymentRows.nth(0);
  const secondPayment = paymentRows.nth(1);
  await firstPayment.locator('select').selectOption('cash');
  await firstPayment.locator('input').first().fill('50.00');
  await secondPayment.locator('select').selectOption('upi');
  await secondPayment.locator('input').first().fill('50.00');
  await page.getByRole('button', { name: 'Complete sale' }).click();
  await expect(page.getByRole('heading', { name: 'Sale complete' })).toBeVisible();
  const invoiceNumber = (await page.locator('.invoice-number').textContent())?.trim();
  expect(invoiceNumber).toBeTruthy();
  await page.getByRole('link', { name: 'View invoice' }).click();
  await expect(page.getByRole('heading', { name: invoiceNumber! })).toBeVisible();

  // Print control is wired to the browser print API.
  await page.evaluate(() => { (window as Window & { print: () => void }).print = () => { (window as Window & { __printed?: boolean }).__printed = true; }; });
  await page.getByRole('button', { name: 'Print' }).click();
  await expect.poll(() => page.evaluate(() => (window as Window & { __printed?: boolean }).__printed)).toBe(true);

  // Return part of the invoice; the application issues a cash-refund credit note.
  await page.getByRole('link', { name: 'Return items' }).click();
  await page.getByLabel('Quantity of ' + productName + ' to return').fill('1');
  await page.getByRole('button', { name: 'Issue credit note' }).click();
  await expect(page).toHaveURL(/\\/gst\\/credit-notes\\//);\n  await expect(page.getByRole('heading', { name: /CN-/ })).toBeVisible();

  // Reports render and CSV export produces a downloadable file.
  await page.goto('/reports/gst');
  await expect(page.getByRole('heading', { name: 'GST register' })).toBeVisible();
  const csvDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'This month' }).click();
  await expect(page.getByRole('button', { name: 'Download CSV' }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Download CSV' }).first().click();
  const download = await csvDownload;
  expect(download.suggestedFilename()).toMatch(/\.csv$/);

  // Owner can invite a staff member and assign at least one branch.
  await page.goto('/settings/staff');
  await page.getByLabel('Email').fill('e2e-cashier@example.test');
  await page.getByLabel('Name (optional)').fill('E2E Cashier');
  await page.getByLabel('Role').selectOption('cashier');
  await page.locator('fieldset.branches').getByText('Main Store').click();
  await page.getByRole('button', { name: 'Send invitation' }).click();
  await expect(page.getByText(/e2e-cashier@example\.test/)).toBeVisible();
});
