export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export function token() {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('token') || '';
}

function errorMessage(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    const first = value[0] as { msg?: string } | undefined;
    return first?.msg || null;
  }
  if (value && typeof value === 'object' && 'detail' in value) {
    const detail = (value as { detail?: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return errorMessage(detail);
  }
  return null;
}

export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const hasFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  if (token()) headers.set('Authorization', `Bearer ${token()}`);
  if (options.body !== undefined && !hasFormData && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(`${API}${path}`, { ...options, headers, cache: 'no-store' });
  if (response.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem('token');
    if (location.pathname !== '/login') location.assign('/login');
  }
  if (response.status === 204) return null as T;

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try { body = JSON.parse(text); }
    catch { body = text; }
  }
  if (!response.ok) {
    const message = errorMessage(body) || (typeof body === 'string' ? body : 'Не удалось выполнить запрос');
    throw new ApiError(message, response.status);
  }
  return body as T;
}
