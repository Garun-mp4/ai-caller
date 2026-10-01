import { expect, test, type Page, type Route } from '@playwright/test';

const futureIso = (days = 2) => new Date(Date.now() + days * 86_400_000).toISOString();
const pastIso = () => new Date(Date.now() - 86_400_000).toISOString();

type LeadMock = { id: number; phone: string; name: string | null; company: string | null; notes: string; status: string; result: string | null; attempts: number; created_at: string; updated_at: string; next_call_at: string | null; last_call_at: string | null };
type CallbackMock = { id: number; lead_id: number; call_id: number | null; reason: string; scheduled_at: string; status: string; created_at: string; phone: string; company: string | null };
type TranscriptMock = { id: number; role: string; content: string; timestamp: string };
type CallMock = { id: number; lead_id: number; campaign_id: number | null; phone: string; started_at: string; answered_at: string | null; ended_at: string | null; duration: number; status: string; result: string | null; summary: string; stt_ms: number; llm_ms: number; tts_ms: number; total_ms: number; transcripts: TranscriptMock[] };
type CampaignMock = { id: number; name: string; description: string; agent_prompt: string; status: string; metrics: Record<string, number> };
type SettingsMock = { values: Record<string, string>; providers: Record<string, string> };
type MockRequest = { method: string; path: string; search: string; body?: Record<string, unknown> };
type MockState = { requests: MockRequest[]; leads: LeadMock[]; callbacks: CallbackMock[]; calls: CallMock[]; campaigns: CampaignMock[]; settings: SettingsMock };

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

async function fulfillJson(route: Route, value: unknown, status = 200) {
  const origin = route.request().headers().origin || 'http://127.0.0.1:3117';
  await route.fulfill({
    status,
    contentType: 'application/json',
    headers: {
      'access-control-allow-origin': origin,
      'access-control-allow-credentials': 'true',
      'access-control-allow-headers': 'authorization,content-type',
      'access-control-allow-methods': 'GET,POST,PATCH,PUT,OPTIONS',
    },
    body: JSON.stringify(value),
  });
}

