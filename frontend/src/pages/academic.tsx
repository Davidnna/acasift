import { Navigate } from 'react-router-dom';

/**
 * Compatibility redirect for deployments that still contain the retired
 * academic page. Academic workflows have been replaced by Submission Requests.
 */
export function AcademicPage() {
    return <Navigate to="/app/submission-requests" replace />;
}
