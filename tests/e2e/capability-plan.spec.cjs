const { test, expect } = require('@playwright/test');

test('plan card supports versioned review without claiming implementation', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('region', { name: 'Capability planning' })).toBeVisible();
    await page.evaluate(() => {
        const socket = window.socket;
        socket.disconnect();
        socket.connected = true;
        window.planCalls = [];
        const plan = {
            title: 'Sample report', goal: 'Summarize sample data', kind: 'tool',
            steps: ['Parse sample'], risks: ['Incomplete input'], advantages: ['Repeatable report'],
            permissions: [], tests: ['Reject invalid input'], first_run: 'Synthetic data', rollback: 'Remove candidate'
        };
        let record;
        socket.timeout = () => ({ emit: (event, payload, callback) => {
            window.planCalls.push({ event, payload });
            if (event === 'capability_plan_request') {
                record = { id: 'sample-id', version: (record?.version || 0) + 1, status: 'pending',
                    content_hash: `hash-${(record?.version || 0) + 1}`, plan, execution_available: false };
            } else {
                record = { ...record, status: payload.action === 'approve' ? 'approved' : 'cancelled' };
            }
            socket.listeners('capability_plan').forEach((listener) => listener(record));
            callback(null, { ok: true, record });
        } });
    });
    const card = page.getByRole('region', { name: 'Capability planning' });
    await card.getByRole('textbox').fill('Create a sample report tool');
    await card.getByRole('button', { name: 'Draft plan', exact: true }).click();
    await expect(card.getByText('Sample report (tool)', { exact: true })).toBeVisible();
    await expect(card.getByRole('button', { name: 'Implement (unavailable)' })).toBeDisabled();
    await card.getByRole('button', { name: 'Approve plan v1' }).click();
    await expect(card.getByRole('heading', { name: /v1 — approved/ })).toBeVisible();
    await card.getByRole('textbox').fill('Add a second sample');
    await card.getByRole('button', { name: 'Edit and reassess' }).click();
    await expect(card.getByRole('button', { name: 'Approve plan v2' })).toBeEnabled();
    const calls = await page.evaluate(() => window.planCalls);
    expect(calls[1].payload).toEqual({ action: 'approve', plan_id: 'sample-id', version: 1, content_hash: 'hash-1' });
    expect(calls[2].payload).toEqual({ request: 'Add a second sample', plan_id: 'sample-id', version: 1 });
    await card.getByRole('button', { name: 'Cancel plan' }).click();
    await expect(card.getByRole('heading', { name: /v2 — cancelled/ })).toBeVisible();
});

test('disconnected plan request is not silently queued', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => window.socket.disconnect());
    const card = page.getByRole('region', { name: 'Capability planning' });
    await card.getByRole('textbox').fill('Create a report');
    await card.getByRole('button', { name: 'Draft plan', exact: true }).click();
    await expect(card.getByRole('alert')).toContainText('No request was sent');
});
