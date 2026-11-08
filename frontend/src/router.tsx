import {
  createBrowserRouter,
  redirect,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
} from 'react-router-dom';
import {
  createUser,
  createFirstAdmin,
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
    full_name: String(formData.get('full_name') || ''),
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
    full_name: String(formData.get('full_name') || ''),
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
          { path: 'dashboard', loader: (args) => loadForUser(args, getDashboard), lazy: async () => ({ Component: (await import('./pages/app')).DashboardPage }) },
          { path: 'documents', loader: (args) => loadForUser(args, getDocuments), lazy: async () => ({ Component: (await import('./pages/app')).DocumentsPage }) },
          { path: 'documents/new', action: uploadSubmissionAction, lazy: async () => ({ Component: (await import('./pages/app')).UploadSubmissionPage }) },
          { path: 'comparisons/:comparisonId', loader: (args) => loadForUser(args, (signal) => getComparison(args.params.comparisonId || '', signal)), lazy: async () => ({ Component: (await import('./pages/app')).ComparisonPage }) },
          {
            path: 'admin',
            loader: requireAdmin,
            element: <AdminLayout />,
            children: [
              { index: true, loader: () => redirect('/app/admin/users') },
              { path: 'users', loader: (args) => loadForAdmin(args, getUsers), action: createUserAction, lazy: async () => ({ Component: (await import('./pages/app')).AdminUsersPage }) },
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
