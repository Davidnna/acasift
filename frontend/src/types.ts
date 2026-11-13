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
    external_search_status?: 'pending' | 'running' | 'completed' | 'partial' | 'unavailable' | 'failed';
    external_search_error?: string | null;
    external_search_completed_at?: string | null;
    external_sources_discovered?: number;
    external_sources_compared?: number;
    external_sources_with_matches?: number;
    external_provider_summary?: Record<string, {
        queries_attempted: number;
        queries_succeeded: number;
        records_returned: number;
        errors: string[];
    }>;
}

export interface Passage {
    id: number;
    submitted_start: number;
    submitted_end: number;
    reference_start: number;
    reference_end: number;
    matched_text: string;
    reference_text: string;
    match_method?: string;
    match_score?: number;
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
    fuzzy_similarity: number;
    fuzzy_coverage: number;
    semantic_similarity: number | null;
    semantic_coverage: number | null;
    semantic_status: string;
    composite_similarity: number;
    passages: Passage[];
}

export interface ExternalComparisonPassage {
    id: number;
    submitted_start: number;
    submitted_end: number;
    matched_text: string;
    source_excerpt: string;
    match_method: string;
    match_score: number;
}

export interface ExternalComparisonResult {
    id: number;
    provider: string;
    providers: string[];
    title: string;
    authors: string[];
    year: number | null;
    journal: string | null;
    doi: string | null;
    source_url: string | null;
    full_text_url: string | null;
    license_name: string | null;
    license_url: string | null;
    cosine_similarity: number;
    exact_ngram_coverage: number;
    matched_ngram_count: number;
    total_query_ngrams: number;
    fuzzy_similarity: number;
    fuzzy_coverage: number;
    semantic_similarity: number | null;
    semantic_coverage: number | null;
    semantic_status: string;
    composite_similarity: number;
    passages: ExternalComparisonPassage[];
}

export interface ComparisonDetail extends ComparisonSummary {
    results: ComparisonResult[];
    external_results: ExternalComparisonResult[];
}

export interface DashboardData {
    stats: {
        submission_count: number;
        request_count: number;
    };
    recent_submissions: DocumentRecord[];
    my_submission_requests: {
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
        submission_count: number;
        recent_submissions: DocumentRecord[];
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
    type: 'shared';
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
    active_workspace_id: number | null;
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
    comparison_id?: number | null;
    comparison_status?: string;
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
