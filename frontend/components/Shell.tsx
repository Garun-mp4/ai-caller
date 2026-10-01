'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { Icon } from '@/components/UI';

const navigation = [
  { href: '/', label: 'Обзор', icon: 'home' as const },
  { href: '/campaigns', label: 'Кампании', icon: 'campaigns' as const },
  { href: '/leads', label: 'Лиды', icon: 'leads' as const },
  { href: '/callbacks', label: 'Обратные звонки', short: 'Задачи', icon: 'callback' as const },
  { href: '/calls', label: 'История звонков', short: 'Звонки', icon: 'calls' as const },
  { href: '/settings', label: 'Настройки', icon: 'settings' as const },
];
type HealthSnapshot = { llm?: { ok?: boolean }; telephony?: { ok?: boolean } };

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const healthRequested = useRef(false);
  const current = navigation.find(item => item.href === pathname) || navigation.find(item => item.href === '/');
  const currentLabel = pathname.startsWith('/leads/') ? 'Карточка лида' : current?.label;

  useEffect(() => {
    if (pathname !== '/login' && !localStorage.getItem('token')) router.replace('/login');
  }, [pathname, router]);

  useEffect(() => {
    const savedTheme = localStorage.getItem('ai-caller-theme');
    if (savedTheme === 'dark' || savedTheme === 'light') {
      document.documentElement.dataset.theme = savedTheme;
      setTheme(savedTheme);
    } else {
      setTheme(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
    }
  }, []);

  useEffect(() => {
    if (pathname === '/login') {
      healthRequested.current = false;
      return;
    }
    if (!localStorage.getItem('token') || healthRequested.current) return;

    healthRequested.current = true;
    let active = true;
    api<HealthSnapshot>('/providers/health')
      .then(snapshot => { if (active) setHealth(snapshot); })
      .catch(() => { if (active) setHealth({}); });
    return () => { active = false; };
  }, [pathname]);

  function toggleTheme() {
    const next = theme === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('ai-caller-theme', next);
    setTheme(next);
  }

  function signOut() {
    localStorage.removeItem('token');
    healthRequested.current = false;
    setHealth(null);
    router.replace('/login');
  }

  if (pathname === '/login') return <>{children}</>;

  const healthState = health?.llm?.ok && health?.telephony?.ok ? 'is-ready' : health ? 'is-warning' : '';
  const healthLabel = health ? (health?.llm?.ok && health?.telephony?.ok ? 'Сервисы готовы' : 'Нужна проверка') : 'Проверяем сервисы';

  return <div className="app-frame">
    <aside className="sidebar" aria-label="Боковая панель">
      <Link href="/" className="sidebar-brand" aria-label="AI Call Agent — на главную">
        <span className="brand-mark"><Icon name="activity"/></span><span>AI Call Agent</span>
      </Link>
      <div className="sidebar-section">Рабочее пространство</div>
      <nav className="sidebar-nav" aria-label="Основная навигация">
        {navigation.map(item => <Link key={item.href} href={item.href} className="nav-link" aria-current={pathname === item.href ? 'page' : undefined}>
          <Icon name={item.icon}/><span>{item.label}</span>
        </Link>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="operator-row">
          <span className="operator-avatar" aria-hidden="true">ОП</span>
          <div className="operator-copy"><strong>Оператор</strong><span><i className={`status-dot ${healthState}`} aria-hidden="true"/>{healthLabel}</span></div>
          <button type="button" className="icon-button" aria-label="Выйти из аккаунта" onClick={signOut} title="Выйти"><Icon name="logout"/></button>
        </div>
      </div>
    </aside>

    <div className="main-shell">
      <header className="topbar">
        <div className="topbar-left">
          <Link href="/" className="mobile-brand"><span className="brand-mark"><Icon name="activity"/></span><span>AI Call Agent</span></Link>
          <span className="topbar-context">Пространство оператора</span><span className="topbar-separator topbar-context">/</span><span className="topbar-context">{currentLabel}</span>
        </div>
        <div className="topbar-actions">
          <span className="topbar-context">Локальное рабочее пространство</span>
          <button type="button" className="theme-button" onClick={toggleTheme} aria-label={theme === 'light' ? 'Включить тёмную тему' : 'Включить светлую тему'} title={theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}>
            <Icon name={theme === 'light' ? 'moon' : 'sun'}/>
          </button>
        </div>
      </header>
      <main id="main-content" className="page-container">{children}</main>
    </div>

    <nav className="mobile-nav" aria-label="Основная навигация">
      {navigation.map(item => <Link key={item.href} href={item.href} aria-current={pathname === item.href ? 'page' : undefined}>
        <Icon name={item.icon}/><span>{item.short || item.label}</span>
      </Link>)}
    </nav>
  </div>;
}
