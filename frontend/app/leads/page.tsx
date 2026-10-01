'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import { api } from '@/lib/api';
import { Empty, fmt, friendlyError, Header, Icon, Loading, Notice, resultLabel, StatusBadge } from '@/components/UI';

type LeadRow = {
  id: number; phone: string; name?: string | null; company?: string | null; status: string; attempts: number;
  last_call_at?: string | null; next_call_at?: string | null; result?: string | null;
};
type Campaign = { id: number; name: string };

const statusFilters = [
  ['NEW', 'Новые'], ['QUEUED', 'В очереди'], ['CALLING', 'Звоним'], ['CALLBACK', 'Обратный звонок'],
  ['INTERESTED', 'Есть интерес'], ['HOT_LEAD', 'Горячие'], ['NO_ANSWER', 'Нет ответа'], ['BUSY', 'Занято'],
  ['NOT_INTERESTED', 'Нет интереса'], ['DONE', 'Завершённые'], ['FAILED', 'Ошибка'], ['DO_NOT_CALL', 'Не звонить'],
];
const pageSize = 25;

export default function Leads() {
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [status, setStatus] = useState('');
  const [campaign, setCampaign] = useState('');
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => { api<Campaign[]>('/campaigns').then(setCampaigns).catch(() => setCampaigns([])); }, []);

  useEffect(() => {
    let current = true;
    setLoading(true); setError('');
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (campaign) params.set('campaign', campaign);
    if (submittedQuery.trim()) params.set('search', submittedQuery.trim());
    api<LeadRow[]>(`/leads${params.size ? `?${params.toString()}` : ''}`)
      .then(result => { if (current) setRows(result); })
      .catch(error => { if (current) setError(friendlyError(error)); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [status, campaign, submittedQuery, reloadKey]);

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const visibleRows = useMemo(() => rows.slice((page - 1) * pageSize, page * pageSize), [rows, page]);
  useEffect(() => { setPage(1); }, [status, campaign, submittedQuery, reloadKey]);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSubmittedQuery(query); setPage(1); setReloadKey(value => value + 1);
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    setImporting(true); setFeedback(null);
    const form = new FormData(); form.append('file', file);
    try {
      const result = await api<{ imported: number; duplicates: number; invalid: number }>('/leads/import', { method: 'POST', body: form });
      setFeedback({ tone: 'success', text: `Импорт завершён: добавлено ${result.imported}, дубликатов ${result.duplicates}, пропущено ${result.invalid}.` });
      setSubmittedQuery(''); setQuery(''); setStatus(''); setCampaign('');
      const updated = await api<LeadRow[]>('/leads'); setRows(updated);
    } catch (error) {
      setFeedback({ tone: 'danger', text: friendlyError(error) });
    } finally {
      setImporting(false); input.value = '';
    }
  }

  const hasFilters = Boolean(status || campaign || submittedQuery);

  return <>
    <Header title="Лиды" sub="Контакты и история следующих действий">
      <label className={`btn btn-primary${importing ? ' disabled' : ''}`} htmlFor="lead-import"><Icon name="upload"/>{importing ? 'Импортируем…' : 'Импортировать TXT'}<input id="lead-import" type="file" accept=".txt,text/plain" className="sr-only" onChange={upload} disabled={importing}/></label>
    </Header>
    {feedback && <div className="feedback"><Notice tone={feedback.tone}>{feedback.text}</Notice></div>}
    {error && <div className="feedback"><Notice tone="danger">{error} <button className="btn btn-sm" onClick={() => setReloadKey(value => value + 1)}>Повторить</button></Notice></div>}

    <section className="card" aria-label="Список лидов">
      <form className="table-toolbar" onSubmit={search}>
        <div className="table-filters">
          <label className="search-field"><span className="sr-only">Поиск по телефону или компании</span><Icon name="search"/><input className="input" placeholder="Компания или телефон" value={query} onChange={event => setQuery(event.target.value)}/></label>
          <label><span className="sr-only">Фильтр по статусу</span><select className="select" value={status} onChange={event => setStatus(event.target.value)}><option value="">Все статусы</option>{statusFilters.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <label><span className="sr-only">Фильтр по кампании</span><select className="select" value={campaign} onChange={event => setCampaign(event.target.value)}><option value="">Все кампании</option>{campaigns.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <button type="submit" className="btn">Найти</button>
        </div>
        <div className="table-actions"><span className="table-count">{rows.length.toLocaleString('ru-RU')} {rows.length === 1 ? 'лид' : 'лидов'}</span>{hasFilters && <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setStatus(''); setCampaign(''); setQuery(''); setSubmittedQuery(''); }}>Сбросить фильтры</button>}</div>
      </form>

      {loading ? <Loading text="Загружаем лиды…"/> : error ? null : rows.length === 0 ? <Empty title={hasFilters ? 'Ничего не найдено' : 'Список лидов пока пуст'} text={hasFilters ? 'Измените условия поиска или сбросьте фильтры.' : 'Импортируйте TXT-файл, чтобы добавить первые контакты в CRM.'} icon={hasFilters ? 'search' : 'users'} action={hasFilters ? <button type="button" className="btn btn-sm" onClick={() => { setStatus(''); setCampaign(''); setQuery(''); setSubmittedQuery(''); }}>Сбросить фильтры</button> : undefined}/> : <>
        <div className="table-scroll leads-table"><table className="data-table"><thead><tr><th>Компания / контакт</th><th>Телефон</th><th>Статус</th><th>Попытки</th><th>Последний звонок</th><th>Следующий шаг</th><th>Результат</th></tr></thead><tbody>
          {visibleRows.map(lead => <tr key={lead.id}><td className="primary-cell"><Link href={`/leads/${lead.id}`} className="accent-link">{lead.company || lead.name || `Лид #${lead.id}`}</Link></td><td>{lead.phone}</td><td><StatusBadge status={lead.status}/></td><td>{lead.attempts}</td><td>{fmt(lead.last_call_at)}</td><td>{fmt(lead.next_call_at)}</td><td>{resultLabel(lead.result)}</td></tr>)}
        </tbody></table></div>
        <div className="leads-mobile">
          {visibleRows.map(lead => <article className="mobile-record" key={lead.id}><div className="mobile-record-head"><div><Link className="mobile-record-title" href={`/leads/${lead.id}`}>{lead.company || lead.name || `Лид #${lead.id}`}</Link><div className="mobile-record-meta">{lead.phone}</div></div><StatusBadge status={lead.status}/></div><div className="mobile-record-facts"><span>Попыток: {lead.attempts}</span><span>Далее: {fmt(lead.next_call_at)}</span></div></article>)}
        </div>
        {pageCount > 1 && <div className="pagination"><span className="table-count">Страница {page} из {pageCount}</span><div><button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Назад</button><button type="button" className="btn btn-sm" disabled={page >= pageCount} onClick={() => setPage(value => value + 1)}>Вперёд</button></div></div>}
      </>}
    </section>
  </>;
}
