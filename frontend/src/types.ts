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
}


export interface AccountData {
    user: User;
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
    role: 'owner' | 'admin' | 'lecturer' | 'student' | 'member' | null;
    is_owner: boolean;
    member_count: number;
    created_at: string;
}

export interface WorkspaceInviteRecord {
    id: number;
    role: 'member' | 'student' | 'lecturer';
    course_id: number | null;
    course_title: string | null;
    course_code: string | null;
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
    courses: { id: number; code: string; title: string; status: string; }[];
}

export interface WorkspaceInvitePreviewData {
    workspace: WorkspaceRecord;
    role: 'member' | 'student' | 'lecturer';
    course: { id: number; code: string; title: string; } | null;
    is_member: boolean;
    is_course_member: boolean;
    invited_by: string;
}


export interface CourseRecord {
    id: number;
    workspace_id: number;
    code: string;
    title: string;
    description: string | null;
    status: string;
    my_role: 'lecturer' | 'student' | null;
    is_instructor: boolean;
    member_count: number;
    assignment_count: number;
    created_at: string;
}

export interface CourseListData {
    workspace: { id: number; name: string; type: 'personal' | 'shared'; };
    courses: CourseRecord[];
    can_create: boolean;
    can_join: boolean;
}

export interface CourseMemberRecord {
    id: number;
    full_name: string;
    email: string;
    role: 'lecturer' | 'student';
    enrolled_at: string;
}

export interface AssignmentRecord {
    id: number;
    course_id: number;
    title: string;
    description: string | null;
    instructions: string | null;
    due_at: string | null;
    status: 'draft' | 'published' | 'closed';
    allow_late_submissions: boolean;
    allow_resubmissions: boolean;
    created_by: string | null;
    created_at: string;
    submission_count?: number;
    course_code?: string;
    course_title?: string;
    is_instructor?: boolean;
}

export interface CourseDetailData {
    course: CourseRecord;
    assignments: AssignmentRecord[];
    can_manage: boolean;
    members: CourseMemberRecord[];
}

export interface AcademicSubmissionRecord {
    id: number;
    assignment_id: number;
    document_id: number;
    title: string;
    filename: string;
    attempt_number: number;
    status: string;
    is_late: boolean;
    submitted_at: string;
    comparison_status: string;
    has_assessment: boolean;
    assessment_decision: string | null;
    student?: { id: number; full_name: string; email: string; };
}

export interface AssignmentDetailData {
    assignment: AssignmentRecord;
    course: CourseRecord;
    is_instructor: boolean;
    can_submit: boolean;
    is_past_due: boolean;
    submissions: AcademicSubmissionRecord[];
}

export interface AcademicAssessment {
    decision: 'no_concern' | 'discuss_with_student' | 'further_review';
    feedback: string | null;
    assessor: string | null;
    reviewed_at: string;
}

export interface AcademicComparisonResult {
    id: number;
    reference_document: { id: number; title: string; filename: string; student: string; };
    cosine_similarity: number;
    matched_ngram_coverage: number;
    matched_ngram_count: number;
    total_query_ngrams: number;
    passages: { id: number; matched_text: string; reference_text: string; submitted_start: number; submitted_end: number; }[];
}

export interface AcademicSubmissionDetailData {
    submission: AcademicSubmissionRecord;
    assignment: AssignmentRecord;
    course: CourseRecord;
    is_instructor: boolean;
    assessment: AcademicAssessment | null;
    comparison: null | {
        status: string;
        started_at: string | null;
        completed_at: string | null;
        peer_count: number;
        highest_cosine_similarity?: number;
        highest_ngram_coverage?: number;
        note?: string;
        results?: AcademicComparisonResult[];
    };
}
