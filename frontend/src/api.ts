import type {
    AccountData,
    ComparisonDetail,
    DashboardData,
    DocumentRecord,
    User,
    WorkspaceData,
    WorkspaceInviteRecord,
    WorkspaceInvitePreviewData,
    CourseListData,
    CourseRecord,
    CourseDetailData,
    AssignmentRecord,
    AssignmentDetailData,
    AcademicSubmissionRecord,
    AcademicSubmissionDetailData,
    AcademicAssessment,
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

async function request<T>(path: string, init: RequestInit = {}, options: { skipCsrf?: boolean; } = {}): Promise<T> {
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
        const data = await request<{ user: User; }>('/api/auth/me', { signal });
        return data.user;
    } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
    }
}

export async function signIn(email: string, password: string): Promise<User> {
    const data = await request<{ user: User; }>('/api/auth/login', {
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
    const data = await request<{ user: User; }>('/api/account/profile', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
    return data.user;
}

export async function uploadProfilePicture(image: File): Promise<User> {
    const formData = new FormData();
    formData.append('image', image);
    const data = await request<{ user: User; message: string; }>('/api/account/profile-picture', {
        method: 'POST',
        body: formData,
    });
    return data.user;
}

export async function removeProfilePicture(): Promise<void> {
    await request('/api/account/profile-picture', { method: 'DELETE' });
}

export async function requestEmailChange(payload: {
    new_email: string;
    current_password: string;
}): Promise<{ message: string; pending_email: string; }> {
    return request('/api/account/email-change', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export async function confirmEmailChange(token: string): Promise<{ message: string; email: string; }> {
    return request('/api/auth/confirm-email-change', {
        method: 'POST',
        body: JSON.stringify({ token }),
    }, { skipCsrf: true });
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
    const data = await request<{ documents: DocumentRecord[]; }>('/api/documents', { signal });
    return data.documents;
}

export async function uploadSubmission(formData: FormData, signal?: AbortSignal): Promise<{ comparison_id: number; }> {
    return request('/api/documents', { method: 'POST', body: formData, signal });
}

export async function getComparison(id: string, signal?: AbortSignal): Promise<ComparisonDetail> {
    const data = await request<{ comparison: ComparisonDetail; }>(`/api/comparisons/${id}`, { signal });
    return data.comparison;
}

export async function getUsers(signal?: AbortSignal): Promise<User[]> {
    const data = await request<{ users: User[]; }>('/api/admin/users', { signal });
    return data.users;
}

export async function createUser(payload: Record<string, string>): Promise<void> {
    await request('/api/admin/users', { method: 'POST', body: JSON.stringify(payload) });
}

export async function getReferences(signal?: AbortSignal): Promise<DocumentRecord[]> {
    const data = await request<{ documents: DocumentRecord[]; }>('/api/admin/references', { signal });
    return data.documents;
}

export async function uploadReference(formData: FormData, signal?: AbortSignal): Promise<void> {
    await request('/api/admin/references', { method: 'POST', body: formData, signal });
}


export async function getBootstrapStatus(signal?: AbortSignal): Promise<boolean> {
    const data = await request<{ available: boolean; }>('/api/bootstrap/status', { signal });
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
    const data = await request<{ user: User; }>('/api/bootstrap/first-admin', {
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

export async function createSharedWorkspace(payload: { name: string; description: string; }): Promise<{ workspace: WorkspaceData['workspaces'][number]; message: string; }> {
    return request('/api/workspaces', { method: 'POST', body: JSON.stringify(payload) });
}

export async function manageWorkspace(workspaceId: number, payload: { name: string; description: string; }): Promise<{ message: string; }> {
    return request(`/api/workspaces/${workspaceId}/manage`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function leaveWorkspace(workspaceId: number): Promise<{ message: string; workspace_id: number; }> {
    return request(`/api/workspaces/${workspaceId}/leave`, { method: 'POST', body: JSON.stringify({}) });
}

export async function deleteWorkspace(workspaceId: number): Promise<{ message: string; }> {
    return request(`/api/workspaces/${workspaceId}`, { method: 'DELETE' });
}

export async function createWorkspaceInvite(workspaceId: number, payload: { role: string; course_id: number | null; expires_at: string | null; max_uses: number | null; }): Promise<{ invite: WorkspaceInviteRecord; join_url: string; message: string; }> {
    return request(`/api/workspaces/${workspaceId}/invites`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function revokeWorkspaceInvite(workspaceId: number, inviteId: number): Promise<{ message: string; }> {
    return request(`/api/workspaces/${workspaceId}/invites/${inviteId}/revoke`, { method: 'POST', body: JSON.stringify({}) });
}

export async function getWorkspaceInvitePreview(token: string, signal?: AbortSignal): Promise<WorkspaceInvitePreviewData> {
    return request(`/api/workspaces/invites/preview?token=${encodeURIComponent(token)}`, { signal });
}

export async function acceptWorkspaceInvite(token: string): Promise<{ message: string; workspace_id: number; }> {
    return request('/api/workspaces/invites/accept', { method: 'POST', body: JSON.stringify({ token }) });
}

export async function updateWorkspaceMemberRole(workspaceId: number, userId: number, role: string): Promise<{ message: string; role: string; }> {
    return request(`/api/workspaces/${workspaceId}/members/${userId}/role`, { method: 'POST', body: JSON.stringify({ role }) });
}

export async function removeWorkspaceMember(workspaceId: number, userId: number): Promise<{ message: string; }> {
    return request(`/api/workspaces/${workspaceId}/members/${userId}/remove`, { method: 'POST', body: JSON.stringify({}) });
}

export async function addWorkspaceMember(workspaceId: number, payload: { email: string; role: string; }): Promise<void> {
    await request(`/api/workspaces/${workspaceId}/members`, { method: 'POST', body: JSON.stringify(payload) });
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
}): Promise<{ message: string; email: string; }> {
    return request('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) });
}

export async function verifyEmail(token: string): Promise<User> {
    const data = await request<{ user: User; }>('/api/auth/verify-email', {
        method: 'POST', body: JSON.stringify({ token }),
    }, { skipCsrf: true });
    return data.user;
}

export async function resendVerification(email: string): Promise<{ message: string; }> {
    return request('/api/auth/resend-verification', { method: 'POST', body: JSON.stringify({ email }) });
}

export async function requestPasswordReset(email: string): Promise<{ message: string; }> {
    return request('/api/auth/password-reset/request', { method: 'POST', body: JSON.stringify({ email }) });
}

export async function resetPassword(payload: {
    token: string;
    new_password: string;
    confirm_password: string;
}): Promise<{ message: string; }> {
    return request('/api/auth/password-reset/confirm', {
        method: 'POST',
        body: JSON.stringify(payload),
    }, { skipCsrf: true });
}

export async function getCourses(signal?: AbortSignal): Promise<CourseListData> {
    return request('/api/courses', { signal });
}

export async function createCourse(payload: { code: string; title: string; description: string; }): Promise<{ course: CourseRecord; join_code: string; }> {
    return request('/api/courses', { method: 'POST', body: JSON.stringify(payload) });
}

export async function joinCourse(join_code: string): Promise<{ message: string; course_id: number; }> {
    return request('/api/courses/join', { method: 'POST', body: JSON.stringify({ join_code }) });
}

export async function getCourse(courseId: string, signal?: AbortSignal): Promise<CourseDetailData> {
    return request(`/api/courses/${courseId}`, { signal });
}

export async function rotateCourseJoinCode(courseId: string): Promise<{ join_code: string; message: string; }> {
    return request(`/api/courses/${courseId}/join-code`, { method: 'POST', body: '{}' });
}

export async function addCourseMember(courseId: string, payload: { email: string; role: 'student' | 'lecturer'; }): Promise<{ message: string; }> {
    return request(`/api/courses/${courseId}/members`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function getAssignments(signal?: AbortSignal): Promise<{ assignments: AssignmentRecord[]; workspace: { name: string; type: string; }; }> {
    return request('/api/assignments', { signal });
}

export async function createAssignment(courseId: string, payload: {
    title: string;
    description: string;
    instructions: string;
    due_at: string | null;
    status: 'draft' | 'published';
    allow_late_submissions: boolean;
    allow_resubmissions: boolean;
}): Promise<{ assignment: AssignmentRecord; message: string; }> {
    return request(`/api/courses/${courseId}/assignments`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function getAssignment(assignmentId: string, signal?: AbortSignal): Promise<AssignmentDetailData> {
    return request(`/api/assignments/${assignmentId}`, { signal });
}

export async function submitAssignment(assignmentId: string, formData: FormData): Promise<{ submission: AcademicSubmissionRecord; message: string; }> {
    return request(`/api/assignments/${assignmentId}/submit`, { method: 'POST', body: formData });
}

export async function analyseAssignment(assignmentId: string): Promise<{ message: string; completed: number; total: number; }> {
    return request(`/api/assignments/${assignmentId}/analyse`, { method: 'POST', body: '{}' });
}

export async function getAcademicSubmission(submissionId: string, signal?: AbortSignal): Promise<AcademicSubmissionDetailData> {
    return request(`/api/submissions/${submissionId}`, { signal });
}

export async function saveAcademicAssessment(submissionId: string, payload: {
    decision: 'no_concern' | 'discuss_with_student' | 'further_review';
    feedback: string;
}): Promise<{ message: string; assessment: AcademicAssessment; }> {
    return request(`/api/submissions/${submissionId}/assessment`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function updateAssignmentStatus(assignmentId: string, status: 'draft' | 'published' | 'closed'): Promise<{ message: string; assignment: AssignmentRecord; }> {
    return request(`/api/assignments/${assignmentId}/status`, { method: 'POST', body: JSON.stringify({ status }) });
}
