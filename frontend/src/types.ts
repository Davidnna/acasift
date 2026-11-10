export interface User {
    id: number;
    full_name: string;
    first_name: string | null;
    last_name: string | null;
    other_names: string | null;
    email: string;
    role: 'admin' | 'user';
    is_admin: boolean;
    is_active?: boolean;
    email_verified?: boolean;
    profile_image_url?: string | null;
    created_at?: string;
}

export interface DocumentRecord {
    id: number;
    user_id: number;
    uploader?: string | null;
    title: string;
    original_filename: string;
    file_type: string;
    document_type: 'submission' | 'reference';
    workspace_id?: number | null;
    visibility_scope?: 'private' | 'workspace' | 'platform';
    processing_status: string;
    uploaded_at: string;
}

export interface ComparisonSummary {
    id: number;
    status: string;
    started_at: string;
    completed_at?: string | null;
    submitted_document: DocumentRecord;
}

export interface Passage {
    id: number;
    submitted_start: number;
    submitted_end: number;
    reference_start: number;
    reference_end: number;
    matched_text: string;
    reference_text: string;
}

export interface ComparisonResult {
    id: number;
    source_scope?: 'global' | 'workspace' | 'request' | 'personal';
    reference_document: DocumentRecord;
    cosine_similarity: number;
    matched_ngram_coverage: number;
    matched_ngram_count: number;
    total_query_ngrams: number;
    coverage_method?: string;
    passages: Passage[];
}

export interface ComparisonDetail extends ComparisonSummary {
    results: ComparisonResult[];
}

export interface DashboardData {
    stats: {
        document_count: number;
        comparison_count: number;
        reference_count: number;
    };
    recent_documents: DocumentRecord[];
    recent_comparisons: ComparisonSummary[];
    my_submission_requests?: {
        id: number;
        title: string;
        workspace_name: string | null;
        status: string;
        due_at: string | null;
        submission_count: number;
        last_submitted_at: string | null;
    }[];
}


export interface AccountData {
    user: User;
    pending_email: string | null;
    email_change_pending: boolean;
    activity: {
        document_count: number;
        comparison_count: number;
        recent_documents: DocumentRecord[];
        recent_comparisons: ComparisonSummary[];
    };
}


export interface AppShellData {
    user: User;
    activeWorkspace: WorkspaceRecord | null;
}

export interface WorkspaceRecord {
    id: number;
    name: string;
    description: string | null;
    type: 'personal' | 'shared';
    status: string;
    role: 'owner' | 'admin' | 'member' | null;
    is_owner: boolean;
    member_count: number;
    created_at: string;
}

export interface WorkspaceInviteRecord {
    id: number;
    role: 'member';
    status: 'active' | 'revoked' | 'expired' | 'used_up';
    expires_at: string | null;
    max_uses: number | null;
    use_count: number;
    created_at: string;
    created_by: string | null;
}

export interface WorkspaceData {
    active_workspace_id: number;
    workspaces: WorkspaceRecord[];
    pending_request: null;
    can_manage_members: boolean;
    is_workspace_owner: boolean;
    members: { id: number; full_name: string; email: string; role: string; }[];
    invites: WorkspaceInviteRecord[];
}

export interface WorkspaceInvitePreviewData {
    workspace: WorkspaceRecord;
    role: 'member';
    is_member: boolean;
    invited_by: string;
}


export interface SubmissionRequestRecord {
    id: number;
    workspace_id: number;
    workspace_name: string | null;
    title: string;
    description: string | null;
    instructions: string | null;
    opens_at: string | null;
    due_at: string | null;
    status: 'draft' | 'open' | 'closed' | 'archived';
    accepted_file_types: string[];
    max_file_size_mb: number;
    allow_late_submissions: boolean;
    allow_resubmissions: boolean;
    allow_external_participants: boolean;
    created_by: string | null;
    created_at: string;
    submission_count?: number;
    participant_count?: number;
    reviewers?: { id: number; full_name: string; email: string; }[];
    invites?: SubmissionRequestInviteRecord[];
}

export interface SubmissionRequestInviteRecord {
    id: number;
    status: 'active' | 'revoked' | 'expired' | 'used_up';
    expires_at: string | null;
    max_uses: number | null;
    use_count: number;
    created_at: string;
    created_by: string | null;
}

export interface SubmissionRequestListData {
    workspace: { id: number; name: string; };
    can_manage: boolean;
    submission_requests: SubmissionRequestRecord[];
    active_workspace: WorkspaceRecord;
}

export interface SubmissionRequestSubmission {
    id: number;
    document_id: number;
    title: string;
    filename: string;
    status: string;
    attempt_number: number;
    is_late: boolean;
    submitted_at: string;
    comparison_id: number | null;
    comparison_status: string;
    contributor?: { id: number; full_name: string; email: string; };
    review: {
        decision: 'no_action' | 'revision_requested' | 'further_review' | string;
        feedback: string | null;
        reviewer: string | null;
        reviewed_at: string | null;
    } | null;
}

export interface SubmissionRequestDetailData {
    submission_request: SubmissionRequestRecord;
    submissions: SubmissionRequestSubmission[];
    workspace_members: { id: number; full_name: string; email: string; }[];
    permissions: {
        can_manage: boolean;
        can_review: boolean;
        can_submit: boolean;
        can_join: boolean;
        is_participant: boolean;
        is_external_participant: boolean;
    };
}

export interface SubmissionRequestInvitePreviewData {
    submission_request: SubmissionRequestRecord;
    invited_by: string;
    already_joined: boolean;
}
