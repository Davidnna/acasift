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


export interface WorkspaceRecord {
  id: number;
  name: string;
  type: 'personal' | 'organization';
  status: string;
  role: 'owner' | 'admin' | 'lecturer' | 'student' | 'member' | null;
  created_at: string;
}

export interface WorkspaceData {
  active_workspace_id: number;
  workspaces: WorkspaceRecord[];
  pending_request: { id: number; organization_name: string; status: string; created_at: string } | null;
  can_manage_members: boolean;
  members: { id: number; full_name: string; email: string; role: string }[];
}

export interface WorkspaceRequestRecord {
  id: number;
  requester: string;
  requester_email: string;
  organization_name: string;
  organization_type: string;
  website: string | null;
  reason: string;
  status: string;
  created_at: string;
  review_notes: string | null;
}
