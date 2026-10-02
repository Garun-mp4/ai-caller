'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { friendlyError, Header, Icon, Loading, Notice } from '@/components/UI';

type SettingsData = { values: Record<string, string>; providers: Record<string, string> };
type ProviderHealth = { ok?: boolean; provider?: unknown; detail?: unknown; model?: string; configured?: boolean };
type HealthData = { llm?: ProviderHealth; telephony?: ProviderHealth; tts?: ProviderHealth; stt?: ProviderHealth; codex_on_path?: boolean };

const agentFields = [
  { key: 'agent_name', label: 'Имя агента' },
  { key: 'company_name', label: 'Название компании' },
  { key: 'what_we_sell', label: 'Что предлагает компания', wide: true },
  { key: 'introduction', label: 'Первое приветствие', wide: true, multiline: true },
  { key: 'offer', label: 'Краткое предложение', wide: true, multiline: true },
  { key: 'allowed_claims', label: 'Что можно обещать', wide: true, multiline: true, hint: 'Указывайте только проверенные факты.' },
  { key: 'forbidden_claims', label: 'Что нельзя обещать', wide: true, multiline: true },
  { key: 'call_objective', label: 'Цель разговора', wide: true, multiline: true },
  { key: 'max_response_length', label: 'Максимум предложений в ответе', type: 'number', min: 1, max: 8 },
];
const callFields = [
  { key: 'calling_hours', label: 'Разрешённое время звонков', hint: 'Например, 09:00-18:00' },
  { key: 'timezone', label: 'Часовой пояс' },
  { key: 'max_attempts', label: 'Попыток на контакт', type: 'number', min: 1, max: 50 },
  { key: 'delay_between_attempts', label: 'Пауза между попытками (мин)', type: 'number', min: 1, max: 10080 },
  { key: 'max_concurrent_calls', label: 'Одновременных звонков', type: 'number', min: 1, max: 25 },
];
const providerRows = [
  ['llm', 'Модель диалога'], ['telephony', 'Телефония'], ['stt', 'Распознавание речи'], ['tts', 'Синтез речи'],
] as const;
const providerLabels: Record<string, string> = { mock: 'Тестовый режим', codex: 'Codex', twilio: 'Twilio', vosk: 'Vosk', piper: 'Piper' };
const healthDetailLabels: Record<string, string> = { python: 'Python', binary: 'Piper CLI', model: 'Модель' };

function Field({ id, label, value, onChange, hint, error, wide, multiline, type = 'text', min, max }: { id: string; label: string; value: string; onChange: (value: string) => void; hint?: string; error?: string; wide?: boolean; multiline?: boolean; type?: string; min?: number; max?: number }) {
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') || undefined;
  return <label className={`field${wide ? ' field-wide' : ''}`}>
    <span className="field-label">{label}</span>
    {multiline
      ? <textarea id={id} className="textarea" value={value || ''} onChange={event => onChange(event.target.value)} rows={3} aria-invalid={Boolean(error)} aria-describedby={describedBy}/>
      : <input id={id} className="input" type={type} value={value || ''} min={min} max={max} onChange={event => onChange(event.target.value)} aria-invalid={Boolean(error)} aria-describedby={describedBy}/>}
    {hint && <span id={`${id}-hint`} className="field-hint">{hint}</span>}
    {error && <span id={`${id}-error`} className="field-error" role="status">{error}</span>}
  </label>;
}

function providerLabel(value: unknown) {
  if (typeof value !== 'string' || !value) return 'Не указано';
  return providerLabels[value.toLowerCase()] || value;
}

function formatProviderDetail(value: unknown): string | null {
  if (typeof value === 'string') return value || null;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;

  const details = Object.entries(value as Record<string, unknown>).map(([key, item]) => {
    const label = healthDetailLabels[key] || key;
    if (typeof item === 'boolean') return `${label}: ${item ? 'доступен' : 'не настроен'}`;
    if (typeof item === 'string') {
      if (key === 'model') return `${label}: ${item.trim() ? item.split(/[\\/]/).filter(Boolean).at(-1) : 'не указана'}`;
      return `${label}: ${item || 'не указано'}`;
    }
    if (typeof item === 'number') return `${label}: ${item}`;
    return `${label}: не проверено`;
  });

  return details.length ? details.join(' · ') : null;
}

