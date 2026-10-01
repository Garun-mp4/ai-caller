'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { Empty, fmt, fmtDuration, friendlyError, Header, Icon, Loading, Metric, Notice, StatusBadge } from '@/components/UI';

type Call = { id: number; lead_id: number; campaign_id?: number | null; phone: string; started_at: string; answered_at?: string | null; ended_at?: string | null; duration: number; status: string; result?: string | null; summary?: string; stt_ms: number; llm_ms: number; tts_ms: number; total_ms: number; transcripts: Array<{ id: number; role: string; content: string; timestamp: string }> };
const callFilters = [['', 'Все звонки'], ['ANSWERED', 'Ответили'], ['NO_ANSWER', 'Нет ответа'], ['BUSY', 'Занято'], ['FAILED', 'Ошибка'], ['IN_PROGRESS', 'В процессе']];

export default function Calls() {
  const [rows, setRows] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  async function load() {
    setLoading(true); setError('');
    try { setRows(await api<Call[]>('/calls')); }
    catch (requestError) { setError(friendlyError(requestError)); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  const filteredRows = useMemo(() => rows.filter(call => {
    const callStatus = (call.result || call.status || '').toUpperCase();
    const matchesStatus = !status || callStatus === status || call.status === status;
    return matchesStatus && (!query.trim() || call.phone.includes(query.trim()));
  }), [rows, query, status]);
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const visibleRows = filteredRows.slice((page - 1) * pageSize, page * pageSize);
  const answered = rows.filter(call => Boolean(call.answered_at) || call.status === 'ANSWERED').length;
  const totalDuration = rows.reduce((sum, call) => sum + (call.duration || 0), 0);
  const averageDuration = rows.length ? Math.round(totalDuration / rows.length) : 0;

  return <>
    <Header title="Звонки" sub="История контактов, результаты и расшифровки"/>
    {error && <div className="feedback"><Notice tone="danger">{error} <button className="btn btn-sm" onClick={load}>Повторить</button></Notice></div>}
    {!loading && !error && <div className="metric-grid"><Metric label="Всего звонков" value={rows.length} icon="phone"/><Metric label="Ответили" value={answered} icon="check"/><Metric label="Средняя длительность" value={fmtDuration(averageDuration)} icon="clock"/><Metric label="С расшифровкой" value={rows.filter(call => call.transcripts?.length).length} icon="file"/></div>}
    <section className="card" aria-label="История звонков">
      <div className="table-toolbar"><div className="table-filters">
        <label className="search-field"><span className="visually-hidden">Поиск по номеру телефона</span><Icon name="search"/><input className="input" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} placeholder="Поиск по телефону"/></label>
        <label><span className="visually-hidden">Фильтр по результату</span><select className="select" value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}>{callFilters.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      </div><span className="table-count">{filteredRows.length} из {rows.length}</span></div>
      {loading ? <Loading text="Загружаем историю…"/> : error ? null : filteredRows.length === 0 ? <Empty title={rows.length ? 'Звонки не найдены' : 'История пока пуста'} text={rows.length ? 'Попробуйте изменить поиск или фильтр.' : 'Здесь появятся результаты и расшифровки первых звонков.'} icon="phone"/> : <div className="panel-content calls-list">
        {visibleRows.map(call => <details className="card call-card" key={call.id}>
          <summary className="call-summary-row"><span className="call-summary-main"><span className="activity-mark"><Icon name="phone"/></span><span><span className="call-phone">{call.phone || `Лид #${call.lead_id}`}</span><span className="call-list-meta">{fmt(call.started_at)} · {fmtDuration(call.duration)}</span></span></span><span className="call-summary-end"><StatusBadge status={call.result || call.status}/><Icon name="chevron" size={14}/></span></summary>
          <div className="call-expanded">
            <div className="call-expanded-header"><div><p className="call-summary">{call.summary || 'Краткая сводка отсутствует.'}</p><div className="call-timings">Речь STT {Math.round(call.stt_ms || 0)} мс · AI {Math.round(call.llm_ms || 0)} мс · голос {Math.round(call.tts_ms || 0)} мс · всего {Math.round(call.total_ms || 0)} мс</div></div><Link href={`/leads/${call.lead_id}`} className="btn btn-sm">Открыть лида <Icon name="arrow" size={12}/></Link></div>
            {call.transcripts?.length ? <div className="call-transcript">{call.transcripts.map(message => <div className="transcript" key={message.id}><span className="transcript-role">{message.role === 'assistant' ? 'Ассистент' : message.role === 'user' ? 'Собеседник' : 'Система'} · {fmt(message.timestamp)}</span>{message.content}</div>)}</div> : <p className="section-description" style={{ marginTop: 14 }}>Расшифровка для этого звонка недоступна.</p>}
          </div>
        </details>)}
        {pageCount > 1 && <div className="pagination"><span className="table-count">Страница {page} из {pageCount}</span><div><button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Назад</button><button className="btn btn-sm" disabled={page >= pageCount} onClick={() => setPage(value => value + 1)}>Вперёд</button></div></div>}
      </div>}
    </section>
  </>;
}
