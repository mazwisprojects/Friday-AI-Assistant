const { test, expect } = require('@playwright/test');

test('HUD loads without backend or camera access', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toBeVisible();
  await expect(page.getByText('SYS // TELEMETRY')).toBeVisible();
  await expect(page.getByText(/VISION \/\//)).toBeVisible();
  await expect(page.getByText(/SOURCE \/\//)).toBeVisible();
});


test('plan card reviews versions without claiming implementation', async ({ page }) => {
  await page.route('**/socket.io/**', route => route.abort());
  await page.goto('/');
  await page.evaluate(() => {
    const record = {
      id: 'sample-plan', version: 1, status: 'pending', content_hash: 'hash-1',
      execution_available: false,
      plan: { title: 'Sample report', goal: 'Summarize synthetic data', kind: 'tool',
        steps: ['Parse sample'], risks: ['Incomplete input'], advantages: ['Repeatable'],
        permissions: [], tests: ['Reject invalid input'], first_run: 'Synthetic data', rollback: 'Remove candidate' }
    };
    window.planRequests = [];
    window.socket.connected = true;
    window.socket.timeout = () => ({ emit(event, payload, callback) {
      window.planRequests.push({ event, payload });
      if (event === 'capability_plan_request') {
        record.version += 1;
        record.content_hash = `hash-${record.version}`;
        record.status = 'pending';
        record.plan.risks = ['Reassessed risk'];
      } else {
        record.status = payload.action === 'approve' ? 'approved' : 'cancelled';
      }
      callback(null, { ok: true, record: structuredClone(record) });
    } });
    window.socket.emitEvent(['capability_plan', record]);
  });
  const card = page.getByRole('region', { name: 'Capability planning' });
  await expect(card.getByText('Sample report (tool)')).toBeVisible();
  await expect(card.getByRole('button', { name: 'Implement (unavailable)' })).toBeDisabled();
  await card.getByRole('button', { name: 'Approve plan v1' }).click();
  await expect(card.getByRole('heading', { name: /v1.*approved/ })).toBeVisible();
  await card.getByRole('textbox').fill('Add invalid-input tests');
  await card.getByRole('button', { name: 'Edit and reassess' }).click();
  await expect(card.getByText('Reassessed risk')).toBeVisible();
  await card.getByRole('button', { name: 'Approve plan v2' }).click();
  const requests = await page.evaluate(() => window.planRequests);
  expect(requests[2].payload).toMatchObject({ version: 2, content_hash: 'hash-2', action: 'approve' });
  await card.getByRole('button', { name: 'Cancel plan' }).click();
  await expect(card.getByRole('heading', { name: /v2.*cancelled/ })).toBeVisible();
});

