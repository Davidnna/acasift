import {
    createBrowserRouter,
    redirect,
    type ActionFunctionArgs,
    type LoaderFunctionArgs,
} from 'react-router-dom';
import {
    createUser,
    registerAccount,
    verifyEmail,
    resendVerification,
    requestPasswordReset,
    resetPassword,
    getWorkspaces,
    switchWorkspace,
    createSharedWorkspace,
    manageWorkspace,
    leaveWorkspace,
    deleteWorkspace,
    createWorkspaceInvite,
    revokeWorkspaceInvite,
    getWorkspaceInvitePreview,
    acceptWorkspaceInvite,
    addWorkspaceMember,
    updateWorkspaceMemberRole,
    removeWorkspaceMember,
    createFirstAdmin,
    getAccount,
    updateAccountProfile,
    uploadProfilePicture,
    removeProfilePicture,
    requestEmailChange,
    confirmEmailChange,
    changeAccountPassword,
    getBootstrapStatus,
    getComparison,
    getCurrentUser,
    getDashboard,
    getDocuments,
    getReferences,
    getAcquisitionDashboard,
    runAcquisitionDiscovery,
    getUsers,
    signIn,
    signOut,
    uploadReference,
    verifyGlobalReferenceEntry,
    archiveGlobalReferenceEntry,
    uploadSubmission,
    getSubmissionRequests,
    createSubmissionRequest,
    getSubmissionRequest,
    updateSubmissionRequest,
    updateSubmissionRequestStatus,
    joinSubmissionRequest,
    uploadSubmissionRequest,
    createSubmissionRequestInvite,
    revokeSubmissionRequestInvite,
    assignSubmissionReviewer,
    removeSubmissionReviewer,
    saveSubmissionReview,
    getSubmissionRequestInvitePreview,
    acceptSubmissionRequestInvite,
} from './api';
import { AdminLayout, AppLayout, NotFoundPage, PublicLayout, RootLayout, RouteErrorBoundary } from './components/layouts';

async function publicLoader({ request }: LoaderFunctionArgs) {
    return getCurrentUser(request.signal);
}

async function requireUser({ request }: LoaderFunctionArgs) {
    const user = await getCurrentUser(request.signal);
    if (!user) {
        const url = new URL(request.url);
        const next = `${url.pathname}${url.search}`;
        throw redirect(`/login?next=${encodeURIComponent(next)}`);
    }
    return user;
}

async function appLoader(args: LoaderFunctionArgs) {
    const user = await requireUser(args);
    const workspaceData = await getWorkspaces(args.request.signal);
    const activeWorkspace = workspaceData.workspaces.find(
        workspace => workspace.id === workspaceData.active_workspace_id,
    ) || null;
    return { user, activeWorkspace };
}

async function submissionRequestsLoader(args: LoaderFunctionArgs) {
    await requireUser(args);
    const workspaceData = await getWorkspaces(args.request.signal);
    const activeWorkspace = workspaceData.workspaces.find(
        workspace => workspace.id === workspaceData.active_workspace_id,
    );
    if (!activeWorkspace || activeWorkspace.type !== 'shared') {
        throw redirect('/app/workspaces');
    }
    const requestData = await getSubmissionRequests(activeWorkspace.id, args.request.signal);
    return { ...requestData, active_workspace: activeWorkspace };
}

async function submissionRequestDetailLoader(args: LoaderFunctionArgs) {
    await requireUser(args);
    return getSubmissionRequest(args.params.requestId || '', args.request.signal);
}

async function requireAdmin(args: LoaderFunctionArgs) {
    const user = await requireUser(args);
    if (!user.is_admin) throw redirect('/app/dashboard');
    return user;
}


async function loadForUser<T>(args: LoaderFunctionArgs, load: (signal: AbortSignal) => Promise<T>) {
    await requireUser(args);
    return load(args.request.signal);
}

async function loadForAdmin<T>(args: LoaderFunctionArgs, load: (signal: AbortSignal) => Promise<T>) {
    await requireAdmin(args);
    return load(args.request.signal);
}


async function firstAdminLoader({ request }: LoaderFunctionArgs) {
    return { available: await getBootstrapStatus(request.signal) };
}