async function mockApi(page: Page, options: { invalidLogin?: boolean } = {}): Promise<MockState> {
  const requests: MockRequest[] = [];
  const leads: LeadMock[] = [
    { id: 42, phone: '+79991112233', name: 'Анна', company: 'Альфа', notes: 'Позвонить после обеда', status: 'CALLBACK', result: null, attempts: 2, created_at: futureIso(-20), updated_at: futureIso(-1), next_call_at: futureIso(1), last_call_at: futureIso(-2) },
    { id: 43, phone: '+79992223344', name: null, company: 'Бета', notes: '', status: 'HOT_LEAD', result: 'Interested', attempts: 1, created_at: futureIso(-3), updated_at: futureIso(-1), next_call_at: null, last_call_at: futureIso(-1) },
  ];
  const callbacks: CallbackMock[] = [
    { id: 5, lead_id: 42, call_id: 1, reason: 'Уточнить сроки', scheduled_at: futureIso(2), status: 'SCHEDULED', created_at: futureIso(-1), phone: '+79991112233', company: 'Альфа' },
    { id: 6, lead_id: 43, call_id: null, reason: 'Обсудить предложение', scheduled_at: pastIso(), status: 'DUE', created_at: futureIso(-3), phone: '+79992223344', company: 'Бета' },
    { id: 7, lead_id: 43, call_id: null, reason: 'Больше не актуально', scheduled_at: futureIso(-2), status: 'CANCELED', created_at: futureIso(-4), phone: '+79992223344', company: 'Бета' },
  ];
  const calls: CallMock[] = [
    { id: 1, lead_id: 42, campaign_id: 1, phone: '+79991112233', started_at: futureIso(-1), answered_at: futureIso(-1), ended_at: futureIso(-1), duration: 104, status: 'COMPLETED', result: 'INTERESTED', summary: 'Договорились прислать предложение.', stt_ms: 180, llm_ms: 320, tts_ms: 210, total_ms: 710, transcripts: [{ id: 1, role: 'assistant', content: 'Добрый день! Удобно говорить?', timestamp: futureIso(-1) }, { id: 2, role: 'user', content: 'Да, расскажите подробнее.', timestamp: futureIso(-1) }] },
    { id: 2, lead_id: 43, campaign_id: 1, phone: '+79992223344', started_at: futureIso(-2), answered_at: null, ended_at: futureIso(-2), duration: 35, status: 'NO_ANSWER', result: 'No answer', summary: 'Абонент не ответил.', stt_ms: 0, llm_ms: 0, tts_ms: 0, total_ms: 0, transcripts: [] },
  ];
  const campaigns: CampaignMock[] = [{ id: 1, name: 'Первичный контакт', description: 'Знакомство с потенциальными клиентами', agent_prompt: '', status: 'DRAFT', metrics: { total: 2, queued: 1, calling: 0, answered: 1, no_answer: 1, interested: 1, hot_leads: 1 } }];
  const settings: SettingsMock = {
    values: { agent_name: 'Алекс', company_name: 'Веб-студия', what_we_sell: 'Создание и улучшение сайтов', introduction: 'Добрый день! Можно задать короткий вопрос?', offer: 'Разработка сайтов', allowed_claims: 'Проверенные сведения', forbidden_claims: 'Не придумывать цены', call_objective: 'Договориться о следующем шаге', max_response_length: '3', calling_hours: '09:00-18:00', timezone: 'Europe/Astrakhan', max_attempts: '3', delay_between_attempts: '30', max_concurrent_calls: '1', vosk_model_path: '', piper_model_path: '', llm_provider: 'mock', llm_model: 'mock', reasoning_effort: 'low' },
    providers: { auth_mode: 'local', llm_provider: 'mock', telephony_provider: 'mock', stt_provider: 'vosk', tts_provider: 'piper' },
  };
  const health = { llm: { ok: true, provider: 'mock', detail: 'Тестовый провайдер отвечает' }, telephony: { ok: true, provider: 'mock', detail: 'Тестовые звонки включены' }, stt: { ok: false, provider: 'vosk', detail: 'Модель не настроена' }, tts: { ok: false, provider: 'piper', detail: { python: false, binary: false, model: '' } }, codex_on_path: false };
  let imported = false;

  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const path = url.pathname.replace(/^\/api/, '') || '/';
    if (method === 'OPTIONS') {
      const origin = request.headers().origin || 'http://127.0.0.1:3117';
      await route.fulfill({ status: 204, headers: { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true', 'access-control-allow-headers': 'authorization,content-type', 'access-control-allow-methods': 'GET,POST,PATCH,PUT,OPTIONS' } });
      return;
    }
    let rawBody: unknown;
    try { rawBody = request.postDataJSON(); } catch { rawBody = undefined; }
    const body = asRecord(rawBody) || {};
    requests.push({ method, path, search: url.search, body: rawBody === undefined ? undefined : body });

    if (path === '/auth/config' && method === 'GET') return fulfillJson(route, { mode: 'local', chatgpt_oauth_available: false });
    if (path === '/auth/login' && method === 'POST') return options.invalidLogin ? fulfillJson(route, { detail: 'Invalid credentials' }, 401) : fulfillJson(route, { access_token: 'test-token', token_type: 'bearer', user: 'admin' });
    if (path === '/providers/health' && method === 'GET') return fulfillJson(route, health);
    if (path === '/dashboard' && method === 'GET') return fulfillJson(route, {
      stats: { total_leads: leads.length, calls_today: 3, answered: 2, interested: 1, hot_leads: 1, callbacks: 2, no_answer: 1 },
      recent_calls: calls.slice(0, 1),
      callbacks: callbacks.filter(item => ['SCHEDULED', 'DUE'].includes(item.status)).slice(0, 2),
    });

    if (path === '/leads/import' && method === 'POST') {
      if (!imported) { imported = true; const createdAt = new Date().toISOString(); leads.unshift({ id: 44, phone: '+79994445566', name: null, company: 'Новая компания', notes: '', status: 'NEW', result: null, attempts: 0, created_at: createdAt, updated_at: createdAt, next_call_at: null, last_call_at: null }); }
      return fulfillJson(route, { imported: 1, duplicates: 1, invalid: 1 });
    }
    if (path === '/leads' && method === 'GET') {
      const status = url.searchParams.get('status');
      const query = (url.searchParams.get('search') || '').toLocaleLowerCase('ru-RU');
      let filtered = leads.filter(lead => (!status || lead.status === status) && (!query || `${lead.company || ''} ${lead.phone}`.toLocaleLowerCase('ru-RU').includes(query)));
      if (url.searchParams.get('campaign')) filtered = filtered.filter(lead => lead.id !== 44);
      return fulfillJson(route, filtered);
    }
    const leadMatch = path.match(/^\/leads\/(\d+)$/);
    if (leadMatch && method === 'GET') {
      const lead = leads.find(item => item.id === Number(leadMatch[1]));
      if (!lead) return fulfillJson(route, { detail: 'Lead not found' }, 404);
      return fulfillJson(route, { lead, calls: calls.filter(item => item.lead_id === lead.id), callbacks: callbacks.filter(item => item.lead_id === lead.id) });
    }
    if (leadMatch && method === 'PATCH') {
      const lead = leads.find(item => item.id === Number(leadMatch[1]));
      if (!lead) return fulfillJson(route, { detail: 'Lead not found' }, 404);
      if (typeof body.notes === 'string') lead.notes = body.notes;
      if (typeof body.status === 'string') lead.status = body.status;
      if (body.status === 'DO_NOT_CALL') {
        lead.next_call_at = null;
        callbacks.filter(item => item.lead_id === lead.id && ['SCHEDULED', 'DUE'].includes(item.status)).forEach(item => { item.status = 'CANCELED'; });
      }
      return fulfillJson(route, lead);
    }
    const leadCallback = path.match(/^\/leads\/(\d+)\/callback$/);
    if (leadCallback && method === 'POST') {
      const lead = leads.find(item => item.id === Number(leadCallback[1]));
      if (!lead) return fulfillJson(route, { detail: 'Lead not found' }, 404);
      const item: CallbackMock = { id: 9, lead_id: Number(leadCallback[1]), call_id: null, reason: typeof body.reason === 'string' ? body.reason : 'Обратный звонок', scheduled_at: typeof body.scheduled_at === 'string' ? body.scheduled_at : futureIso(), status: 'SCHEDULED', created_at: new Date().toISOString(), phone: lead.phone, company: lead.company };
      callbacks.unshift(item); lead.status = 'CALLBACK'; lead.next_call_at = item.scheduled_at;
      return fulfillJson(route, item);
    }
    const leadCall = path.match(/^\/leads\/(\d+)\/call-now$/);
    if (leadCall && method === 'POST') {
      const lead = leads.find(item => item.id === Number(leadCall[1]));
      if (!lead) return fulfillJson(route, { detail: 'Lead not found' }, 404);
      const item = { ...calls[0], id: 10, lead_id: Number(leadCall[1]), phone: lead.phone, status: 'STARTING', started_at: new Date().toISOString(), result: null, summary: 'Звонок создан.', transcripts: [] };
      calls.unshift(item); return fulfillJson(route, item);
    }

    if (path === '/campaigns' && method === 'GET') return fulfillJson(route, campaigns);
    if (path === '/campaigns' && method === 'POST') {
      const item: CampaignMock = { id: campaigns.length + 1, name: String(body.name || ''), description: String(body.description || ''), agent_prompt: String(body.agent_prompt || ''), status: 'DRAFT', metrics: { total: 0, queued: 0, calling: 0, answered: 0, no_answer: 0, interested: 0, hot_leads: 0 } };
      campaigns.unshift(item); return fulfillJson(route, item);
    }
    const campaignAction = path.match(/^\/campaigns\/(\d+)\/(attach-all|start|pause|stop)$/);
    if (campaignAction && method === 'POST') {
      const campaign = campaigns.find(item => item.id === Number(campaignAction[1]));
      if (!campaign) return fulfillJson(route, { detail: 'Campaign not found' }, 404);
      if (campaignAction[2] === 'attach-all') return fulfillJson(route, { attached: 2 });
      if (campaignAction[2] === 'start') campaign.status = 'RUNNING';
      if (campaignAction[2] === 'pause') campaign.status = 'PAUSED';
      if (campaignAction[2] === 'stop') campaign.status = 'STOPPED';
      return fulfillJson(route, campaign);
    }
    if (path === '/scheduler/tick' && method === 'POST') return fulfillJson(route, { processed: 1 });

    if (path === '/callbacks' && method === 'GET') return fulfillJson(route, callbacks);
    const callbackMatch = path.match(/^\/callbacks\/(\d+)$/);
    if (callbackMatch && method === 'PATCH') {
      const callback = callbacks.find(item => item.id === Number(callbackMatch[1]));
      if (!callback) return fulfillJson(route, { detail: 'Callback not found' }, 404);
      if (typeof body.status === 'string') callback.status = body.status;
      if (typeof body.scheduled_at === 'string') callback.scheduled_at = body.scheduled_at;
      if (typeof body.reason === 'string') callback.reason = body.reason;
      return fulfillJson(route, callback);
    }
    if (path === '/calls' && method === 'GET') return fulfillJson(route, calls);
    if (path === '/settings' && method === 'GET') return fulfillJson(route, settings);
    if (path === '/settings' && method === 'PUT') { settings.values = Object.fromEntries(Object.entries(body).map(([key, value]) => [key, String(value)])); return fulfillJson(route, { ok: true }); }

    return fulfillJson(route, { detail: `Unhandled mock route: ${method} ${path}` }, 500);
  });
  return { requests, leads, callbacks, calls, campaigns, settings };
}

async function enterWorkspace(page: Page): Promise<MockState> {
  await page.addInitScript(() => localStorage.setItem('token', 'test-token'));
  return mockApi(page);
}

test('login translates authentication errors and keeps the operator on the sign-in screen', async ({ page }) => {
  await mockApi(page, { invalidLogin: true });
  await page.goto('/login');
  await page.getByLabel('Имя пользователя').fill('operator');
  await page.getByLabel('Пароль', { exact: true }).fill('incorrect');
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page.getByRole('region', { name: 'Рады видеть вас' }).getByRole('alert')).toContainText('Логин или пароль указаны неверно.');
  await expect(page).toHaveURL(/\/login$/);
});

