import type { ReactNode } from 'react';

type IconName = 'home' | 'campaigns' | 'leads' | 'callback' | 'calls' | 'settings' | 'sun' | 'moon' | 'search' | 'plus' | 'upload' | 'arrow' | 'phone' | 'clock' | 'users' | 'spark' | 'check' | 'warning' | 'refresh' | 'file' | 'activity' | 'calendar' | 'chevron' | 'close' | 'info' | 'save' | 'edit' | 'play' | 'pause' | 'stop' | 'external' | 'shield' | 'building' | 'logout';

const iconPaths: Record<IconName, ReactNode> = {
  home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-6h6v6"/></>,
  campaigns: <><path d="M4 19V5M4 19h17"/><path d="m7 15 4-4 3 2 6-7"/><path d="M16 6h4v4"/></>,
  leads: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M16 11a3 3 0 0 0 0-6M18 14a5 5 0 0 1 3 4.6V20"/></>,
  callback: <><path d="M20 11a8 8 0 1 0 2 5"/><path d="M20 4v7h-7"/><path d="M12 8v4l3 2"/></>,
  calls: <><path d="M6.6 3.7 9 3l2 5-2 1.5a14 14 0 0 0 5.5 5.5L16 13l5 2-.7 2.4A3 3 0 0 1 17.4 20 14.4 14.4 0 0 1 4 6.6a3 3 0 0 1 2.6-2.9Z"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.4 1.1-1.5 2.6-1.7-.7a8 8 0 0 1-1.7 1l-.3 1.9h-3l-.3-1.9a8 8 0 0 1-1.7-1l-1.7.7-1.5-2.6 1.4-1.1a7 7 0 0 1 0-2l-1.4-1.1 1.5-2.6 1.7.7a8 8 0 0 1 1.7-1l.3-1.9h3l.3 1.9a8 8 0 0 1 1.7 1l1.7-.7 1.5 2.6-1.4 1.1a7 7 0 0 1 0 2Z" transform="translate(-1 -1)"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></>,
  moon: <path d="M20.8 13A8.5 8.5 0 0 1 11 3.2 8.5 8.5 0 1 0 20.8 13Z"/>,
  search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4 4"/></>,
  plus: <><path d="M12 5v14M5 12h14"/></>,
  upload: <><path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M5 14v5h14v-5"/></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  phone: <path d="M6.6 3.7 9 3l2 5-2 1.5a14 14 0 0 0 5.5 5.5L16 13l5 2-.7 2.4A3 3 0 0 1 17.4 20 14.4 14.4 0 0 1 4 6.6a3 3 0 0 1 2.6-2.9Z"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  users: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M16 11a3 3 0 0 0 0-6M18 14a5 5 0 0 1 3 4.6V20"/></>,
  spark: <><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z"/><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  warning: <><path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3h.01"/></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.6 9A7 7 0 0 1 18 6.3L20 12M4 12l2 5.7A7 7 0 0 0 18.4 15"/></>,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8m-8 4h8"/></>,
  activity: <path d="M3 12h4l3-8 4 16 3-8h4"/>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
  chevron: <path d="m9 18 6-6-6-6"/>,
  close: <><path d="m6 6 12 12M18 6 6 18"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></>,
  save: <><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><path d="M17 21v-8H7v8M7 3v5h8"/></>,
  edit: <><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></>,
  play: <path d="m7 4 13 8-13 8V4Z"/>,
  pause: <><path d="M8 5v14M16 5v14"/></>,
  stop: <rect x="5" y="5" width="14" height="14" rx="2"/>,
  external: <><path d="M14 3h7v7m0-7-9 9"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></>,
  shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
  building: <><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 7h1m4 0h1m-6 4h1m4 0h1m-5 4h2m5 6v-4h-4v4"/></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></>
};

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return <svg aria-hidden="true" className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{iconPaths[name]}</svg>;
}

const statusLabels: Record<string, string> = {
  NEW: 'Новый', QUEUED: 'В очереди', CALLING: 'Звоним', NO_ANSWER: 'Нет ответа', BUSY: 'Занято', FAILED: 'Ошибка',
  NOT_INTERESTED: 'Нет интереса', CALLBACK: 'Перезвонить', INTERESTED: 'Есть интерес', HOT_LEAD: 'Горячий лид',
  DO_NOT_CALL: 'Не звонить', DONE: 'Завершён', DRAFT: 'Черновик', RUNNING: 'Активна', PAUSED: 'На паузе', STOPPED: 'Остановлена',
  SCHEDULED: 'Запланирован', DUE: 'Пора связаться', COMPLETED: 'Выполнен', CANCELED: 'Отменён', STARTING: 'Подключаемся',
  IN_PROGRESS: 'Идёт звонок', ANSWERED: 'Отвечен', END_CALL: 'Нет интереса', CONTINUE: 'Разговор продолжается',
  CALLBACK_REQUESTED: 'Запрошен обратный звонок',
};
const statusTones: Record<string, string> = {
  INTERESTED: 'success', HOT_LEAD: 'success', DONE: 'success', COMPLETED: 'success', ANSWERED: 'success',
  CALLBACK: 'warning', BUSY: 'warning', NO_ANSWER: 'warning', DUE: 'warning', SCHEDULED: 'warning', PAUSED: 'warning',
  FAILED: 'danger', DO_NOT_CALL: 'danger', CANCELED: 'danger', STOPPED: 'danger',
  QUEUED: 'info', CALLING: 'info', RUNNING: 'info', IN_PROGRESS: 'info', STARTING: 'info',
};

