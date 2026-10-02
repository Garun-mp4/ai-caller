'use client';

import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Empty, fmt, friendlyError, Header, Icon, Loading, Notice, resultLabel, StatusBadge } from '@/components/UI';

type LeadRow = {
  id: number; phone: string; name?: string | null; company?: string | null; status: string; attempts: number;
  last_call_at?: string | null; next_call_at?: string | null; result?: string | null;
};
type LeadPage = { items: LeadRow[]; total: number; page: number; page_size: number; page_count: number };
type Campaign = { id: number; name: string };
type SortField = 'id' | 'company' | 'phone' | 'status' | 'attempts' | 'last_call_at' | 'next_call_at';

const statusFilters = [
  ['NEW', 'Новые'], ['QUEUED', 'В очереди'], ['CALLING', 'Звоним'], ['CALLBACK', 'Обратный звонок'],
  ['INTERESTED', 'Есть интерес'], ['HOT_LEAD', 'Горячие'], ['NO_ANSWER', 'Нет ответа'], ['BUSY', 'Занято'],
  ['NOT_INTERESTED', 'Нет интереса'], ['DONE', 'Завершённые'], ['FAILED', 'Ошибка'], ['DO_NOT_CALL', 'Не звонить'],
];
const pageSize = 25;

function leadWord(count: number) {
  const mod100 = count % 100;
  if (mod100 >= 11 && mod100 <= 14) return 'лидов';
  const mod10 = count % 10;
  if (mod10 === 1) return 'лид';
  if (mod10 >= 2 && mod10 <= 4) return 'лида';
  return 'лидов';
}