function validateSetting(key: string, value: string): string | null {
  const integerRanges: Record<string, { min: number; max: number }> = {
    max_response_length: { min: 1, max: 8 },
    max_attempts: { min: 1, max: 50 },
    delay_between_attempts: { min: 1, max: 10080 },
    max_concurrent_calls: { min: 1, max: 25 },
  };
  const maxLengths: Record<string, number> = {
    agent_name: 200, company_name: 300, what_we_sell: 2000, introduction: 4000,
    offer: 4000, allowed_claims: 4000, forbidden_claims: 4000, call_objective: 4000,
    vosk_model_path: 1024, piper_model_path: 1024, llm_model: 200,
  };

  if (key === 'agent_name' && !value.length) return 'Укажите имя агента.';
  if (maxLengths[key] && value.length > maxLengths[key]) return `Максимум ${maxLengths[key]} символов.`;

  const range = integerRanges[key];
  if (range) {
    if (!/^\d+$/.test(value)) return 'Введите целое число.';
    const number = Number(value);
    if (number < range.min || number > range.max) return `Допустимое значение: от ${range.min} до ${range.max}.`;
  }

  if (key === 'calling_hours') {
    const match = value.match(/^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$/);
    if (!match) return 'Введите время в формате ЧЧ:ММ-ЧЧ:ММ, например 09:00-18:00.';
    const start = Number(match[1]) * 60 + Number(match[2]);
    const end = Number(match[3]) * 60 + Number(match[4]);
    if (start >= end) return 'Время окончания должно быть позже времени начала.';
  }

  if (key === 'timezone') {
    if (!value) return 'Укажите часовой пояс.';
    try { new Intl.DateTimeFormat('ru-RU', { timeZone: value }).format(new Date()); }
    catch { return 'Укажите часовой пояс IANA, например Europe/Astrakhan.'; }
  }

  if (key === 'llm_provider' && !['mock', 'codex'].includes(value)) return 'Выберите доступный провайдер.';
  if (key === 'reasoning_effort' && !['low', 'medium', 'high', 'xhigh'].includes(value)) return 'Выберите доступный уровень рассуждений.';
  return null;
}