async function firstAdminAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    const payload = {
        first_name: String(formData.get('first_name') || ''),
        last_name: String(formData.get('last_name') || ''),
        other_names: String(formData.get('other_names') || ''),
        email: String(formData.get('email') || ''),
        password: String(formData.get('password') || ''),
        setup_token: String(formData.get('setup_token') || ''),
    };
    try {
        await createFirstAdmin(payload);
        throw redirect('/app/dashboard');
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'The administrator account could not be created.' };
    }
}


async function registerAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const result = await registerAccount({
            first_name: String(formData.get('first_name') || ''),
            last_name: String(formData.get('last_name') || ''),
            other_names: String(formData.get('other_names') || ''),
            email: String(formData.get('email') || ''),
            password: String(formData.get('password') || ''),
            confirm_password: String(formData.get('confirm_password') || ''),
        });
        return { success: result.message, email: result.email };
    } catch (error) {
        return { error: error instanceof Error ? error.message : 'Registration could not be completed.' };
    }
}

async function verifyEmailAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        await verifyEmail(String(formData.get('token') || ''));
        throw redirect('/app/dashboard');
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'Email verification failed.' };
    }
}

async function resendVerificationAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const result = await resendVerification(String(formData.get('email') || ''));
        return { success: result.message };
    } catch (error) {
        return { error: error instanceof Error ? error.message : 'The request could not be completed.' };
    }
}

async function passwordResetRequestAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const result = await requestPasswordReset(String(formData.get('email') || ''));
        return { success: result.message };
    } catch (error) {
        return { error: error instanceof Error ? error.message : 'The request could not be completed.' };
    }
}

async function passwordResetConfirmAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const result = await resetPassword({
            token: String(formData.get('token') || ''),
            new_password: String(formData.get('new_password') || ''),
            confirm_password: String(formData.get('confirm_password') || ''),
        });
        return { success: result.message };
    } catch (error) {
        return { error: error instanceof Error ? error.message : 'Your password could not be reset.' };
    }
}

async function workspaceInviteLoader({ request }: LoaderFunctionArgs) {
    const url = new URL(request.url);
    const token = url.searchParams.get('token') || '';
    if (!token) throw new Response('Invitation link is missing.', { status: 404 });
    const user = await getCurrentUser(request.signal);
    if (!user) {
        const next = `${url.pathname}${url.search}`;
        throw redirect(`/login?next=${encodeURIComponent(next)}`);
    }
    return getWorkspaceInvitePreview(token, request.signal);
}

async function workspaceInviteAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        await acceptWorkspaceInvite(String(formData.get('token') || ''));
        throw redirect('/app/workspaces');
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'The invitation could not be accepted.' };
    }
}

async function submissionRequestInviteLoader({ request }: LoaderFunctionArgs) {
    const url = new URL(request.url);
    const token = url.searchParams.get('token') || '';
    const next = `${url.pathname}${url.search}`;

    if (!token) throw new Response('Submission link is missing.', { status: 404 });

    const user = await getCurrentUser(request.signal);
    if (!user) {
        throw redirect(`/login?next=${encodeURIComponent(next)}`);
    }

    try {
        return await getSubmissionRequestInvitePreview(token, request.signal);
    } catch (error) {
        if (error instanceof Error && /verify your email/i.test(error.message)) {
            throw redirect(`/resend-verification?next=${encodeURIComponent(next)}`);
        }
        throw error;
    }
}

async function submissionRequestInviteAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const result = await acceptSubmissionRequestInvite(String(formData.get('token') || ''));
        throw redirect(`/app/submission-requests/${result.request_id}`);
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'The submission link could not be accepted.' };
    }
}

async function loginLoader({ request }: LoaderFunctionArgs) {
    const user = await getCurrentUser(request.signal);
    if (user) throw redirect('/app/dashboard');
    return null;
}

async function loginAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    const email = String(formData.get('email') || '');
    const password = String(formData.get('password') || '');
    try {
        await signIn(email, password);
        const url = new URL(request.url);
        const next = url.searchParams.get('next') || '/app/dashboard';
        throw redirect(next.startsWith('/') && !next.startsWith('//') ? next : '/app/dashboard');
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'Sign in failed.' };
    }
}