export default function Leads() {
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [total, setTotal] = useState(0);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [status, setStatus] = useState('');
  const [campaign, setCampaign] = useState('');
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const [sortBy, setSortBy] = useState<SortField>('id');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => { api<Campaign[]>('/campaigns').then(setCampaigns).catch(() => setCampaigns([])); }, []);

  useEffect(() => {
    let current = true;
    setLoading(true); setError('');
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), sort_by: sortBy, sort_order: sortOrder });
    if (status) params.set('status', status);
    if (campaign) params.set('campaign', campaign);
    if (submittedQuery.trim()) params.set('search', submittedQuery.trim());
    api<LeadPage>(`/leads?${params.toString()}`)
      .then(result => {
        if (!current) return;
        setRows(result.items); setTotal(result.total); setPageCount(result.page_count);
        if (page > result.page_count) setPage(result.page_count);
      })
      .catch(requestError => { if (current) setError(friendlyError(requestError)); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [status, campaign, submittedQuery, page, sortBy, sortOrder, reloadKey]);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSubmittedQuery(query); setPage(1); setReloadKey(value => value + 1);
  }

  function resetFilters() {
    setStatus(''); setCampaign(''); setQuery(''); setSubmittedQuery(''); setPage(1);
  }

  function sort(field: SortField) {
    setPage(1);
    if (field === sortBy) setSortOrder(value => value === 'asc' ? 'desc' : 'asc');
    else { setSortBy(field); setSortOrder(field === 'company' ? 'asc' : 'desc'); }
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
      resetFilters(); setReloadKey(value => value + 1);
    } catch (requestError) {
      setFeedback({ tone: 'danger', text: friendlyError(requestError) });
    } finally {
      setImporting(false); input.value = '';
    }
  }

  const hasFilters = Boolean(status || campaign || submittedQuery);
  const firstRow = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastRow = Math.min(page * pageSize, total);
  const sortableHeader = (field: SortField, label: string) => {
    const active = sortBy === field;
    const direction = active ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none';
    return <th aria-sort={direction}><button type="button" className="table-sort" onClick={() => sort(field)} aria-label={`Сортировать по полю «${label}»${active ? sortOrder === 'asc' ? ' по убыванию' : ' по возрастанию' : ''}`}><span>{label}</span><Icon name="chevron" size={12} className={`table-sort-icon${active ? ` is-${sortOrder}` : ''}`}/></button></th>;
  };

  return <>
    <Header title="Лиды" sub="Контакты и история следующих действий">
      <label className={`btn btn-primary${importing ? ' disabled' : ''}`} htmlFor="lead-import"><Icon name="upload"/>{importing ? 'Импортируем…' : 'Импортировать TXT'}<input id="lead-import" type="file" accept=".txt,text/plain" className="sr-only" onChange={upload} disabled={importing}/></label>
    </Header>
    {feedback && <div className="feedback"><Notice tone={feedback.tone}>{feedback.text}</Notice></div>}
    {error && <div className="feedback"><Notice tone="danger">{error} <button className="btn btn-sm" onClick={() => setReloadKey(value => value + 1)}>Повторить</button></Notice></div>}

    <section className="card" aria-label="Список лидов">
      <form className="table-toolbar" onSubmit={search}>
        <div className="table-filters">
          <label className="search-field"><span className="sr-only">Поиск по имени, компании или телефону</span><Icon name="search"/><input className="input" placeholder="Имя, компания или телефон" value={query} onChange={event => setQuery(event.target.value)}/></label>
          <label><span className="sr-only">Фильтр по статусу</span><select className="select" value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}><option value="">Все статусы</option>{statusFilters.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <label><span className="sr-only">Фильтр по кампании</span><select className="select" value={campaign} onChange={event => { setCampaign(event.target.value); setPage(1); }}><option value="">Все кампании</option>{campaigns.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <button type="submit" className="btn">Найти</button>
        </div>
        <div className="table-actions"><span className="table-count">{total.toLocaleString('ru-RU')} {leadWord(total)}</span>{hasFilters && <button type="button" className="btn btn-ghost btn-sm" onClick={resetFilters}>Сбросить фильтры</button>}</div>
      </form>

      {loading ? <Loading text="Загружаем лиды…"/> : error ? null : rows.length === 0 ? <Empty title={hasFilters ? 'Ничего не найдено' : 'Список лидов пока пуст'} text={hasFilters ? 'Измените условия поиска или сбросьте фильтры.' : 'Импортируйте TXT-файл, чтобы добавить первые контакты в CRM.'} icon={hasFilters ? 'search' : 'users'} action={hasFilters ? <button type="button" className="btn btn-sm" onClick={resetFilters}>Сбросить фильтры</button> : undefined}/> : <>
        <div className="table-scroll leads-table"><table className="data-table"><thead><tr>
          {sortableHeader('company', 'Компания / контакт')}{sortableHeader('phone', 'Телефон')}{sortableHeader('status', 'Статус')}{sortableHeader('attempts', 'Попытки')}{sortableHeader('last_call_at', 'Последний звонок')}{sortableHeader('next_call_at', 'Следующий шаг')}<th>Результат</th>
        </tr></thead><tbody>
          {rows.map(lead => <tr key={lead.id}><td className="primary-cell"><Link href={`/leads/${lead.id}`} className="accent-link">{lead.company || lead.name || `Лид #${lead.id}`}</Link></td><td>{lead.phone}</td><td><StatusBadge status={lead.status}/></td><td>{lead.attempts}</td><td>{fmt(lead.last_call_at)}</td><td>{fmt(lead.next_call_at)}</td><td>{resultLabel(lead.result)}</td></tr>)}
        </tbody></table></div>
        <div className="leads-mobile">
          {rows.map(lead => <article className="mobile-record" key={lead.id}><div className="mobile-record-head"><div><Link className="mobile-record-title" href={`/leads/${lead.id}`}>{lead.company || lead.name || `Лид #${lead.id}`}</Link><div className="mobile-record-meta">{lead.phone}</div></div><StatusBadge status={lead.status}/></div><div className="mobile-record-facts"><span>Попыток: {lead.attempts}</span><span>Далее: {fmt(lead.next_call_at)}</span></div></article>)}
        </div>
        {pageCount > 1 && <nav className="pagination" aria-label="Страницы лидов"><span className="table-count">Страница {page} из {pageCount} · {firstRow}–{lastRow} из {total.toLocaleString('ru-RU')}</span><div><button type="button" className="btn btn-sm" disabled={page <= 1 || loading} onClick={() => setPage(value => value - 1)}>Назад</button><button type="button" className="btn btn-sm" disabled={page >= pageCount || loading} onClick={() => setPage(value => value + 1)}>Вперёд</button></div></nav>}
      </>}
    </section>
  </>;
}
