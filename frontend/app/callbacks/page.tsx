'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import ConfirmDialog from '@/components/ConfirmDialog';
import Dialog from '@/components/Dialog';
import { Empty, fmt, friendlyError, Header, Icon, Loading, localDateTimeValue, Metric, Notice, StatusBadge } from '@/components/UI';

type CallbackRow = { id: number; lead_id: number; call_id?: number | null; reason: string; scheduled_at: string; status: string; phone: string; company?: string | null };
type Filter = 'active' | 'all' | 'completed' | 'canceled';

const filterLabels: Array<{ id: Filter; label: string }> = [
  { id: 'active', label: 'Предстоящие' }, { id: 'all', label: 'Все' }, { id: 'completed', label: 'Выполненные' }, { id: 'canceled', label: 'Отменённые' },
];

export default function Callbacks() {
  const [rows, setRows] = useState<CallbackRow[]>([]);
  const [filter, setFilter] = useState<Filter>('active');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [cancelTarget, setCancelTarget] = useState<CallbackRow | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<CallbackRow | null>(null);
  const [scheduledAt, setScheduledAt] = useState('');
  const [query, setQuery] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setRows(await api<CallbackRow[]>('/callbacks')); }
    catch (requestError) { setError(friendlyError(requestError)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const now = Date.now();
  const activeRows = rows.filter(row => ['SCHEDULED', 'DUE'].includes(row.status));
  const overdueCount = activeRows.filter(row => row.status === 'DUE' || new Date(row.scheduled_at).getTime() < now).length;
  const todayCount = activeRows.filter(row => { const date = new Date(row.scheduled_at); const today = new Date(); return date.toDateString() === today.toDateString(); }).length;
  const upcomingCount = Math.max(0, activeRows.length - overdueCount - todayCount);
  const filteredRows = useMemo(() => rows.filter(row => {
    const matchesFilter = filter === 'active' ? ['SCHEDULED', 'DUE'].includes(row.status)
      : filter === 'completed' ? row.status === 'COMPLETED' : filter === 'canceled' ? row.status === 'CANCELED' : true;
    const haystack = `${row.company || ''} ${row.phone || ''} ${row.reason || ''}`.toLocaleLowerCase('ru-RU');
    return matchesFilter && (!query.trim() || haystack.includes(query.trim().toLocaleLowerCase('ru-RU')));
  }).sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime()), [rows, filter, query]);

  async function updateCallback(row: CallbackRow, patch: { status: 'COMPLETED' | 'CANCELED' | 'SCHEDULED'; scheduled_at?: string }) {
    setWorkingId(row.id); setFeedback(null); setError('');
    try {
      await api(`/callbacks/${row.id}`, { method: 'PATCH', body: JSON.stringify(patch) });
      setFeedback({ tone: 'success', text: patch.status === 'COMPLETED' ? 'Обратный звонок отмечен выполненным.' : patch.status === 'CANCELED' ? 'Обратный звонок отменён.' : 'Новое время сохранено.' });
      setCancelTarget(null); setRescheduleTarget(null); await load();
    } catch (requestError) { setFeedback({ tone: 'danger', text: friendlyError(requestError) }); }
    finally { setWorkingId(null); }
  }

  function openReschedule(row: CallbackRow) {
    const existing = new Date(row.scheduled_at);
    const fallback = new Date(Date.now() + 86400000);
    setScheduledAt(localDateTimeValue(existing.getTime() > Date.now() ? existing : fallback));
    setRescheduleTarget(row); setFeedback(null);
  }

  const dueLabel = overdueCount ? `${overdueCount} требуют внимания` : 'Просроченных нет';

  return <>
    <Header title="Обратные звонки" sub="Очередь следующих шагов по контактам"/>
    {feedback && <div className="feedback"><Notice tone={feedback.tone}>{feedback.text}</Notice></div>}
    {error && <div className="feedback"><Notice tone="danger">{error} <button className="btn btn-sm" onClick={load}>Повторить</button></Notice></div>}
    {!loading && !error && <>
      <div className="metric-grid">
        <Metric label="Нужно связаться" value={overdueCount} icon="warning" footnote={dueLabel}/>
        <Metric label="Запланировано на сегодня" value={todayCount} icon="calendar"/>
        <Metric label="Позже" value={upcomingCount} icon="clock"/>
        <Metric label="Выполнено" value={rows.filter(row => row.status === 'COMPLETED').length} icon="check"/>
      </div>
    </>}

    <section className="card" aria-label="Очередь обратных звонков">
      <div className="table-toolbar">
        <div className="table-filters">
          <label className="search-field"><span className="visually-hidden">Поиск по компании, телефону или причине</span><Icon name="search"/><input className="input" placeholder="Компания, телефон или причина" value={query} onChange={event => setQuery(event.target.value)}/></label>
        </div>
        <span className="table-count">{filteredRows.length} {filteredRows.length === 1 ? 'задача' : 'задач'}</span>
      </div>
      <div className="tabs" role="group" aria-label="Фильтр очереди">
        {filterLabels.map(item => <button key={item.id} type="button" className="tab" aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}>{item.label}{item.id === 'active' && ` · ${activeRows.length}`}</button>)}
      </div>
      {loading ? <Loading text="Загружаем очередь…"/> : error ? null : filteredRows.length === 0 ? <Empty title={filter === 'active' ? 'Очередь свободна' : 'Задач не найдено'} text={filter === 'active' ? 'Новые задачи появятся здесь после звонка или планирования контакта.' : 'Попробуйте изменить фильтр или поисковый запрос.'} icon="callback"/> : <>
        <div className="table-scroll callbacks-table"><table className="data-table"><thead><tr><th>Контакт</th><th>Причина</th><th>Время</th><th>Статус</th><th><span className="visually-hidden">Действия</span></th></tr></thead><tbody>
          {filteredRows.map(row => <tr key={row.id}><td className="primary-cell"><Link href={`/leads/${row.lead_id}`} className="accent-link">{row.company || `Лид #${row.lead_id}`}</Link><div className="muted" style={{ fontSize: 10, marginTop: 2 }}>{row.phone || 'Телефон не указан'}</div></td><td>{row.reason || 'Обратный звонок'}</td><td>{fmt(row.scheduled_at)}</td><td><StatusBadge status={row.status}/></td><td><div className="callback-actions">{['SCHEDULED', 'DUE'].includes(row.status) && <><button className="btn btn-sm" type="button" onClick={() => openReschedule(row)} aria-label={`Перенести обратный звонок #${row.id}`} disabled={workingId === row.id}>Перенести</button><button className="btn btn-sm" type="button" onClick={() => void updateCallback(row, { status: 'COMPLETED' })} aria-label={`Отметить обратный звонок #${row.id} выполненным`} disabled={workingId === row.id}>Готово</button><button className="btn btn-ghost btn-sm" type="button" onClick={() => setCancelTarget(row)} aria-label={`Отменить обратный звонок #${row.id}`} disabled={workingId === row.id}>Отменить</button></>}</div></td></tr>)}
        </tbody></table></div>
        <div className="callbacks-mobile">
          {filteredRows.map(row => <article className="mobile-record" key={row.id}><div className="mobile-record-head"><div><Link href={`/leads/${row.lead_id}`} className="mobile-record-title">{row.company || `Лид #${row.lead_id}`}</Link><div className="mobile-record-meta">{row.phone}</div></div><StatusBadge status={row.status}/></div><div className="mobile-record-meta" style={{ marginTop: 8 }}>{row.reason || 'Обратный звонок'} · {fmt(row.scheduled_at)}</div>{['SCHEDULED', 'DUE'].includes(row.status) && <div className="callback-actions" style={{ marginTop: 10 }}><button className="btn btn-sm" type="button" onClick={() => openReschedule(row)} aria-label={`Перенести обратный звонок #${row.id}`}>Перенести</button><button className="btn btn-sm" type="button" onClick={() => void updateCallback(row, { status: 'COMPLETED' })} aria-label={`Отметить обратный звонок #${row.id} выполненным`}>Готово</button><button className="btn btn-ghost btn-sm" type="button" onClick={() => setCancelTarget(row)} aria-label={`Отменить обратный звонок #${row.id}`}>Отменить</button></div>}</article>)}
        </div>
      </>}
    </section>

    <ConfirmDialog open={Boolean(cancelTarget)} title="Отменить обратный звонок?" description={cancelTarget ? `${cancelTarget.company || cancelTarget.phone || `Лид #${cancelTarget.lead_id}`} · ${fmt(cancelTarget.scheduled_at)}` : ''} confirmLabel="Отменить звонок" danger busy={workingId !== null} onCancel={() => setCancelTarget(null)} onConfirm={() => cancelTarget && void updateCallback(cancelTarget, { status: 'CANCELED' })}/>

    {rescheduleTarget && <Dialog title="Перенести звонок" description={`${rescheduleTarget.company || rescheduleTarget.phone || `Лид #${rescheduleTarget.lead_id}`}. Новое время будет показано в часовом поясе вашего устройства.`} onClose={() => setRescheduleTarget(null)} dismissible={workingId === null}>
      <label className="field"><span className="field-label">Новое время</span><input data-autofocus className="input" type="datetime-local" value={scheduledAt} min={localDateTimeValue(new Date(Date.now() + 60000))} onChange={event => setScheduledAt(event.target.value)}/></label>
      {feedback?.tone === 'danger' && <div className="feedback" style={{ marginTop: 10 }}><Notice tone="danger">{feedback.text}</Notice></div>}
      <div className="modal-actions"><button type="button" className="btn" onClick={() => setRescheduleTarget(null)} disabled={workingId !== null}>Назад</button><button type="button" className="btn btn-primary" disabled={!scheduledAt || workingId !== null} onClick={() => { const date = new Date(scheduledAt); if (date.getTime() <= Date.now()) { setFeedback({ tone: 'danger', text: 'Выберите время в будущем.' }); return; } void updateCallback(rescheduleTarget, { status: 'SCHEDULED', scheduled_at: date.toISOString() }); }}>Сохранить время</button></div>
    </Dialog>}
  </>;
}