async function logoutAction() {
    await signOut();
    return redirect('/');
}

async function uploadSubmissionAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const result = await uploadSubmission(formData, request.signal);
        throw redirect(`/app/comparisons/${result.comparison_id}`);
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'The document could not be analysed.' };
    }
}

async function createUserAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    const payload = {
        first_name: String(formData.get('first_name') || ''),
        last_name: String(formData.get('last_name') || ''),
        other_names: String(formData.get('other_names') || ''),
        email: String(formData.get('email') || ''),
        password: String(formData.get('password') || ''),
        role: String(formData.get('role') || 'user'),
    };
    try {
        await createUser(payload);
        return { success: 'User account created successfully.' };
    } catch (error) {
        return { error: error instanceof Error ? error.message : 'The account could not be created.' };
    }
}


async function workspacesAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    const intent = String(formData.get('_intent') || '');
    try {
        if (intent === 'switch') {
            await switchWorkspace(Number(formData.get('workspace_id')));
            return { success: 'Active workspace changed.' };
        }
        if (intent === 'create') {
            const result = await createSharedWorkspace({
                name: String(formData.get('name') || ''),
                description: String(formData.get('description') || ''),
            });
            return { success: result.message };
        }
        if (intent === 'add-member') {
            const data = await getWorkspaces();
            await addWorkspaceMember(data.active_workspace_id, {
                email: String(formData.get('email') || ''),
                role: String(formData.get('role') || 'member'),
            });
            return { success: 'Workspace member added.' };
        }
        if (intent === 'manage') {
            const data = await getWorkspaces();
            const result = await manageWorkspace(data.active_workspace_id, {
                name: String(formData.get('name') || ''),
                description: String(formData.get('description') || ''),
            });
            return { success: result.message };
        }
        if (intent === 'leave') {
            const data = await getWorkspaces();
            const result = await leaveWorkspace(data.active_workspace_id);
            return { success: result.message };
        }
        if (intent === 'delete') {
            const data = await getWorkspaces();
            const result = await deleteWorkspace(data.active_workspace_id);
            return { success: result.message };
        }
        if (intent === 'create-invite') {
            const data = await getWorkspaces();
            const expiryValue = String(formData.get('expires_at') || '');
            const maxValue = String(formData.get('max_uses') || '');
            const result = await createWorkspaceInvite(data.active_workspace_id, {
                role: 'member',
                expires_at: expiryValue ? new Date(expiryValue).toISOString() : null,
                max_uses: maxValue ? Number(maxValue) : null,
            });
            return { success: result.message, inviteUrl: result.join_url, invite: result.invite };
        }
        if (intent === 'revoke-invite') {
            const data = await getWorkspaces();
            const result = await revokeWorkspaceInvite(data.active_workspace_id, Number(formData.get('invite_id')));
            return { success: result.message };
        }
        if (intent === 'update-role') {
            const data = await getWorkspaces();
            const result = await updateWorkspaceMemberRole(
                data.active_workspace_id,
                Number(formData.get('user_id')),
                String(formData.get('role') || 'member'),
            );
            return { success: result.message };
        }
        if (intent === 'remove-member') {
            const data = await getWorkspaces();
            const result = await removeWorkspaceMember(data.active_workspace_id, Number(formData.get('user_id')));
            return { success: result.message };
        }
        return { error: 'Unknown workspace action.' };
    } catch (error) {
        return { error: error instanceof Error ? error.message : 'Workspace action failed.' };
    }
}

