'use client';

import Link from 'next/link';
import { use, useCallback, useEffect, useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import Dialog from '@/components/Dialog';
import ConfirmDialog from '@/components/ConfirmDialog';
import { fmt, friendlyError, Header, Icon, Loading, localDateTimeValue, Notice, StatusBadge } from '@/components/UI';

type Callback = { id: number; reason: string; scheduled_at: string; status: string };
type Call = { id: number; result?: string | null; status: string; started_at: string; summary?: string; duration: number; stt_ms: number; llm_ms: number; tts_ms: number; total_ms: number; transcripts: Array<{ id: number; role: string; content: string; timestamp: string }> };
type Lead = { id: number; name?: string | null; company?: string | null; phone: string; notes: string; status: string; attempts: number; result?: string | null; created_at: string; last_call_at?: string | null; next_call_at?: string | null };
type Details = { lead: Lead; calls: Call[]; callbacks: Callback[] };

function transcriptRole(role: string) { return role === 'assistant' ? 'Ассистент' : role === 'user' ? 'Собеседник' : 'Система'; }

export default function LeadDetails({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [details, setDetails] = useState<Details | null>(null);
  const [note, setNote] = useState('');
  const [savedNote, setSavedNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [confirm, setConfirm] = useState<'call' | 'dnc' | null>(null);
  const [callbackOpen, setCallbackOpen] = useState(false);
  const [callbackDate, setCallbackDate] = useState(() => {
    const date = new Date(); date.setDate(date.getDate() + 1); date.setHours(11, 0, 0, 0); return localDateTimeValue(date);
  });
  const [callbackReason, setCallbackReason] = useState('Уточнить детали');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const result = await api<Details>(`/leads/${id}`);
      setDetails(result); setNote(result.lead.notes || ''); setSavedNote(result.lead.notes || '');
    } catch (requestError) { setError(friendlyError(requestError)); }
    finally { setLoading(false); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);

  async function updateStatus(status: string, successMessage: string) {
    setWorking(true); setError(''); setSuccess('');
    try { await api(`/leads/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }); setSuccess(successMessage); setConfirm(null); await load(); }
    catch (requestError) { setError(friendlyError(requestError)); }
    finally { setWorking(false); }
  }

  async function saveNotes(event?: FormEvent) {
    event?.preventDefault();
    setWorking(true); setError(''); setSuccess('');
    try { await api(`/leads/${id}`, { method: 'PATCH', body: JSON.stringify({ notes: note }) }); setSavedNote(note); setSuccess('Заметки сохранены.'); }
    catch (requestError) { setError(friendlyError(requestError)); }
    finally { setWorking(false); }
  }

  async function callNow() {
    setWorking(true); setError(''); setSuccess('');
    try { await api(`/leads/${id}/call-now`, { method: 'POST' }); setConfirm(null); setSuccess('Звонок добавлен. Статус обновится после ответа провайдера.'); await load(); }
    catch (requestError) { setError(friendlyError(requestError)); setConfirm(null); }
    finally { setWorking(false); }
  }

  async function scheduleCallback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const date = new Date(callbackDate);
    if (!callbackDate || Number.isNaN(date.getTime()) || date.getTime() <= Date.now()) {
      setError('Выберите время в будущем.'); return;
    }
    setWorking(true); setError(''); setSuccess('');
    try {
      await api(`/leads/${id}/callback`, { method: 'POST', body: JSON.stringify({ scheduled_at: date.toISOString(), reason: callbackReason.trim() || 'Обратный звонок' }) });
      setCallbackOpen(false); setSuccess('Обратный звонок запланирован.'); await load();
    } catch (requestError) { setError(friendlyError(requestError)); }
    finally { setWorking(false); }
  }

  if (loading) return <Loading text="Загружаем карточку лида…"/>;
  if (error && !details) return <><Header title="Карточка лида" sub="Не удалось открыть контакт"/><Notice tone="danger">{error} <button type="button" className="btn btn-sm" onClick={load}>Повторить</button></Notice></>;
  if (!details) return null;
  const lead = details.lead;
  const isBlocked = lead.status === 'DO_NOT_CALL';
  const scheduledCallbacks = details.callbacks.filter(callback => ['SCHEDULED', 'DUE'].includes(callback.status));

  return <>
    <Header breadcrumb={<><Link href="/leads" className="accent-link">Лиды</Link><Icon name="chevron" size={12}/></>} title={lead.company || lead.name || `Лид #${lead.id}`} sub={lead.phone}>
      <button type="button" className="btn btn-primary" onClick={() => setConfirm('call')} disabled={working || isBlocked}><Icon name="phone"/>Позвонить</button>
      <button type="button" className="btn" onClick={() => { setError(''); setCallbackOpen(true); }} disabled={working || isBlocked}><Icon name="calendar"/>Назначить звонок</button>
      {!isBlocked && <button type="button" className="btn" onClick={() => void updateStatus('DONE', 'Лид отмечен как завершённый.')} disabled={working}><Icon name="check"/>Завершить</button>}
      {!isBlocked && <button type="button" className="btn btn-danger" onClick={() => setConfirm('dnc')} disabled={working}>Не звонить</button>}
    </Header>
    {error && <div className="feedback"><Notice tone="danger">{error}</Notice></div>}
    {success && <div className="feedback"><Notice tone="success">{success}</Notice></div>}
    {isBlocked && <div className="feedback"><Notice tone="warning">Для этого контакта включён запрет на звонки. Активные обратные звонки отменены.</Notice></div>}

    <div className="lead-detail-grid">
      <aside className="stack">
        <section className="card settings-section">
          <div className="section-heading"><div><h2 className="section-title">Контакт</h2><p className="section-description">Основная информация и статус</p></div><StatusBadge status={lead.status}/></div>
          <div className="detail-property"><span>Компания</span><span>{lead.company || '—'}</span></div>
          <div className="detail-property"><span>Контакт</span><span>{lead.name || '—'}</span></div>
          <div className="detail-property"><span>Попытки звонка</span><span>{lead.attempts}</span></div>
          <div className="detail-property"><span>Последний звонок</span><span>{fmt(lead.last_call_at)}</span></div>
          <div className="detail-property"><span>Следующий шаг</span><span>{fmt(lead.next_call_at)}</span></div>
          <div className="detail-property"><span>Результат</span><span>{lead.result || '—'}</span></div>
          <form onSubmit={saveNotes} style={{ marginTop: 16 }}>
            <label className="field"><span className="field-label">Заметки</span><textarea className="textarea" value={note} onChange={event => setNote(event.target.value)} placeholder="Важные детали о контакте" rows={5}/></label>
            <button type="submit" className="btn" style={{ marginTop: 9 }} disabled={working || note === savedNote}><Icon name="save"/>Сохранить заметки</button>
          </form>
        </section>
        <section className="card">
          <div className="panel-header"><div><h2 className="section-title">Обратные звонки</h2><p className="section-description">Следующие действия по контакту</p></div>{scheduledCallbacks.length > 0 && <span className="badge badge-info">{scheduledCallbacks.length}</span>}</div>
          <div className="panel-content">
            {details.callbacks.length ? details.callbacks.map(callback => <div className="activity-row" key={callback.id}><span className="activity-mark"><Icon name="calendar"/></span><div className="activity-copy"><div className="activity-title">{callback.reason || 'Обратный звонок'}</div><div className="activity-meta">{fmt(callback.scheduled_at)}</div></div><StatusBadge status={callback.status}/></div>) : <div className="muted" style={{ fontSize: 11 }}>Пока ничего не запланировано.</div>}
            {details.callbacks.length > 0 && <Link href="/callbacks" className="btn btn-ghost btn-sm" style={{ marginTop: 8 }}>Открыть очередь <Icon name="arrow" size={12}/></Link>}
          </div>
        </section>
      </aside>

      <section className="card">
        <div className="panel-header"><div><h2 className="section-title">История звонков</h2><p className="section-description">Результаты, сводки и расшифровки</p></div><span className="table-count">{details.calls.length} {details.calls.length === 1 ? 'звонок' : 'звонков'}</span></div>
        <div className="panel-content">
          {details.calls.length ? details.calls.map(call => <article className="card call-card" key={call.id}>
            <div className="panel-header"><div><div className="section-title">Звонок #{call.id} <StatusBadge status={call.result || call.status}/></div><p className="section-description">{fmt(call.started_at)} · {call.duration ? `${Math.floor(call.duration / 60)} мин ${call.duration % 60} сек` : 'длительность не указана'}</p></div></div>
            <div className="panel-content">
              <p className="call-summary">{call.summary || 'Краткая сводка отсутствует.'}</p>
              <div className="call-timings">Обработка речи: STT {Math.round(call.stt_ms || 0)} мс · AI {Math.round(call.llm_ms || 0)} мс · голос {Math.round(call.tts_ms || 0)} мс · всего {Math.round(call.total_ms || 0)} мс</div>
              {call.transcripts?.length > 0 && <details className="call-transcript"><summary className="btn btn-sm">Показать расшифровку · {call.transcripts.length}</summary><div style={{ marginTop: 10 }}>{call.transcripts.map(message => <div className="transcript" key={message.id}><span className="transcript-role">{transcriptRole(message.role)} · {fmt(message.timestamp)}</span>{message.content}</div>)}</div></details>}
            </div>
          </article>) : <div className="empty-state"><div className="empty-icon"><Icon name="phone"/></div><h3 className="empty-title">Звонков ещё не было</h3><p className="empty-copy">История, результаты и расшифровки появятся после первого контакта.</p></div>}
        </div>
      </section>
    </div>

    <ConfirmDialog open={confirm === 'call'} title={`Позвонить ${lead.phone}?`} description="Система отправит запрос провайдеру звонков. Проверьте номер перед запуском." confirmLabel="Начать звонок" busy={working} onCancel={() => setConfirm(null)} onConfirm={callNow}/>
    <ConfirmDialog open={confirm === 'dnc'} title="Запретить звонки этому лиду?" description="Контакт будет исключён из кампаний, а запланированные обратные звонки отменятся." confirmLabel="Включить запрет" danger busy={working} onCancel={() => setConfirm(null)} onConfirm={() => void updateStatus('DO_NOT_CALL', 'Запрет на звонки включён.')}/>

    {callbackOpen && <Dialog title="Запланировать обратный звонок" description="Укажите удобное время и контекст следующего контакта." onClose={() => setCallbackOpen(false)} dismissible={!working}><form onSubmit={scheduleCallback}>
      <div className="form-grid"><label className="field field-wide"><span className="field-label">Дата и время</span><input data-autofocus className="input" type="datetime-local" value={callbackDate} min={localDateTimeValue(new Date(Date.now() + 60000))} onChange={event => setCallbackDate(event.target.value)} required/></label><label className="field field-wide"><span className="field-label">Причина</span><input className="input" value={callbackReason} onChange={event => setCallbackReason(event.target.value)} maxLength={500}/></label></div>
      <div className="modal-actions"><button type="button" className="btn" onClick={() => setCallbackOpen(false)} disabled={working}>Отмена</button><button type="submit" className="btn btn-primary" disabled={working}>{working ? 'Сохраняем…' : 'Запланировать'}</button></div>
    </form></Dialog>}
  </>;
}
