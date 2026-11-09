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
  requestOrganizationWorkspace,
  addWorkspaceMember,
  getWorkspaceRequests,
  decideWorkspaceRequest,
  createFirstAdmin,
  getAccount,
  updateAccountProfile,
  changeAccountPassword,
  getBootstrapStatus,
  getComparison,
  getCurrentUser,
  getDashboard,
  getDocuments,
  getReferences,
  getUsers,
  signIn,
  signOut,
  uploadReference,
  uploadSubmission,
  uploadWorkspaceReference,
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
    if (intent === 'request') {
      await requestOrganizationWorkspace({
        organization_name: String(formData.get('organization_name') || ''),
        organization_type: String(formData.get('organization_type') || 'other'),
        website: String(formData.get('website') || ''),
        reason: String(formData.get('reason') || ''),
      });
      return { success: 'Your organisational workspace request has been submitted.' };
    }
    if (intent === 'add-member') {
      const data = await getWorkspaces();
      await addWorkspaceMember(data.active_workspace_id, {
        email: String(formData.get('email') || ''),
        role: String(formData.get('role') || 'member'),
      });
      return { success: 'Workspace member added.' };
    }
    return { error: 'Unknown workspace action.' };
  } catch (error) {
    return { error: error instanceof Error ? error.message : 'Workspace action failed.' };
  }
}

async function workspaceRequestDecisionAction({ request }: ActionFunctionArgs) {
  const formData = await request.formData();
  try {
    await decideWorkspaceRequest(
      Number(formData.get('request_id')),
      String(formData.get('decision')) as 'approve' | 'reject',
    );
    return { success: 'Workspace request reviewed.' };
  } catch (error) {
    return { error: error instanceof Error ? error.message : 'The workspace request could not be reviewed.' };
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

async function uploadWorkspaceReferenceAction({ request }: ActionFunctionArgs) {
  const formData = await request.formData();
  try {
    await uploadWorkspaceReference(formData, request.signal);
    throw redirect('/app/documents');
  } catch (error) {
    if (error instanceof Response) throw error;
    return { error: error instanceof Error ? error.message : 'The workspace reference could not be saved.' };
  }
}

async function uploadReferenceAction({ request }: ActionFunctionArgs) {
  const formData = await request.formData();
  try {
    await uploadReference(formData, request.signal);
    throw redirect('/app/admin/references');
  } catch (error) {
    if (error instanceof Response) throw error;
    return { error: error instanceof Error ? error.message : 'The reference document could not be saved.' };
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
        ],
      },
      { path: 'setup/first-admin', loader: firstAdminLoader, action: firstAdminAction, lazy: async () => ({ Component: (await import('./pages/setup')).FirstAdminSetupPage }) },
      { path: 'logout', action: logoutAction, element: null },
      {
        id: 'app',
        path: 'app',
        loader: requireUser,
        element: <AppLayout />,
        children: [
          { index: true, loader: () => redirect('/app/dashboard') },
          { path: 'account', loader: (args) => loadForUser(args, getAccount), action: accountAction, lazy: async () => ({ Component: (await import('./pages/account')).AccountPage }) },
          { path: 'workspaces', loader: (args) => loadForUser(args, getWorkspaces), action: workspacesAction, lazy: async () => ({ Component: (await import('./pages/workspaces')).WorkspacesPage }) },
          { path: 'dashboard', loader: (args) => loadForUser(args, getDashboard), lazy: async () => ({ Component: (await import('./pages/app')).DashboardPage }) },
          { path: 'documents', loader: (args) => loadForUser(args, getDocuments), lazy: async () => ({ Component: (await import('./pages/app')).DocumentsPage }) },
          { path: 'documents/new', action: uploadSubmissionAction, lazy: async () => ({ Component: (await import('./pages/app')).UploadSubmissionPage }) },
          { path: 'references/new', action: uploadWorkspaceReferenceAction, lazy: async () => ({ Component: (await import('./pages/workspace-reference')).WorkspaceReferenceUploadPage }) },
          { path: 'comparisons/:comparisonId', loader: (args) => loadForUser(args, (signal) => getComparison(args.params.comparisonId || '', signal)), lazy: async () => ({ Component: (await import('./pages/app')).ComparisonPage }) },
          {
            path: 'admin',
            loader: requireAdmin,
            element: <AdminLayout />,
            children: [
              { index: true, loader: () => redirect('/app/admin/users') },
              { path: 'users', loader: (args) => loadForAdmin(args, getUsers), action: createUserAction, lazy: async () => ({ Component: (await import('./pages/app')).AdminUsersPage }) },
              { path: 'workspace-requests', loader: (args) => loadForAdmin(args, getWorkspaceRequests), action: workspaceRequestDecisionAction, lazy: async () => ({ Component: (await import('./pages/workspace-requests')).WorkspaceRequestsPage }) },
              { path: 'references', loader: (args) => loadForAdmin(args, getReferences), lazy: async () => ({ Component: (await import('./pages/app')).AdminReferencesPage }) },
              { path: 'references/new', action: uploadReferenceAction, lazy: async () => ({ Component: (await import('./pages/app')).AdminUploadReferencePage }) },
            ],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