async function accountAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    const intent = String(formData.get('_intent') || 'profile');
    try {
        if (intent === 'profile') {
            await updateAccountProfile({
                first_name: String(formData.get('first_name') || ''),
                last_name: String(formData.get('last_name') || ''),
                other_names: String(formData.get('other_names') || ''),
            });
            return { intent, success: 'Your personal information has been updated.' };
        }
        if (intent === 'profile-picture') {
            const image = formData.get('image');
            if (!(image instanceof File) || image.size === 0) {
                return { intent, error: 'Choose a profile picture before uploading.' };
            }
            await uploadProfilePicture(image);
            return { intent, success: 'Your profile picture has been updated.' };
        }
        if (intent === 'remove-picture') {
            await removeProfilePicture();
            return { intent, success: 'Your profile picture has been removed.' };
        }
        if (intent === 'email-change') {
            const result = await requestEmailChange({
                new_email: String(formData.get('new_email') || ''),
                current_password: String(formData.get('email_current_password') || ''),
            });
            return { intent, success: result.message, pendingEmail: result.pending_email };
        }
        if (intent === 'password') {
            await changeAccountPassword({
                current_password: String(formData.get('current_password') || ''),
                new_password: String(formData.get('new_password') || ''),
                confirm_password: String(formData.get('confirm_password') || ''),
            });
            return { intent, success: 'Your password has been changed.' };
        }
        return { intent, error: 'Unknown account action.' };
    } catch (error) {
        return { intent, error: error instanceof Error ? error.message : 'The account update could not be completed.' };
    }
}

async function confirmEmailChangeAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const result = await confirmEmailChange(String(formData.get('token') || ''));
        return { success: result.message, email: result.email };
    } catch (error) {
        return { error: error instanceof Error ? error.message : 'The email address could not be confirmed.' };
    }
}


async function submissionRequestsAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const workspaceData = await getWorkspaces();
        const opensValue = String(formData.get('opens_at') || '');
        const dueValue = String(formData.get('due_at') || '');
        const result = await createSubmissionRequest({
            workspace_id: workspaceData.active_workspace_id,
            title: String(formData.get('title') || ''),
            description: String(formData.get('description') || ''),
            instructions: String(formData.get('instructions') || ''),
            opens_at: opensValue ? new Date(opensValue).toISOString() : null,
            due_at: dueValue ? new Date(dueValue).toISOString() : null,
            accepted_file_types: formData.getAll('accepted_file_types').map(value => String(value)),
            max_file_size_mb: Number(formData.get('max_file_size_mb') || 15),
            allow_late_submissions: formData.get('allow_late_submissions') === 'on',
            allow_resubmissions: formData.get('allow_resubmissions') === 'on',
            allow_external_participants: formData.get('allow_external_participants') === 'on',
        });
        throw redirect(`/app/submission-requests/${result.submission_request.id}`);
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'The submission request could not be created.' };
    }
}

async function submissionRequestAction({ request, params }: ActionFunctionArgs) {
    const formData = await request.formData();
    const requestId = params.requestId || '';
    const intent = String(formData.get('_intent') || '');
    try {
        if (intent === 'edit') {
            const opensValue = String(formData.get('opens_at') || '');
            const dueValue = String(formData.get('due_at') || '');
            const result = await updateSubmissionRequest(requestId, {
                title: String(formData.get('title') || ''),
                description: String(formData.get('description') || ''),
                instructions: String(formData.get('instructions') || ''),
                opens_at: opensValue ? new Date(opensValue).toISOString() : null,
                due_at: dueValue ? new Date(dueValue).toISOString() : null,
            });
            return { success: result.message };
        }
        if (intent === 'status') {
            const result = await updateSubmissionRequestStatus(
                requestId,
                String(formData.get('status') || 'draft') as 'draft' | 'open' | 'closed' | 'archived',
            );
            return { success: result.message };
        }
        if (intent === 'join') {
            const result = await joinSubmissionRequest(requestId);
            return { success: result.message };
        }
        if (intent === 'submit') {
            const result = await uploadSubmissionRequest(requestId, formData);
            if (result.submission.comparison_id) {
                throw redirect(`/app/comparisons/${result.submission.comparison_id}`);
            }
            return { success: result.message };
        }
        if (intent === 'create-invite') {
            const expiryValue = String(formData.get('expires_at') || '');
            const maxValue = String(formData.get('max_uses') || '');
            const result = await createSubmissionRequestInvite(requestId, {
                expires_at: expiryValue ? new Date(expiryValue).toISOString() : null,
                max_uses: maxValue ? Number(maxValue) : null,
            });
            return { success: result.message, inviteUrl: result.join_url };
        }
        if (intent === 'revoke-invite') {
            const result = await revokeSubmissionRequestInvite(requestId, Number(formData.get('invite_id')));
            return { success: result.message };
        }
        if (intent === 'assign-reviewer') {
            const result = await assignSubmissionReviewer(requestId, Number(formData.get('user_id')));
            return { success: result.message };
        }
        if (intent === 'remove-reviewer') {
            const result = await removeSubmissionReviewer(requestId, Number(formData.get('user_id')));
            return { success: result.message };
        }
        if (intent === 'review') {
            const result = await saveSubmissionReview(requestId, Number(formData.get('submission_id')), {
                decision: String(formData.get('decision') || 'further_review') as 'no_action' | 'revision_requested' | 'further_review',
                feedback: String(formData.get('feedback') || ''),
            });
            return { success: result.message };
        }
        return { error: 'Unknown submission request action.' };
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'The submission request could not be updated.' };
    }
}

