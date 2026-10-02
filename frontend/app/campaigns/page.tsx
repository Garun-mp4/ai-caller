'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import ConfirmDialog from '@/components/ConfirmDialog';
import { Empty, friendlyError, Header, Icon, Loading, Notice, StatusBadge } from '@/components/UI';

type Campaign = { id: number; name: string; description: string; agent_prompt: string; status: string; metrics: Record<string, number> };
type CampaignForm = { name: string; description: string; agent_prompt: string };
type AudiencePreview = { to_attach: number; already_attached: number; attached_eligible: number; by_status: Record<string, number> };
const metricLabels: Record<string, string> = { total: 'Лидов', queued: 'В очереди', calling: 'Звонят', answered: 'Ответили', no_answer: 'Нет ответа', interested: 'С интересом', hot_leads: 'Горячие' };

export default function Campaigns() {
  const [rows, setRows] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState<Record<number, boolean>>({});
  const [audiences, setAudiences] = useState<Record<number, AudiencePreview>>({});
  const [audienceReviewed, setAudienceReviewed] = useState<Record<number, boolean>>({});
  const [previewingId, setPreviewingId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<CampaignForm>({ name: '', description: '', agent_prompt: '' });
  const [creating, setCreating] = useState(false);
  const [stopTarget, setStopTarget] = useState<Campaign | null>(null);
  const [showTickConfirm, setShowTickConfirm] = useState(false);
  const [tickBusy, setTickBusy] = useState(false);
  const showDevActions = process.env.NODE_ENV !== 'production';

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setRows(await api<Campaign[]>('/campaigns')); }
    catch (requestError) { setError(friendlyError(requestError)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function createCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setCreating(true); setFeedback(null); setError('');
    try {
      await api('/campaigns', { method: 'POST', body: JSON.stringify(form) });
      setForm({ name: '', description: '', agent_prompt: '' }); setFormOpen(false);
      setFeedback({ tone: 'success', text: 'Кампания создана. Проверьте настройки и подтвердите право на контакт перед запуском.' });
      await load();
    } catch (requestError) { setFeedback({ tone: 'danger', text: friendlyError(requestError) }); }
    finally { setCreating(false); }
  }

  async function previewAudience(campaign: Campaign) {
    setPreviewingId(campaign.id); setFeedback(null);
    setConfirmed(current => ({ ...current, [campaign.id]: false }));
    setAudienceReviewed(current => ({ ...current, [campaign.id]: false }));
    try {
      const preview = await api<AudiencePreview>(`/campaigns/${campaign.id}/audience`);
      setAudiences(current => ({ ...current, [campaign.id]: preview }));
      setAudienceReviewed(current => ({ ...current, [campaign.id]: true }));
    } catch (requestError) {
      setFeedback({ tone: 'danger', text: friendlyError(requestError) });
    } finally { setPreviewingId(null); }
  }

  async function campaignAction(campaign: Campaign, action: 'start' | 'pause' | 'stop') {
    setWorkingId(campaign.id); setFeedback(null); setError('');
    try {
      if (action === 'start') {
        if (!confirmed[campaign.id]) throw new Error('Compliance confirmation is required');
        if (!audienceReviewed[campaign.id]) throw new Error('Сначала проверьте аудиторию кампании.');
        const attached = await api<{ attached: number }>(`/campaigns/${campaign.id}/attach-all`, { method: 'POST' });
        await api(`/campaigns/${campaign.id}/start`, { method: 'POST', body: JSON.stringify({ confirm_compliance: true }) });
        setFeedback({ tone: 'success', text: `Кампания запущена. Добавлено контактов: ${attached.attached}. Подтверждение права на связь сохранено.` });
        setAudiences(current => { const next = { ...current }; delete next[campaign.id]; return next; });
        setAudienceReviewed(current => ({ ...current, [campaign.id]: false }));
      } else {
        await api(`/campaigns/${campaign.id}/${action}`, { method: 'POST' });
        setFeedback({ tone: 'success', text: action === 'pause' ? 'Кампания приостановлена.' : 'Кампания остановлена.' });
      }
      setStopTarget(null); setConfirmed(current => ({ ...current, [campaign.id]: false })); await load();
    } catch (requestError) { setFeedback({ tone: 'danger', text: friendlyError(requestError) }); }
    finally { setWorkingId(null); }
  }

  async function runTick() {
    setTickBusy(true); setFeedback(null);
    try {
      const result = await api<{ processed: number }>('/scheduler/tick', { method: 'POST' });
      setFeedback({ tone: 'success', text: `Планировщик обработал звонков: ${result.processed}.` }); setShowTickConfirm(false); await load();
    } catch (requestError) { setFeedback({ tone: 'danger', text: friendlyError(requestError) }); }
    finally { setTickBusy(false); }
  }

  return <>
    <Header title="Кампании" sub="Подготовка очередей и управление запуском">
      {showDevActions && <button type="button" className="btn" onClick={() => setShowTickConfirm(true)}><Icon name="activity"/>Тестовый шаг</button>}
      <button type="button" className="btn btn-primary" onClick={() => setFormOpen(value => !value)}><Icon name={formOpen ? 'close' : 'plus'}/>{formOpen ? 'Закрыть форму' : 'Новая кампания'}</button>
    </Header>
    {feedback && <div className="feedback"><Notice tone={feedback.tone}>{feedback.text}</Notice></div>}
    {error && <div className="feedback"><Notice tone="danger">{error} <button className="btn btn-sm" onClick={load}>Повторить</button></Notice></div>}

    {formOpen && <section className="card settings-section" style={{ marginBottom: 14 }}>
      <div className="section-heading"><div><h2 className="section-title">Новая кампания</h2><p className="section-description">Задайте цель и контекст для AI-оператора.</p></div></div>
      <form onSubmit={createCampaign} className="form-grid">
        <label className="field"><span className="field-label">Название</span><input className="input" value={form.name} onChange={event => setForm(value => ({ ...value, name: event.target.value }))} maxLength={200} required placeholder="Например, первичный контакт"/></label>
        <label className="field"><span className="field-label">Описание</span><input className="input" value={form.description} onChange={event => setForm(value => ({ ...value, description: event.target.value }))} placeholder="Кому и с каким предложением звоним"/></label>
        <label className="field field-wide"><span className="field-label">Инструкция агенту <span className="muted">(необязательно)</span></span><textarea className="textarea" rows={3} value={form.agent_prompt} onChange={event => setForm(value => ({ ...value, agent_prompt: event.target.value }))} placeholder="Тон разговора, вопросы, критерии квалификации"/></label>
        {feedback?.tone === 'danger' && <div className="field-wide"><Notice tone="danger">{feedback.text}</Notice></div>}
        <div className="form-actions"><button type="submit" className="btn btn-primary" disabled={creating || !form.name.trim()}>{creating ? 'Создаём…' : 'Создать кампанию'}</button></div>
      </form>
    </section>}

    {loading ? <Loading text="Загружаем кампании…"/> : error ? null : rows.length === 0 ? <section className="card"><Empty title="Кампаний пока нет" text="Создайте кампанию, проверьте аудиторию и только потом запускайте звонки." icon="campaigns" action={<button className="btn btn-primary btn-sm" onClick={() => setFormOpen(true)}><Icon name="plus"/>Создать кампанию</button>}/></section> : <div className="campaign-list">
      {rows.map(campaign => {
        const metrics = campaign.metrics || {};
        const canStart = ['DRAFT', 'PAUSED'].includes(campaign.status);
        const canPause = campaign.status === 'RUNNING';
        const canStop = !['STOPPED', 'DRAFT'].includes(campaign.status);
        const audience = audiences[campaign.id];
        const hasCallableAudience = Boolean(audience && audience.to_attach + audience.attached_eligible > 0);
        return <article className="card campaign-card" key={campaign.id}>
          <div className="campaign-topline">
            <div><h2 className="campaign-name">{campaign.name} <StatusBadge status={campaign.status}/></h2><p className="campaign-copy">{campaign.description || 'Описание не добавлено.'}</p></div>
            <div className="campaign-actions">
              {canStart && <button type="button" className="btn btn-primary" onClick={() => void campaignAction(campaign, 'start')} disabled={!confirmed[campaign.id] || !audienceReviewed[campaign.id] || !hasCallableAudience || workingId === campaign.id}><Icon name="play"/>{workingId === campaign.id ? 'Запускаем…' : 'Запустить'}</button>}
              {canPause && <button type="button" className="btn" onClick={() => void campaignAction(campaign, 'pause')} disabled={workingId === campaign.id}><Icon name="pause"/>Приостановить</button>}
              {canStop && <button type="button" className="btn btn-danger" onClick={() => setStopTarget(campaign)} disabled={workingId === campaign.id}><Icon name="stop"/>Остановить</button>}
            </div>
          </div>
          <div className="campaign-metrics">{Object.entries(metricLabels).map(([key, label]) => <div className="campaign-metric" key={key}><span>{label}</span><strong>{metrics[key] ?? 0}</strong></div>)}</div>
          {canStart && <div className="campaign-audience-review">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => void previewAudience(campaign)} disabled={previewingId === campaign.id}><Icon name="users"/>{previewingId === campaign.id ? 'Проверяем…' : audienceReviewed[campaign.id] ? 'Обновить аудиторию' : 'Проверить аудиторию'}</button>
            {audienceReviewed[campaign.id] && audience && <p className="field-hint" role="status">К добавлению: {audience.to_attach}; уже подходят в кампании: {audience.attached_eligible}; прикреплено всего: {audience.already_attached}. В разрезе: новые — {audience.by_status.NEW || 0}, в очереди — {audience.by_status.QUEUED || 0}, обратные звонки — {audience.by_status.CALLBACK || 0}. Запрет «Не звонить» исключается автоматически.</p>}
            {audienceReviewed[campaign.id] && !hasCallableAudience && <div className="notice notice-warning">Подходящих контактов пока нет. Добавьте новых лидов или проверьте статус кампании.</div>}
            <label className="checkbox-row"><input type="checkbox" checked={Boolean(confirmed[campaign.id])} disabled={!audienceReviewed[campaign.id] || !hasCallableAudience} onChange={event => setConfirmed(value => ({ ...value, [campaign.id]: event.target.checked }))}/><span>Я проверил аудиторию, имею право связываться с этими лидами и буду соблюдать требования к телемаркетингу и защите персональных данных.</span></label>
          </div>}
          {campaign.agent_prompt && <details style={{ marginTop: 12 }}><summary className="btn btn-ghost btn-sm">Инструкция AI-агенту</summary><p className="call-summary">{campaign.agent_prompt}</p></details>}
        </article>;
      })}
    </div>}

    <ConfirmDialog open={Boolean(stopTarget)} title="Остановить кампанию?" description={stopTarget ? `«${stopTarget.name}» перестанет запускать новые звонки. Продолжить можно будет только вручную.` : ''} confirmLabel="Остановить кампанию" danger busy={workingId !== null} onCancel={() => setStopTarget(null)} onConfirm={() => stopTarget && void campaignAction(stopTarget, 'stop')}/>
    <ConfirmDialog open={showTickConfirm} title="Выполнить тестовый шаг?" description="Этот инструмент принудительно обходит разрешённые часы звонков. Используйте его только локально для проверки планировщика." confirmLabel="Запустить шаг" busy={tickBusy} onCancel={() => setShowTickConfirm(false)} onConfirm={runTick}/>
  </>;
}