export default function Settings() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [initialValues, setInitialValues] = useState<Record<string, string>>({});
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [healthLoading, setHealthLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);

  const refreshHealth = useCallback(async () => {
    setHealthLoading(true);
    try { setHealth(await api<HealthData>('/providers/health')); }
    catch { setHealth(null); }
    finally { setHealthLoading(false); }
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    const settingsPromise = api<SettingsData>('/settings');
    const healthPromise = refreshHealth();
    const [settingsResult] = await Promise.allSettled([settingsPromise]);
    await healthPromise;
    if (settingsResult.status === 'fulfilled') {
      setData(settingsResult.value); setInitialValues(settingsResult.value.values);
    } else setError(friendlyError(settingsResult.reason));
    setLoading(false);
  }, [refreshHealth]);
  useEffect(() => { void load(); }, [load]);

  const isDirty = useMemo(() => JSON.stringify(data?.values || {}) !== JSON.stringify(initialValues), [data?.values, initialValues]);

  function setValue(key: string, value: string) {
    setData(current => current ? { ...current, values: { ...current.values, [key]: value } } : current);
    setValidationErrors(current => current[key] ? { ...current, [key]: validateSetting(key, value) || '' } : current);
    setFeedback(null);
  }

  async function save() {
    if (!data || !isDirty) return;
    const nextErrors = Object.fromEntries(Object.entries(data.values).flatMap(([key, value]) => {
      const validationError = validateSetting(key, value);
      return validationError ? [[key, validationError]] : [];
    }));
    setValidationErrors(nextErrors);
    const firstInvalidKey = Object.keys(nextErrors)[0];
    if (firstInvalidKey) {
      setFeedback({ tone: 'danger', text: 'Проверьте поля с ошибками.' });
      document.getElementById(`setting-${firstInvalidKey}`)?.focus();
      return;
    }
    setSaving(true); setFeedback(null); setError('');
    try {
      const changes = Object.fromEntries(Object.entries(data.values).filter(([key, value]) => initialValues[key] !== value));
      await api('/settings', { method: 'PUT', body: JSON.stringify(changes) });
      setInitialValues({ ...data.values });
      setFeedback({ tone: 'success', text: 'Настройки сохранены.' });
    } catch (requestError) { setFeedback({ tone: 'danger', text: friendlyError(requestError) }); }
    finally { setSaving(false); }
  }

  const settings = data?.values || {};
  const providers = data?.providers || {};

  return <>
    <Header title="Настройки" sub="Поведение AI-агента, правила звонков и локальные сервисы">
      <button type="button" className="btn btn-primary" onClick={save} disabled={!isDirty || saving || !data}><Icon name="save"/>{saving ? 'Сохраняем…' : 'Сохранить изменения'}</button>
    </Header>
    {feedback && <div className="feedback"><Notice tone={feedback.tone}>{feedback.text}</Notice></div>}
    {error && <div className="feedback"><Notice tone="danger">{error} <button className="btn btn-sm" onClick={load}>Повторить</button></Notice></div>}
    {loading ? <Loading text="Загружаем настройки…"/> : data && <div className="settings-layout">
      <div>
        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Стиль разговора</h2><p className="section-description">Факты и инструкции, на которые опирается агент</p></div><span className="metric-icon"><Icon name="spark"/></span></div>
          <div className="settings-fields">{agentFields.map(field => <Field key={field.key} id={`setting-${field.key}`} label={field.label} value={settings[field.key] || ''} onChange={value => setValue(field.key, value)} error={validationErrors[field.key]} hint={'hint' in field ? field.hint : undefined} wide={'wide' in field ? field.wide : false} multiline={'multiline' in field ? field.multiline : false} type={'type' in field ? field.type : undefined} min={'min' in field ? field.min : undefined} max={'max' in field ? field.max : undefined}/>)}</div>
        </section>
        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Правила звонков</h2><p className="section-description">Расписание и ограничения повторных попыток</p></div><span className="metric-icon"><Icon name="clock"/></span></div>
          <div className="settings-fields">{callFields.map(field => <Field key={field.key} id={`setting-${field.key}`} label={field.label} value={settings[field.key] || ''} onChange={value => setValue(field.key, value)} error={validationErrors[field.key]} hint={'hint' in field ? field.hint : undefined} type={'type' in field ? field.type : undefined} min={'min' in field ? field.min : undefined} max={'max' in field ? field.max : undefined}/>)}</div>
          <div className="notice notice-info" style={{ marginTop: 15 }}><Icon name="info"/><span>Часы звонков применяются планировщиком. Тестовый ручной шаг в разделе кампаний их обходит.</span></div>
        </section>
        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Модели и локальные файлы</h2><p className="section-description">После сохранения новые вызовы сразу используют обновлённые настройки.</p></div></div>
          <div className="settings-fields">
            <label className="field"><span className="field-label">Провайдер диалога</span><select id="setting-llm_provider" className="select" value={settings.llm_provider || 'mock'} onChange={event => setValue('llm_provider', event.target.value)} aria-invalid={Boolean(validationErrors.llm_provider)} aria-describedby={validationErrors.llm_provider ? 'setting-llm_provider-error' : undefined}><option value="mock">Тестовый режим</option><option value="codex">Codex</option></select>{validationErrors.llm_provider && <span id="setting-llm_provider-error" className="field-error" role="status">{validationErrors.llm_provider}</span>}</label>
            <Field id="setting-llm_model" label="Модель диалога" value={settings.llm_model || ''} onChange={value => setValue('llm_model', value)} error={validationErrors.llm_model}/>
            <label className="field"><span className="field-label">Уровень рассуждений</span><select id="setting-reasoning_effort" className="select" value={settings.reasoning_effort || 'low'} onChange={event => setValue('reasoning_effort', event.target.value)} aria-invalid={Boolean(validationErrors.reasoning_effort)} aria-describedby={validationErrors.reasoning_effort ? 'setting-reasoning_effort-error' : undefined}><option value="low">Низкий</option><option value="medium">Средний</option><option value="high">Высокий</option><option value="xhigh">Очень высокий</option></select>{validationErrors.reasoning_effort && <span id="setting-reasoning_effort-error" className="field-error" role="status">{validationErrors.reasoning_effort}</span>}</label>
            <Field id="setting-vosk_model_path" label="Путь к модели распознавания (Vosk)" value={settings.vosk_model_path || ''} onChange={value => setValue('vosk_model_path', value)} error={validationErrors.vosk_model_path} wide hint="Путь на компьютере, где запущен backend."/>
            <Field id="setting-piper_model_path" label="Путь к модели голоса (Piper)" value={settings.piper_model_path || ''} onChange={value => setValue('piper_model_path', value)} error={validationErrors.piper_model_path} wide hint="Путь на компьютере, где запущен backend."/>
          </div>
        </section>
      </div>

      <aside>
        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Состояние сервисов</h2><p className="section-description">{healthLoading ? 'Проверяем подключение…' : 'Проверка при последнем обновлении'}</p></div><span className={`status-dot ${health ? 'is-ready' : ''}`} aria-label={healthLoading ? 'Проверяется' : health ? 'Проверено' : 'Нет данных'}/></div>
          {health ? <>
            {providerRows.map(([key, label]) => {
              const provider = health[key];
              const configuredProvider = provider?.provider ?? providers[`${key}_provider`] ?? settings.llm_provider;
              const detail = formatProviderDetail(provider?.detail);
              return <div className="provider-card" key={key}><div className="provider-card-top"><strong>{label}</strong><span className={`badge ${provider?.ok ? 'badge-success' : 'badge-danger'}`}>{provider?.ok ? 'Доступен' : 'Проверить'}</span></div><div className="provider-card-value">{providerLabel(configuredProvider)}</div><div className="field-hint">{provider?.ok ? (detail || 'Сервис отвечает.') : (detail || 'Проверьте конфигурацию и журнал backend.')}</div></div>;
            })}
            <div className="provider-row"><dt>Codex CLI</dt><dd><span className={`badge ${health.codex_on_path ? 'badge-success' : 'badge-neutral'}`}>{health.codex_on_path ? 'Доступен' : 'Не найден'}</span></dd></div>
          </> : <Notice tone="warning">Не удалось получить состояние провайдеров. Проверьте сервер или попробуйте обновить страницу.</Notice>}
          <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={refreshHealth} disabled={healthLoading}><Icon name="refresh"/>{healthLoading ? 'Проверяем…' : 'Проверить снова'}</button>
        </section>

        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Рабочее пространство</h2><p className="section-description">Общие параметры приложения</p></div></div>
          <dl>
            <div className="provider-row"><dt>Вход</dt><dd>{providerLabel(providers.auth_mode)}</dd></div>
            <div className="provider-row"><dt>Телефония</dt><dd>{providerLabel(providers.telephony_provider)}</dd></div>
            <div className="provider-row"><dt>Распознавание речи</dt><dd>{providerLabel(providers.stt_provider)}</dd></div>
            <div className="provider-row"><dt>Озвучивание</dt><dd>{providerLabel(providers.tts_provider)}</dd></div>
          </dl>
          <div className="notice notice-info" style={{ marginTop: 12 }}><Icon name="shield"/><span>Ключи и пароли здесь не отображаются. Тему можно переключить кнопкой в верхней панели.</span></div>
        </section>
      </aside>
    </div>}
  </>;
}
