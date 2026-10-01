'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { api, API } from '@/lib/api';
import { friendlyError, Icon, Notice } from '@/components/UI';

type AuthConfig = { mode: string; chatgpt_oauth_available: boolean };

export default function Login() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let current = true;
    api<AuthConfig>('/auth/config').then(result => { if (current) setConfig(result); }).catch(() => { if (current) setConfig(null); }).finally(() => { if (current) setConfigLoading(false); });
    const token = new URLSearchParams(window.location.search).get('token');
    if (token) {
      localStorage.setItem('token', token);
      window.history.replaceState({}, '', '/login');
      router.replace('/');
    }
    return () => { current = false; };
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setSubmitting(true);
    try {
      const result = await api<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ username: username.trim(), password }) });
      localStorage.setItem('token', result.access_token);
      router.replace('/');
    } catch (requestError) { setError(friendlyError(requestError)); }
    finally { setSubmitting(false); }
  }

  const usesChatGPT = config?.mode === 'chatgpt';

  return <main className="login-screen">
    <section className="card login-card" aria-labelledby="login-title">
      <div className="login-logo"><span className="brand-mark"><Icon name="activity"/></span><span>AI Call Agent</span></div>
      <h1 className="login-heading" id="login-title">{usesChatGPT ? 'Вход в рабочее пространство' : 'Рады видеть вас'}</h1>
      <p className="login-description">{usesChatGPT ? 'Авторизуйтесь с помощью аккаунта ChatGPT, чтобы продолжить.' : 'Войдите, чтобы работать с лидами и кампаниями.'}</p>
      {error && <div className="feedback"><Notice tone="danger">{error}</Notice></div>}
      {configLoading ? <div className="loading-state"><span className="spinner" aria-hidden="true"/>Проверяем способ входа…</div> : usesChatGPT ? <>
        {config?.chatgpt_oauth_available
          ? <button type="button" className="btn btn-primary btn-block" onClick={() => window.location.assign(`${API}/auth/chatgpt/start`)}><Icon name="external"/>Продолжить с ChatGPT</button>
          : <Notice tone="warning">OAuth не настроен на сервере. Добавьте OAuth client ID или переключите AUTH_MODE на local.</Notice>}
        <p className="login-footnote">Вход в сайт и авторизация в Codex CLI на компьютере — разные механизмы.</p>
      </> : <form onSubmit={submit}>
        <label className="field"><span className="field-label">Имя пользователя</span><input className="input" name="username" value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" autoFocus required/></label>
        <div className="field" style={{ marginTop: 13 }}><label className="field-label" htmlFor="login-password">Пароль</label><span className="password-field"><input id="login-password" className="input" name="password" type={showPassword ? 'text' : 'password'} value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" required/><button type="button" className="password-toggle" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'} aria-pressed={showPassword}>{showPassword ? 'Скрыть' : 'Показать'}</button></span></div>
        <button type="submit" className="btn btn-primary btn-block" style={{ marginTop: 16 }} disabled={submitting || !username.trim() || !password}>{submitting ? 'Входим…' : 'Войти'}</button>
        <p className="login-footnote">Учётные данные задаются в конфигурации сервера.</p>
      </form>}
    </section>
  </main>;
}