async function adminReferencesAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    const intent = String(formData.get('_intent') || 'upload');
    try {
        if (intent === 'upload') {
            await uploadReference(formData, request.signal);
            return { success: 'The document was added to the AcaSift Reference Bank.' };
        }
        const entryId = Number(formData.get('entry_id'));
        if (!Number.isInteger(entryId) || entryId < 1) return { error: 'The reference record is invalid.' };
        if (intent === 'archive') {
            await archiveGlobalReferenceEntry(entryId);
            return { success: 'The document was removed from future private checks.' };
        }
        if (intent === 'verify') {
            await verifyGlobalReferenceEntry(entryId, formData);
            return { success: 'Global reference permission was recorded.' };
        }
        return { error: 'Unknown global reference action.' };
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'The AcaSift Reference Bank could not be updated.' };
    }
}

async function adminAcquisitionAction({ request }: ActionFunctionArgs) {
    const formData = await request.formData();
    try {
        const result = await runAcquisitionDiscovery({
            provider: String(formData.get('provider') || ''),
            query: String(formData.get('query') || ''),
            limit: Number(formData.get('limit') || 10),
        });
        if (result.job.status === 'failed') {
            return { error: result.job.error_message || 'The scholarly source could not complete this search.' };
        }
        return { success: result.message, job: result.job };
    } catch (error) {
        if (error instanceof Response) throw error;
        return { error: error instanceof Error ? error.message : 'The source search could not be completed.' };
    }
}

