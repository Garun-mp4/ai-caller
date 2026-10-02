'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import ConfirmDialog from '@/components/ConfirmDialog';
import Dialog from '@/components/Dialog';
import { Empty, fmt, friendlyError, Header, Icon, Loading, localDateTimeValue, Metric, Notice, StatusBadge } from '@/components/UI';

type CallbackRow = { id: number; lead_id: number; call_id?: number | null; reason: string; scheduled_at: string; status: string; phone: string; company?: string | null };
type CallbackPage = {
  items: CallbackRow[];
  total: number;
  page: number;
  page_size: number;
  page_count: number;
  stats: { total: number; active: number; overdue: number; today: number; upcoming: number; completed: number };
};
type Filter = 'active' | 'all' | 'completed' | 'canceled';

const PAGE_SIZE = 20;
const filterLabels: Array<{ id: Filter; label: string }> = [
  { id: 'active', label: 'Предстоящие' }, { id: 'all', label: 'Все' }, { id: 'completed', label: 'Выполненные' }, { id: 'canceled', label: 'Отменённые' },
];
const statusByFilter: Partial<Record<Filter, string>> = { active: 'ACTIVE', completed: 'COMPLETED', canceled: 'CANCELED' };

export default function Callbacks() {
  const [data, setData] = useState<CallbackPage | null>(null);
  const [filter, setFilter] = useState<Filter>('active');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [cancelTarget, setCancelTarget] = useState<CallbackRow | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<CallbackRow | null>(null);
  const [scheduledAt, setScheduledAt] = useState('');
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(query.trim());
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    const status = statusByFilter[filter];
    if (status) params.set('status', status);
    if (search) params.set('search', search);
    setLoading(true);
    setError('');
    void api<CallbackPage>(`/callbacks?${params.toString()}`, { signal: controller.signal })
      .then(result => {
        if (!current) return;
        if (page > result.page_count) {
          setPage(result.page_count);
          return;
        }
        setData(result);
      })
      .catch(requestError => {
        if (current && !controller.signal.aborted) setError(friendlyError(requestError));
      })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [filter, page, retry, search]);

  const rows = data?.items || [];
  const total = data?.total || 0;
  const stats = data?.stats;
  const pageCount = data?.page_count || 1;
  const firstResult = total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const lastResult = Math.min(page * PAGE_SIZE, total);
  const queueIsEmpty = filter === 'active' && !search && total === 0;
  const historyIsEmpty = filter === 'all' && !search && stats?.total === 0;

  async function updateCallback(row: CallbackRow, patch: { status: 'COMPLETED' | 'CANCELED' | 'SCHEDULED'; scheduled_at?: string }) {
    setWorkingId(row.id); setFeedback(null); setError('');
    try {
      await api(`/callbacks/${row.id}`, { method: 'PATCH', body: JSON.stringify(patch) });
      setFeedback({ tone: 'success', text: patch.status === 'COMPLETED' ? 'Обратный звонок отмечен выполненным.' : patch.status === 'CANCELED' ? 'Обратный звонок отменён.' : 'Новое время сохранено.' });
      setCancelTarget(null); setRescheduleTarget(null); setRetry(value => value + 1);
    } catch (requestError) { setFeedback({ tone: 'danger', text: friendlyError(requestError) }); }
    finally { setWorkingId(null); }
  }

  function openReschedule(row: CallbackRow) {
    const existing = new Date(row.scheduled_at);
    const fallback = new Date(Date.now() + 86400000);
    setScheduledAt(localDateTimeValue(existing.getTime() > Date.now() ? existing : fallback));
    setRescheduleTarget(row); setFeedback(null);
  }

  const dueLabel = stats?.overdue ? `${stats.overdue} требуют внимания` : 'Просроченных нет';

  return <>
    <Header title="Обратные звонки" sub="Очередь следующих шагов по контактам"/>
    {feedback && <div className="feedback"><Notice tone={feedback.tone}>{feedback.text}</Notice></div>}
    {error && <div className="feedback"><Notice tone="danger">{error} <button className="btn btn-sm" onClick={() => setRetry(value => value + 1)}>Повторить</button></Notice></div>}
    {stats && <div className="metric-grid">
      <Metric label="Нужно связаться" value={stats.overdue} icon="warning" footnote={dueLabel}/>
      <Metric label="Запланировано на сегодня" value={stats.today} icon="calendar"/>
      <Metric label="Позже" value={stats.upcoming} icon="clock"/>
      <Metric label="Выполнено" value={stats.completed} icon="check"/>
    </div>}

    <section className="card" aria-label="Очередь обратных звонков" aria-busy={loading}>
      <div className="table-toolbar">
        <div className="table-filters">
          <label className="search-field"><span className="visually-hidden">Поиск по компании, телефону или причине</span><Icon name="search"/><input className="input" placeholder="Компания, телефон или причина" value={query} onChange={event => setQuery(event.target.value)}/></label>
        </div>
        <span className="table-count" aria-live="polite">{loading ? 'Обновляем очередь…' : total ? `${firstResult}–${lastResult} из ${total}` : '0 задач'}</span>
      </div>
      <div className="tabs" role="group" aria-label="Фильтр очереди">
        {filterLabels.map(item => <button key={item.id} type="button" className="tab" aria-pressed={filter === item.id} onClick={() => { setFilter(item.id); setPage(1); }}>{item.label}{item.id === 'active' && ` · ${stats?.active ?? '…'}`}</button>)}
      </div>
      {loading ? <Loading text="Загружаем очередь…"/> : error ? null : total === 0 ? <Empty title={queueIsEmpty ? 'Очередь свободна' : historyIsEmpty ? 'Обратных звонков пока нет' : 'Задач не найдено'} text={queueIsEmpty ? 'Новые задачи появятся здесь после звонка или планирования контакта.' : historyIsEmpty ? 'Запланируйте обратный звонок из карточки контакта.' : 'Попробуйте изменить фильтр или поисковый запрос.'} icon="callback"/> : <>
        <div className="table-scroll callbacks-table"><table className="data-table"><thead><tr><th>Контакт</th><th>Причина</th><th>Время</th><th>Статус</th><th><span className="visually-hidden">Действия</span></th></tr></thead><tbody>
          {rows.map(row => <tr key={row.id}><td className="primary-cell"><Link href={`/leads/${row.lead_id}`} className="accent-link">{row.company || `Лид #${row.lead_id}`}</Link><div className="muted" style={{ fontSize: 10, marginTop: 2 }}>{row.phone || 'Телефон не указан'}</div></td><td>{row.reason || 'Обратный звонок'}</td><td>{fmt(row.scheduled_at)}</td><td><StatusBadge status={row.status}/></td><td><div className="callback-actions">{['SCHEDULED', 'DUE'].includes(row.status) && <><button className="btn btn-sm" type="button" onClick={() => openReschedule(row)} aria-label={`Перенести обратный звонок #${row.id}`} disabled={workingId === row.id}>Перенести</button><button className="btn btn-sm" type="button" onClick={() => void updateCallback(row, { status: 'COMPLETED' })} aria-label={`Отметить обратный звонок #${row.id} выполненным`} disabled={workingId === row.id}>Готово</button><button className="btn btn-ghost btn-sm" type="button" onClick={() => setCancelTarget(row)} aria-label={`Отменить обратный звонок #${row.id}`} disabled={workingId === row.id}>Отменить</button></>}</div></td></tr>)}
        </tbody></table></div>
        <div className="callbacks-mobile">
          {rows.map(row => <article className="mobile-record" key={row.id}><div className="mobile-record-head"><div><Link href={`/leads/${row.lead_id}`} className="mobile-record-title">{row.company || `Лид #${row.lead_id}`}</Link><div className="mobile-record-meta">{row.phone || 'Телефон не указан'}</div></div><StatusBadge status={row.status}/></div><div className="mobile-record-meta" style={{ marginTop: 8 }}>{row.reason || 'Обратный звонок'} · {fmt(row.scheduled_at)}</div>{['SCHEDULED', 'DUE'].includes(row.status) && <div className="callback-actions" style={{ marginTop: 10 }}><button className="btn btn-sm" type="button" onClick={() => openReschedule(row)} aria-label={`Перенести обратный звонок #${row.id}`} disabled={workingId === row.id}>Перенести</button><button className="btn btn-sm" type="button" onClick={() => void updateCallback(row, { status: 'COMPLETED' })} aria-label={`Отметить обратный звонок #${row.id} выполненным`} disabled={workingId === row.id}>Готово</button><button className="btn btn-ghost btn-sm" type="button" onClick={() => setCancelTarget(row)} aria-label={`Отменить обратный звонок #${row.id}`} disabled={workingId === row.id}>Отменить</button></div>}</article>)}
        </div>
        {pageCount > 1 && <nav className="pagination" aria-label="Страницы очереди обратных звонков"><span className="table-count">Страница {page} из {pageCount} · {firstResult}–{lastResult} из {total}</span><div><button type="button" className="btn btn-sm" disabled={page <= 1 || loading} onClick={() => setPage(value => value - 1)}>Назад</button><button type="button" className="btn btn-sm" disabled={page >= pageCount || loading} onClick={() => setPage(value => value + 1)}>Вперёд</button></div></nav>}
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
