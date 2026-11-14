// Optional headless UI regression; install Playwright outside the app dependencies.
// Requires a test account with an existing assistant plan. Never use a paid provider.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.VISIONARY_TEST_URL || 'http://127.0.0.1:5173';
assert(process.env.VISIONARY_TEST_USERNAME && process.env.VISIONARY_TEST_PASSWORD, 'Set synthetic test credentials');
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1180 } });
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    return ['http:', 'https:'].includes(url.protocol) && !['127.0.0.1', 'localhost'].includes(url.hostname)
      ? route.abort() : route.continue();
  });
  const login = await page.request.post(base + '/api/auth/login', { data: {
    username: process.env.VISIONARY_TEST_USERNAME, password: process.env.VISIONARY_TEST_PASSWORD,
  } });
  assert.equal(login.status(), 200);
  await page.addInitScript(token => {
    localStorage.setItem('token', token);
    localStorage.setItem('visionary_creation_mode', 'assistant');
  }, (await login.json()).access_token);
  const changes = [];
  page.on('request', request => {
    if (request.method() === 'PUT' && request.url().endsWith('/plan')) changes.push(request.postDataJSON());
  });
  await page.goto(base);
  await page.getByRole('button', { name: '编辑方案', exact: true }).click();
  // Assert the editor remains open; opening it must not fire an implicit submit.
  await page.getByRole('textbox', { name: '画面描述', exact: true }).fill('手动编辑回归：浅色背景贺卡');
  assert.equal(changes.length, 0);
  await page.getByRole('button', { name: '保存方案', exact: true }).click();
  await page.getByRole('button', { name: '编辑方案', exact: true }).waitFor();
  assert.equal(changes.length, 1);
  assert.equal(changes[0].plan.prompt, '手动编辑回归：浅色背景贺卡');
  assert.match(await page.locator('.plan-fields').innerText(), /手动编辑回归：浅色背景贺卡/);
  console.log('PASS: opening editor submits nothing; save submits one edited version.');
} finally {
  await browser.close();
}