test('successful sign-in loads service status after leaving the login route', async ({ page }) => {
  await mockApi(page);
  await page.goto('/login');
  await page.getByLabel('Имя пользователя').fill('operator');
  await page.getByLabel('Пароль', { exact: true }).fill('correct-password');
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText('Сервисы готовы')).toBeVisible();
});

test('protected workspace routes return an unauthenticated operator to sign-in', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Рады видеть вас' })).toBeVisible();
});

test('dashboard shows the operator overview and useful recent activity', async ({ page }) => {
  await enterWorkspace(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Обзор' })).toBeVisible();
  await expect(page.getByText('Всего лидов')).toBeVisible();
  await expect(page.getByText('Горячие лиды')).toBeVisible();
  await expect(page.getByText('+79991112233')).toBeVisible();
  await expect(page.getByText('Ближайшие задачи')).toBeVisible();
});

test('leads can be searched, filtered, imported, and paged without losing Russian labels', async ({ page }) => {
  const mocks = await enterWorkspace(page);
  await page.goto('/leads');
  await expect(page.getByRole('link', { name: 'Альфа' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Есть интерес' })).toBeVisible();
  const search = page.getByPlaceholder('Компания или телефон');
  await search.fill('Бета');
  await search.press('Enter');
  await expect(page.getByRole('link', { name: 'Бета' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Альфа' })).toHaveCount(0);
  await page.getByLabel('Фильтр по статусу').selectOption('HOT_LEAD');
  expect(mocks.requests.some(request => request.path === '/leads' && request.method === 'GET' && request.search.includes('status=HOT_LEAD'))).toBe(true);
  await page.locator('.table-actions').getByRole('button', { name: 'Сбросить фильтры' }).click();
  await search.fill('Несуществующая компания');
  await search.press('Enter');
  await expect(page.getByRole('heading', { name: 'Ничего не найдено' })).toBeVisible();
  await page.locator('.table-actions').getByRole('button', { name: 'Сбросить фильтры' }).click();
  await expect(page.getByRole('link', { name: 'Альфа' })).toBeVisible();
  await page.locator('#lead-import').setInputFiles({ name: 'contacts.txt', mimeType: 'text/plain', buffer: Buffer.from('ООО Тест,+79994445566\n') });
  await expect(page.getByRole('status').filter({ hasText: 'Импорт завершён: добавлено 1' })).toContainText('дубликатов 1, пропущено 1.');
  await expect(page.getByRole('link', { name: 'Новая компания' })).toBeVisible();
  for (let id = 100; id < 126; id += 1) {
    const base = mocks.leads[0];
    mocks.leads.push({ ...base, id, phone: `+7999000${String(id).padStart(4, '0')}`, company: `Компания ${id}`, status: 'NEW' });
  }
  await page.getByRole('button', { name: 'Найти' }).click();
  await expect(page.getByText('Страница 1 из 2')).toBeVisible();
  await page.getByRole('button', { name: 'Вперёд' }).click();
  await expect(page.getByText('Страница 2 из 2')).toBeVisible();
});

test('lead details save notes, schedule a callback, confirm a call, and protect DNC contacts', async ({ page }) => {
  const mocks = await enterWorkspace(page);
  await page.goto('/leads/42');
  await expect(page.getByRole('heading', { name: 'Альфа' })).toBeVisible();
  await page.getByLabel('Заметки').fill('Договорились вернуться в понедельник');
  await page.getByRole('button', { name: 'Сохранить заметки' }).click();
  await expect(page.getByRole('status')).toContainText('Заметки сохранены');

  await page.getByRole('button', { name: 'Назначить звонок' }).click();
  await page.getByRole('button', { name: 'Запланировать', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Обратный звонок запланирован');
  expect(mocks.requests.some(request => request.path === '/leads/42/callback' && request.method === 'POST')).toBe(true);

  await page.getByRole('button', { name: 'Позвонить' }).click();
  await expect(page.getByRole('button', { name: 'Отмена' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: 'Позвонить' }).click();
  await expect(page.getByRole('dialog')).toContainText('Проверьте номер перед запуском.');
  await page.getByRole('button', { name: 'Начать звонок' }).click();
  await expect(page.getByRole('status')).toContainText('Звонок добавлен');

  await page.getByRole('button', { name: 'Не звонить' }).click();
  await page.getByRole('button', { name: 'Включить запрет' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Запрет на звонки включён' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Позвонить' })).toBeDisabled();
  expect(mocks.leads[0].status).toBe('DO_NOT_CALL');
});

test('callbacks can be rescheduled, completed, and canceled', async ({ page }) => {
  const mocks = await enterWorkspace(page);
  await page.goto('/callbacks');
  await expect(page.getByRole('heading', { name: 'Обратные звонки' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Альфа' })).toBeVisible();
  await page.getByRole('button', { name: 'Перенести обратный звонок #5' }).click();
  await page.getByRole('button', { name: 'Сохранить время' }).click();
  await expect(page.getByRole('status')).toContainText('Новое время сохранено');
  expect(mocks.requests.some(request => request.path === '/callbacks/5' && request.method === 'PATCH' && request.body?.scheduled_at)).toBe(true);

  await page.getByRole('button', { name: 'Отметить обратный звонок #5 выполненным' }).click();
  await page.getByRole('button', { name: /Выполненные/ }).click();
  await expect(page.getByRole('cell', { name: 'Уточнить сроки' })).toBeVisible();

  await page.getByRole('button', { name: /Предстоящие/ }).click();
  await page.getByRole('button', { name: 'Отменить обратный звонок #6' }).click();
  await page.getByRole('button', { name: 'Отменить звонок' }).click();
  expect(mocks.callbacks.find(item => item.id === 6)?.status).toBe('CANCELED');
});

test('campaign creation requires compliance before start and confirms scheduler override', async ({ page }) => {
  const mocks = await enterWorkspace(page);
  await page.goto('/campaigns');
  await page.getByRole('button', { name: 'Новая кампания' }).click();
  await page.getByLabel('Название').fill('Проверка кампании');
  await page.getByLabel('Описание').fill('Новый сегмент операторской базы');
  await page.getByRole('button', { name: 'Создать кампанию' }).click();
  const campaignCard = page.locator('.campaign-card').filter({ hasText: 'Проверка кампании' });
  await expect(campaignCard).toBeVisible();
  const start = campaignCard.getByRole('button', { name: 'Запустить' });
  await expect(start).toBeDisabled();
  await campaignCard.getByRole('checkbox').check();
  await expect(start).toBeEnabled();
  await start.click();
  expect(mocks.requests.some(request => request.path.endsWith('/attach-all') && request.method === 'POST')).toBe(true);
  await expect.poll(() => mocks.requests.some(request => request.path.endsWith('/start') && request.body?.confirm_compliance === true)).toBe(true);
  await campaignCard.getByRole('button', { name: 'Приостановить' }).click();
  await campaignCard.getByRole('button', { name: 'Остановить' }).click();
  await page.getByRole('button', { name: 'Остановить кампанию' }).click();
  expect(mocks.campaigns.find(item => item.name === 'Проверка кампании')?.status).toBe('STOPPED');

  await page.getByRole('button', { name: 'Тестовый шаг' }).click();
  await expect(page.getByRole('dialog')).toContainText('обходит разрешённые часы звонков');
  await page.getByRole('button', { name: 'Запустить шаг' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Планировщик обработал звонков:' })).toContainText('Планировщик обработал звонков: 1');
});

test('calls can be filtered and the transcript stays attached to its call', async ({ page }) => {
  await enterWorkspace(page);
  await page.goto('/calls');
  await expect(page.getByRole('heading', { name: 'Звонки' })).toBeVisible();
  const call = page.locator('details.call-card').filter({ hasText: '+79991112233' });
  await call.locator('summary').click();
  await expect(call.getByText('Добрый день! Удобно говорить?')).toBeVisible();
  await expect(call.getByText('Собеседник')).toBeVisible();
  await page.getByLabel('Фильтр по результату').selectOption('NO_ANSWER');
  const noAnswer = page.locator('details.call-card').filter({ hasText: 'Абонент не ответил.' });
  await noAnswer.locator('summary').click();
  await expect(noAnswer.getByText('Абонент не ответил.')).toBeVisible();
  await expect(page.getByText('Добрый день! Удобно говорить?')).toHaveCount(0);
});

test('settings save changes and display provider health as clear statuses', async ({ page }) => {
  const mocks = await enterWorkspace(page);
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Настройки' })).toBeVisible();
  await expect(page.getByText('Состояние сервисов')).toBeVisible();
  await expect(page.getByText('Piper CLI: не настроен')).toBeVisible();
  await page.getByLabel('Имя агента').fill('Наталья');
  const save = page.getByRole('button', { name: 'Сохранить изменения' });
  await expect(save).toBeEnabled();
  await save.click();
  await expect(page.getByRole('status')).toContainText('Настройки сохранены');
  expect(mocks.settings.values.agent_name).toBe('Наталья');
  await expect(page.getByText('Доступен').first()).toBeVisible();
});

test('theme preference persists and mobile navigation fits the viewport', async ({ page }) => {
  await enterWorkspace(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/leads');
  await page.getByRole('button', { name: 'Включить тёмную тему' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('navigation', { name: 'Основная навигация' }).last()).toBeVisible();
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    const dimensions = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, viewport: window.innerWidth }));
    expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
  }
});
