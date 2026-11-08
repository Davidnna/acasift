import type {
  ComparisonDetail,
  DashboardData,
  DocumentRecord,
  User,
} from './types';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

let csrfToken: string | null = null;

async function getCsrfToken(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken;
  const response = await fetch('/api/csrf', { credentials: 'same-origin' });
  const data = await response.json();
  if (!response.ok) throw new ApiError(data.error || 'Could not initialise a secure session.', response.status);
  csrfToken = data.csrf_token;
  return csrfToken as string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || 'GET').toUpperCase();
  const headers = new Headers(init.headers || {});
  headers.set('Accept', 'application/json');

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers.set('X-CSRFToken', await getCsrfToken());
    if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
  }

  const response = await fetch(path, {
    ...init,
    method,
    headers,
    credentials: 'same-origin',
  });
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json() : null;

  if (!response.ok) {
    if (response.status === 400 && String(data?.error || '').toLowerCase().includes('session token')) {
      csrfToken = null;
    }
    throw new ApiError(data?.error || 'The request could not be completed.', response.status);
  }
  return data as T;
}

export async function getCurrentUser(signal?: AbortSignal): Promise<User | null> {
  try {
    const data = await request<{ user: User }>('/api/auth/me', { signal });
    return data.user;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function signIn(email: string, password: string): Promise<User> {
  const data = await request<{ user: User }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  return data.user;
}

export async function signOut(): Promise<void> {
  await request('/api/auth/logout', { method: 'POST', body: '{}' });
  csrfToken = null;
}

export async function getDashboard(signal?: AbortSignal): Promise<DashboardData> {
  return request('/api/dashboard', { signal });
}

export async function getDocuments(signal?: AbortSignal): Promise<DocumentRecord[]> {
  const data = await request<{ documents: DocumentRecord[] }>('/api/documents', { signal });
  return data.documents;
}

export async function uploadSubmission(formData: FormData, signal?: AbortSignal): Promise<{ comparison_id: number }> {
  return request('/api/documents', { method: 'POST', body: formData, signal });
}

export async function getComparison(id: string, signal?: AbortSignal): Promise<ComparisonDetail> {
  const data = await request<{ comparison: ComparisonDetail }>(`/api/comparisons/${id}`, { signal });
  return data.comparison;
}

export async function getUsers(signal?: AbortSignal): Promise<User[]> {
  const data = await request<{ users: User[] }>('/api/admin/users', { signal });
  return data.users;
}

export async function createUser(payload: Record<string, string>): Promise<void> {
  await request('/api/admin/users', { method: 'POST', body: JSON.stringify(payload) });
}

export async function getReferences(signal?: AbortSignal): Promise<DocumentRecord[]> {
  const data = await request<{ documents: DocumentRecord[] }>('/api/admin/references', { signal });
  return data.documents;
}

export async function uploadReference(formData: FormData, signal?: AbortSignal): Promise<void> {
  await request('/api/admin/references', { method: 'POST', body: formData, signal });
}
