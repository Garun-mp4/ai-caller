'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Empty, fmt, Header, Icon, Loading, Metric, Notice, PanelHeading, StatusBadge } from '@/components/UI';

type DashboardData = {
  stats: { total_leads: number; calls_today: number; answered: number; interested: number; hot_leads: number; callbacks: number; no_answer: number };
  recent_calls: Array<{ id: number; lead_id: number; phone: string; summary?: string; result?: string; status: string; started_at: string }>;
  callbacks: Array<{ id: number; lead_id: number; reason: string; scheduled_at: string; status: string }>;
};

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true); setError('');
    try { setData(await api<DashboardData>('/dashboard')); }
    catch { setError('Не удалось загрузить сводку. Проверьте соединение с сервером и попробуйте ещё раз.'); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);
  const stats = data?.stats;

  return <>
    <Header title="Обзор" sub="Главное по работе с лидами, звонками и следующими задачами"/>
    {error && <div className="feedback"><Notice tone="danger">{error} <button className="btn btn-sm" onClick={load}>Повторить</button></Notice></div>}
    {loading ? <Loading/> : data && <>
      <div className="metric-grid">
        <Metric label="Всего лидов" value={stats?.total_leads?.toLocaleString('ru-RU')} icon="users"/>
        <Metric label="Звонки сегодня" value={stats?.calls_today?.toLocaleString('ru-RU')} icon="phone"/>
        <Metric label="Обратные звонки" value={stats?.callbacks?.toLocaleString('ru-RU')} icon="callback" footnote="Лиды, ожидающие продолжения"/>
        <Metric label="Горячие лиды" value={stats?.hot_leads?.toLocaleString('ru-RU')} icon="building"/>
      </div>
      <section className="result-strip" aria-label="Результаты контактов"><div className="result-heading">Результаты контактов</div><div className="result-item"><strong>{stats?.answered?.toLocaleString('ru-RU') ?? '—'}</strong><span>Ответили</span></div><div className="result-item"><strong>{stats?.interested?.toLocaleString('ru-RU') ?? '—'}</strong><span>Есть интерес</span></div><div className="result-item"><strong>{stats?.no_answer?.toLocaleString('ru-RU') ?? '—'}</strong><span>Нет ответа</span></div></section>

      <div className="dashboard-grid">
        <div className="stack">
          <section className="card">
            <div className="panel-header"><div><h2 className="section-title">Недавние звонки</h2><p className="section-description">Последние результаты и контакты</p></div><Link className="btn btn-ghost btn-sm" href="/calls">Все звонки <Icon name="arrow" size={13}/></Link></div>
            <div className="panel-content">
              {data.recent_calls.length ? data.recent_calls.map(call => <div className="activity-row" key={call.id}>
                <span className="activity-mark"><Icon name="phone"/></span>
                <div className="activity-copy"><Link className="activity-title" href={`/leads/${call.lead_id}`}>{call.phone || 'Контакт без номера'}</Link><div className="activity-meta">{call.summary || call.result || `Звонок #${call.id}`} · {fmt(call.started_at)}</div></div>
                <div className="activity-end"><StatusBadge status={call.result || call.status}/></div>
              </div>) : <Empty title="Звонков пока нет" text="После первого звонка здесь появится его результат и краткая сводка." icon="phone" action={<Link className="btn btn-sm" href="/leads">Открыть лиды</Link>}/>}
            </div>
          </section>

          <section className="card">
            <div className="panel-header"><div><h2 className="section-title">Ближайшие задачи</h2><p className="section-description">Запланированные обратные звонки</p></div><Link className="btn btn-ghost btn-sm" href="/callbacks">Открыть очередь <Icon name="arrow" size={13}/></Link></div>
            <div className="panel-content">
              {data.callbacks.length ? data.callbacks.map(callback => <div className="activity-row" key={callback.id}>
                <span className="activity-mark"><Icon name="calendar"/></span>
                <div className="activity-copy"><Link className="activity-title" href={`/leads/${callback.lead_id}`}>{callback.reason || 'Обратный звонок'}</Link><div className="activity-meta">Лид #{callback.lead_id} · {fmt(callback.scheduled_at)}</div></div>
                <StatusBadge status={callback.status}/>
              </div>) : <Empty title="Нет запланированных звонков" text="Добавьте обратный звонок из карточки лида, чтобы не потерять следующий шаг." icon="calendar" action={<Link className="btn btn-sm" href="/leads">Найти лид</Link>}/>}
            </div>
          </section>
        </div>

        <aside className="stack">
          <section className="card card-body">
            <PanelHeading title="Быстрый переход" description="Частые действия оператора"/>
            <div className="quick-actions">
              <Link href="/leads" className="quick-action"><Icon name="users"/><span>Лиды</span><Icon name="arrow"/></Link>
              <Link href="/campaigns" className="quick-action"><Icon name="campaigns"/><span>Кампании</span><Icon name="arrow"/></Link>
              <Link href="/callbacks" className="quick-action"><Icon name="callback"/><span>Очередь звонков</span><Icon name="arrow"/></Link>
              <Link href="/settings" className="quick-action"><Icon name="settings"/><span>Настройки агента</span><Icon name="arrow"/></Link>
            </div>
          </section>
          <section className="card card-body">
            <PanelHeading title="Рабочий режим"/>
            <Notice tone="info">Перед запуском кампании проверьте список лидов и подтвердите право на связь. Лиды со статусом «Не звонить» исключаются из очереди.</Notice>
            <div style={{ marginTop: 13 }}><Link className="accent-link" href="/campaigns">Подготовить кампанию <Icon name="arrow" size={13}/></Link></div>
          </section>
        </aside>
      </div>
    </>}
  </>;
}