export function StatusBadge({ status }: { status?: string | null }) {
  const key = (status || '').trim().toUpperCase().replace(/[\s-]+/g, '_');
  const tone = statusTones[key] || 'neutral';
  return <span className={`badge badge-${tone}`}>{statusLabels[key] || 'Неизвестный статус'}</span>;
}

export function resultLabel(value?: string | null) {
  if (!value?.trim()) return '—';
  const key = value.trim().toUpperCase().replace(/[\s-]+/g, '_');
  return statusLabels[key] || 'Неизвестный результат';
}

export function Header({ title, sub, children, breadcrumb }: { title: string; sub?: string; children?: ReactNode; breadcrumb?: ReactNode }) {
  return <header className="page-header"><div>{breadcrumb && <nav className="breadcrumb" aria-label="Хлебные крошки">{breadcrumb}</nav>}<h1 className="page-title">{title}</h1>{sub && <p className="page-subtitle">{sub}</p>}</div>{children && <div className="page-actions">{children}</div>}</header>;
}

export function PanelHeading({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="section-heading"><div><h2 className="section-title">{title}</h2>{description && <p className="section-description">{description}</p>}</div>{action}</div>;
}

export function Metric({ label, value, icon, footnote }: { label: string; value?: ReactNode; icon?: IconName; footnote?: string }) {
  return <section className="card metric-card"><div className="metric-label"><span>{label}</span>{icon && <span className="metric-icon"><Icon name={icon}/></span>}</div><div className="metric-value">{value ?? '—'}</div>{footnote && <div className="metric-footnote">{footnote}</div>}</section>;
}

export function Empty({ title, text, action, icon = 'file' }: { title: string; text?: string; action?: ReactNode; icon?: IconName }) {
  return <div className="empty-state"><div className="empty-icon"><Icon name={icon}/></div><h3 className="empty-title">{title}</h3>{text && <p className="empty-copy">{text}</p>}{action && <div className="empty-action">{action}</div>}</div>;
}

export function Loading({ text = 'Загружаем данные…' }: { text?: string }) {
  return <div className="loading-state" role="status"><span className="spinner" aria-hidden="true"/>{text}</div>;
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'success' | 'warning' | 'danger' }) {
  const icon: Record<typeof tone, IconName> = { info: 'info', success: 'check', warning: 'warning', danger: 'warning' };
  return <div className={`notice notice-${tone}`} role={tone === 'danger' ? 'alert' : 'status'}><Icon name={icon[tone]}/><div>{children}</div></div>;
}

export function fmt(value?: string | null, withTime = true) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('ru-RU', withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' }).format(date);
}

export function fmtDuration(seconds?: number | null) {
  if (!seconds || seconds < 0) return '0:00';
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
}

export function friendlyError(error: unknown) {
  const message = error instanceof Error ? error.message : '';
  const translations: Record<string, string> = {
    'Invalid credentials': 'Логин или пароль указаны неверно.',
    'Local login disabled': 'Локальный вход отключён в настройках сервера.',
    'Lead is DO_NOT_CALL': 'Для этого контакта запрещены звонки.',
    'Compliance confirmation is required': 'Подтвердите право связываться с лидами перед запуском.',
    'Only TXT files are allowed': 'Для импорта выберите файл в формате TXT.',
    'TXT file is too large': 'Файл слишком большой. Разделите его на несколько файлов.',
    'File must be UTF-8 or CP1251 text': 'Не удалось прочитать файл. Сохраните его в UTF-8 или Windows-1251.',
    'Lead not found': 'Лид не найден. Возможно, его уже удалили.',
    'Campaign not found': 'Кампания не найдена. Обновите список.',
    'Callback not found': 'Обратный звонок не найден. Обновите список.',
  };
  return translations[message] || 'Не удалось выполнить запрос. Проверьте соединение с сервером и попробуйте ещё раз.';
}

export function localDateTimeValue(date: Date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}