export const router = createBrowserRouter([
    {
        path: '/',
        element: <RootLayout />,
        errorElement: <RouteErrorBoundary />,
        children: [
            {
                element: <PublicLayout />,
                loader: publicLoader,
                children: [
                    { index: true, lazy: async () => ({ Component: (await import('./pages/public')).HomePage }) },
                    { path: 'about', lazy: async () => ({ Component: (await import('./pages/public')).AboutPage }) },
                    { path: 'features', lazy: async () => ({ Component: (await import('./pages/public')).FeaturesPage }) },
                    { path: 'how-it-works', lazy: async () => ({ Component: (await import('./pages/public')).HowItWorksPage }) },
                    { path: 'faq', lazy: async () => ({ Component: (await import('./pages/public')).FaqPage }) },
                    { path: 'access', lazy: async () => ({ Component: (await import('./pages/public')).AccessPage }) },
                    { path: 'login', loader: loginLoader, action: loginAction, lazy: async () => ({ Component: (await import('./pages/login')).LoginPage }) },
                    { path: 'register', loader: loginLoader, action: registerAction, lazy: async () => ({ Component: (await import('./pages/auth')).RegisterPage }) },
                    { path: 'verify-email', action: verifyEmailAction, lazy: async () => ({ Component: (await import('./pages/auth')).VerifyEmailPage }) },
                    { path: 'resend-verification', action: resendVerificationAction, lazy: async () => ({ Component: (await import('./pages/auth')).ResendVerificationPage }) },
                    { path: 'forgot-password', loader: loginLoader, action: passwordResetRequestAction, lazy: async () => ({ Component: (await import('./pages/auth')).ForgotPasswordPage }) },
                    { path: 'reset-password', action: passwordResetConfirmAction, lazy: async () => ({ Component: (await import('./pages/auth')).ResetPasswordPage }) },
                    { path: 'join-workspace', loader: workspaceInviteLoader, action: workspaceInviteAction, lazy: async () => ({ Component: (await import('./pages/workspace-invite')).WorkspaceInvitePage }) },
                    { path: 'join-submission-request', loader: submissionRequestInviteLoader, action: submissionRequestInviteAction, lazy: async () => ({ Component: (await import('./pages/submission-request-invite')).SubmissionRequestInvitePage }) },
                    { path: 'confirm-email-change', action: confirmEmailChangeAction, lazy: async () => ({ Component: (await import('./pages/email-change')).EmailChangeConfirmationPage }) },
                ],
            },
            { path: 'setup/first-admin', loader: firstAdminLoader, action: firstAdminAction, lazy: async () => ({ Component: (await import('./pages/setup')).FirstAdminSetupPage }) },
            { path: 'logout', action: logoutAction, element: null },
            {
                id: 'app',
                path: 'app',
                loader: appLoader,
                shouldRevalidate: () => true,
                element: <AppLayout />,
                children: [
                    { index: true, loader: () => redirect('/app/dashboard') },
                    { path: 'account', loader: (args) => loadForUser(args, getAccount), action: accountAction, lazy: async () => ({ Component: (await import('./pages/account')).AccountPage }) },
                    { path: 'workspaces', loader: (args) => loadForUser(args, getWorkspaces), action: workspacesAction, lazy: async () => ({ Component: (await import('./pages/workspaces')).WorkspacesPage }) },
                    { path: 'submission-requests', loader: submissionRequestsLoader, action: submissionRequestsAction, lazy: async () => ({ Component: (await import('./pages/submission-requests')).SubmissionRequestsPage }) },
                    { path: 'submission-requests/:requestId', loader: submissionRequestDetailLoader, action: submissionRequestAction, lazy: async () => ({ Component: (await import('./pages/submission-requests')).SubmissionRequestDetailPage }) },
                    { path: 'courses', loader: () => redirect('/app/submission-requests') },
                    { path: 'courses/:courseId', loader: () => redirect('/app/submission-requests') },
                    { path: 'assignments', loader: () => redirect('/app/submission-requests') },
                    { path: 'assignments/:assignmentId', loader: () => redirect('/app/submission-requests') },
                    { path: 'submissions/:submissionId', loader: () => redirect('/app/submission-requests') },
                    { path: 'dashboard', loader: (args) => loadForUser(args, getDashboard), lazy: async () => ({ Component: (await import('./pages/dashboard')).DashboardPage }) },
                    { path: 'documents', loader: (args) => loadForUser(args, getDocuments), action: uploadSubmissionAction, lazy: async () => ({ Component: (await import('./pages/documents')).DocumentsPage }) },
                    { path: 'documents/new', loader: () => redirect('/app/documents') },
                    { path: 'references', loader: () => redirect('/app/documents') },
                    { path: 'references/new', loader: () => redirect('/app/documents') },
                    { path: 'comparisons/:comparisonId', loader: (args) => loadForUser(args, (signal) => getComparison(args.params.comparisonId || '', signal)), lazy: async () => ({ Component: (await import('./pages/documents')).ComparisonPage }) },
                    {
                        path: 'admin',
                        loader: requireAdmin,
                        element: <AdminLayout />,
                        children: [
                            { index: true, loader: () => redirect('/app/admin/users') },
                            { path: 'users', loader: (args) => loadForAdmin(args, getUsers), action: createUserAction, lazy: async () => ({ Component: (await import('./pages/admin')).AdminUsersPage }) },
                            { path: 'references', loader: (args) => loadForAdmin(args, getReferences), action: adminReferencesAction, lazy: async () => ({ Component: (await import('./pages/admin')).AdminReferencesPage }) },
                            { path: 'acquisition', loader: (args) => loadForAdmin(args, getAcquisitionDashboard), action: adminAcquisitionAction, lazy: async () => ({ Component: (await import('./pages/admin')).AdminAcquisitionPage }) },
                            { path: 'references/new', loader: () => redirect('/app/admin/references') },
                        ],
                    },
                ],
            },
            { path: '*', element: <NotFoundPage /> },
        ],
    },
]);
