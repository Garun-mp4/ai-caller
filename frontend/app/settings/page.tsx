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

function Field({ label, value, onChange, hint, wide, multiline, type = 'text', min, max }: { label: string; value: string; onChange: (value: string) => void; hint?: string; wide?: boolean; multiline?: boolean; type?: string; min?: number; max?: number }) {
  return <label className={`field${wide ? ' field-wide' : ''}`}>
    <span className="field-label">{label}</span>
    {multiline
      ? <textarea className="textarea" value={value || ''} onChange={event => onChange(event.target.value)} rows={3}/>
      : <input className="input" type={type} value={value || ''} min={min} max={max} onChange={event => onChange(event.target.value)}/>}
    {hint && <span className="field-hint">{hint}</span>}
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

export default function Settings() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [initialValues, setInitialValues] = useState<Record<string, string>>({});
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    const [settingsResult, healthResult] = await Promise.allSettled([api<SettingsData>('/settings'), api<HealthData>('/providers/health')]);
    if (settingsResult.status === 'fulfilled') {
      setData(settingsResult.value); setInitialValues(settingsResult.value.values);
    } else setError(friendlyError(settingsResult.reason));
    if (healthResult.status === 'fulfilled') setHealth(healthResult.value);
    else setHealth(null);
    setLoading(false);
  }, []);
  useEffect(() => { void load(); }, [load]);

  const isDirty = useMemo(() => JSON.stringify(data?.values || {}) !== JSON.stringify(initialValues), [data?.values, initialValues]);

  function setValue(key: string, value: string) {
    setData(current => current ? { ...current, values: { ...current.values, [key]: value } } : current);
    setFeedback(null);
  }

  async function save() {
    if (!data || !isDirty) return;
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
          <div className="settings-fields">{agentFields.map(field => <Field key={field.key} label={field.label} value={settings[field.key] || ''} onChange={value => setValue(field.key, value)} hint={'hint' in field ? field.hint : undefined} wide={'wide' in field ? field.wide : false} multiline={'multiline' in field ? field.multiline : false} type={'type' in field ? field.type : undefined} min={'min' in field ? field.min : undefined} max={'max' in field ? field.max : undefined}/>)}</div>
        </section>
        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Правила звонков</h2><p className="section-description">Расписание и ограничения повторных попыток</p></div><span className="metric-icon"><Icon name="clock"/></span></div>
          <div className="settings-fields">{callFields.map(field => <Field key={field.key} label={field.label} value={settings[field.key] || ''} onChange={value => setValue(field.key, value)} hint={'hint' in field ? field.hint : undefined} type={'type' in field ? field.type : undefined} min={'min' in field ? field.min : undefined} max={'max' in field ? field.max : undefined}/>)}</div>
          <div className="notice notice-info" style={{ marginTop: 15 }}><Icon name="info"/><span>Часы звонков применяются планировщиком. Тестовый ручной шаг в разделе кампаний их обходит.</span></div>
        </section>
        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Модели и локальные файлы</h2><p className="section-description">После сохранения новые вызовы сразу используют обновлённые настройки.</p></div></div>
          <div className="settings-fields">
            <label className="field"><span className="field-label">Провайдер диалога</span><select className="select" value={settings.llm_provider || 'mock'} onChange={event => setValue('llm_provider', event.target.value)}><option value="mock">Тестовый режим</option><option value="codex">Codex</option></select></label>
            <Field label="Модель диалога" value={settings.llm_model || ''} onChange={value => setValue('llm_model', value)}/>
            <label className="field"><span className="field-label">Уровень рассуждения</span><select className="select" value={settings.reasoning_effort || 'low'} onChange={event => setValue('reasoning_effort', event.target.value)}><option value="low">Низкий</option><option value="medium">Средний</option><option value="high">Высокий</option><option value="xhigh">Очень высокий</option></select></label>
            <Field label="Путь к модели распознавания (Vosk)" value={settings.vosk_model_path || ''} onChange={value => setValue('vosk_model_path', value)} wide hint="Путь на компьютере, где запущен backend."/>
            <Field label="Путь к модели голоса (Piper)" value={settings.piper_model_path || ''} onChange={value => setValue('piper_model_path', value)} wide hint="Путь на компьютере, где запущен backend."/>
          </div>
        </section>
      </div>

      <aside>
        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Состояние сервисов</h2><p className="section-description">Проверка при последней загрузке страницы</p></div><span className={`status-dot ${health ? 'is-ready' : ''}`} aria-label={health ? 'Проверено' : 'Нет данных'}/></div>
          {health ? <>
            {providerRows.map(([key, label]) => {
              const provider = health[key];
              const configuredProvider = provider?.provider ?? providers[`${key}_provider`] ?? settings.llm_provider;
              const detail = formatProviderDetail(provider?.detail);
              return <div className="provider-card" key={key}><div className="provider-card-top"><strong>{label}</strong><span className={`badge ${provider?.ok ? 'badge-success' : 'badge-danger'}`}>{provider?.ok ? 'Доступен' : 'Проверить'}</span></div><div className="provider-card-value">{providerLabel(configuredProvider)}</div><div className="field-hint">{provider?.ok ? (detail || 'Сервис отвечает.') : (detail || 'Проверьте конфигурацию и журнал backend.')}</div></div>;
            })}
            <div className="provider-row"><dt>Codex CLI</dt><dd><span className={`badge ${health.codex_on_path ? 'badge-success' : 'badge-neutral'}`}>{health.codex_on_path ? 'Доступен' : 'Не найден'}</span></dd></div>
          </> : <Notice tone="warning">Не удалось получить состояние провайдеров. Проверьте сервер или попробуйте обновить страницу.</Notice>}
          <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={load}><Icon name="refresh"/>Проверить снова</button>
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
