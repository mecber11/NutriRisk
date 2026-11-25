/** Cliente HTTP con JWT, refresh automático y sesión de auditoría. */

const API_BASE = '/api/v1';

const ACCESS_KEY = 'nr.access_token';
const REFRESH_KEY = 'nr.refresh_token';
const SESSION_KEY = 'nr.session_id';

type TokenPair = {
  access_token: string;
  refresh_token: string;
};

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function getSessionId(): string {
  let value = sessionStorage.getItem(SESSION_KEY);
  if (!value) {
    value = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, value);
  }
  return value;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(tokens: TokenPair | null): void {
  if (!tokens) {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    return;
  }
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
          setTokens(null);
          return false;
        }
        const data = (await response.json()) as TokenPair;
        setTokens(data);
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return '';
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}

async function rawRequest(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  const token = getAccessToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  headers.set('X-Session-Id', getSessionId());
  if (!(options.body instanceof FormData) && options.body) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

async function parseError(response: Response): Promise<ApiError> {
  let message = `Error ${response.status}`;
  let code: string | undefined;
  try {
    const payload = await response.json();
    if (payload?.error?.message) message = payload.error.message;
    code = payload?.error?.code;
    if (payload?.detail && typeof payload.detail === 'string') message = payload.detail;
  } catch {
    /* ignore */
  }
  return new ApiError(response.status, message, code);
}

async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  let response: Response;
  try {
    response = await rawRequest(path, options);
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor. Verifique que la API esté en ejecución.');
  }
  if (response.status === 401 && retry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return request<T>(path, options, false);
    window.dispatchEvent(new CustomEvent('nr:unauthorized'));
    throw new ApiError(401, 'Sesión expirada. Inicie sesión nuevamente.');
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, unknown>) => request<T>(`${path}${buildQuery(params)}`),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) => request<T>(path, { method: 'POST', body: formData }),
};

/** Descarga un archivo autenticado y dispara el guardado en el navegador. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await rawRequest(path, { method: 'GET' });
  if (!response.ok) throw await parseError(response);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function login(email: string, password: string) {
  return request<{
    access_token: string;
    refresh_token: string;
    expires_in: number;
    user: import('../types').User;
  }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
}
