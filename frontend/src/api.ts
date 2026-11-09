import type {
  AccountData,
  ComparisonDetail,
  DashboardData,
  DocumentRecord,
  User,
  WorkspaceData,
  WorkspaceRequestRecord,
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

async function request<T>(path: string, init: RequestInit = {}, options: { skipCsrf?: boolean } = {}): Promise<T> {
  const method = (init.method || 'GET').toUpperCase();
  const headers = new Headers(init.headers || {});
  headers.set('Accept', 'application/json');

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    if (!options.skipCsrf) {
      headers.set('X-CSRFToken', await getCsrfToken());
    }
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


export async function getAccount(signal?: AbortSignal): Promise<AccountData> {
  return request('/api/account', { signal });
}

export async function updateAccountProfile(payload: {
  first_name: string;
  last_name: string;
  other_names: string;
}): Promise<User> {
  const data = await request<{ user: User }>('/api/account/profile', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return data.user;
}

export async function changeAccountPassword(payload: {
  current_password: string;
  new_password: string;
  confirm_password: string;
}): Promise<void> {
  await request('/api/account/password', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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


export async function getBootstrapStatus(signal?: AbortSignal): Promise<boolean> {
  const data = await request<{ available: boolean }>('/api/bootstrap/status', { signal });
  return data.available;
}

export async function createFirstAdmin(payload: {
  first_name: string;
  last_name: string;
  other_names: string;
  email: string;
  password: string;
  setup_token: string;
}): Promise<User> {
  const data = await request<{ user: User }>('/api/bootstrap/first-admin', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return data.user;
}


export async function getWorkspaces(signal?: AbortSignal): Promise<WorkspaceData> {
  return request('/api/workspaces', { signal });
}

export async function switchWorkspace(workspace_id: number): Promise<void> {
  await request('/api/workspaces/current', { method: 'POST', body: JSON.stringify({ workspace_id }) });
}

export async function requestOrganizationWorkspace(payload: { organization_name: string; organization_type: string; website: string; reason: string }): Promise<void> {
  await request('/api/workspaces/requests', { method: 'POST', body: JSON.stringify(payload) });
}

export async function addWorkspaceMember(workspaceId: number, payload: { email: string; role: string }): Promise<void> {
  await request(`/api/workspaces/${workspaceId}/members`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function getWorkspaceRequests(signal?: AbortSignal): Promise<WorkspaceRequestRecord[]> {
  const data = await request<{ requests: WorkspaceRequestRecord[] }>('/api/admin/workspace-requests', { signal });
  return data.requests;
}

export async function decideWorkspaceRequest(requestId: number, decision: 'approve' | 'reject'): Promise<void> {
  await request(`/api/admin/workspace-requests/${requestId}/decision`, { method: 'POST', body: JSON.stringify({ decision }) });
}


export async function uploadWorkspaceReference(formData: FormData, signal?: AbortSignal): Promise<void> {
  await request('/api/workspace/references', { method: 'POST', body: formData, signal });
}


export async function registerAccount(payload: {
  first_name: string;
  last_name: string;
  other_names: string;
  email: string;
  password: string;
  confirm_password: string;
}): Promise<{ message: string; email: string }> {
  return request('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) });
}

export async function verifyEmail(token: string): Promise<User> {
  const data = await request<{ user: User }>('/api/auth/verify-email', {
    method: 'POST', body: JSON.stringify({ token }),
  }, { skipCsrf: true });
  return data.user;
}

export async function resendVerification(email: string): Promise<{ message: string }> {
  return request('/api/auth/resend-verification', { method: 'POST', body: JSON.stringify({ email }) });
}

export async function requestPasswordReset(email: string): Promise<{ message: string }> {
  return request('/api/auth/password-reset/request', { method: 'POST', body: JSON.stringify({ email }) });
}

export async function resetPassword(payload: {
  token: string;
  new_password: string;
  confirm_password: string;
}): Promise<{ message: string }> {
  return request('/api/auth/password-reset/confirm', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, { skipCsrf: true });
}
