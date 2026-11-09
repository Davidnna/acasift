# AcaSift 0.3.0 — React frontend deployment

## What changes in this release

AcaSift's interface is now a React + TypeScript single-page application using React Router's
data-router APIs. Flask remains the backend API and PostgreSQL remains the database.

The Render deployment changes from the native Python runtime to the Docker runtime because the
production deployment must build the React bundle with Node and then serve it from Flask. The
Dockerfile performs this as a multi-stage build. The frontend and API are served from the same
origin, preserving session-cookie authentication and CSRF protection.

## Before deploying

1. Keep the existing Neon database and its `DATABASE_URL` unchanged.
2. Do not delete the existing Render service or database.
3. Ensure the GitHub repository root contains `Dockerfile`, `.dockerignore`, `render.yaml`,
   `frontend/`, `app/`, `requirements.txt` and `run.py`.
4. Ensure `.env` and all database credentials are excluded from Git.

## GitHub upload

Extract the supplied source archive and replace the existing repository files with the contents
of the `acasift` folder. Upload the folder contents at the repository root, not the containing
folder itself.

Suggested commit message:

`feat: migrate AcaSift frontend to React and React Router`

## Render Blueprint update

The updated `render.yaml` uses `runtime: docker` and points to `./Dockerfile`.

1. Open the existing AcaSift service in Render.
2. Review the Blueprint change before applying it. It should keep the service name `acasift`,
   branch `main`, health check `/health` and the existing environment variables.
3. Confirm the runtime/build configuration is Docker and the Dockerfile path is `./Dockerfile`.
4. Preserve the existing `DATABASE_URL` and `SECRET_KEY`. Do not generate a new database or
   replace the Neon connection string.
5. Trigger the deploy and inspect the Docker build logs.

If Render proposes creating a second service, deleting the current service, changing its name,
or replacing environment variables, stop before confirming and review the proposed change.
The current live service URL is `https://acasift.onrender.com/`; preserving it is important.

## Expected deployment process

1. Node 20 installs the React frontend dependencies.
2. Vite and TypeScript build the React application.
3. Python 3.11 installs the Flask application dependencies.
4. The built React bundle is copied into `app/static/spa/`.
5. Flask initialises any missing database tables and Gunicorn starts the application.

The first Docker build may take longer than the previous Python-only deployment because it builds
both frontend and backend layers. Docker layer caching may reduce later build times, but this is
not guaranteed.

## Post-deployment checks

Public routes:
- `/`
- `/about`
- `/features`
- `/how-it-works`
- `/faq`
- `/access`
- `/login`

Application routes (sign-in required):
- `/app/dashboard`
- `/app/documents`
- `/app/documents/new`
- `/app/admin/users` (administrator only)
- `/app/admin/references` (administrator only)

API checks:
- `GET /health` returns `{"status":"ok"}`.
- `GET /api/csrf` returns a CSRF token.
- `GET /api/auth/me` returns the signed-in user or HTTP 401.
- `GET /api/dashboard` returns HTTP 401 when signed out.

After sign-in, test document uploads, reference management, user creation and comparison reports.
Verify that a normal user cannot open administrator endpoints or another user's comparison.

## Local frontend development

Run Flask on port 5000, then run these commands in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite development server proxies `/api` requests to Flask.

## Automatic redeployment

The Blueprint retains `autoDeployTrigger: commit` on branch `main`. Future commits to `main`
trigger a Render build and deployment. The React bundle is rebuilt from `frontend/` during each
Docker build; do not manually edit generated files under `app/static/spa/`.

## Important storage limitation

The database remains external in Neon. Original uploaded files are still stored on the Render
application filesystem, which is ephemeral on the free plan. Do not treat originals as permanent
until private object storage or another persistent file-storage service is implemented.


## Browser-only first administrator setup (0.4.1)

1. Push the 0.4.1 source update to `main` and wait for Render to deploy successfully.
2. In Render > `acasift` > Environment, add `ADMIN_BOOTSTRAP_TOKEN`.
3. Generate a random value of at least 48 characters with a password manager. Do not reuse an account password.
4. Save the environment change and wait for Render to redeploy.
5. Visit `https://acasift.onrender.com/setup/first-admin`.
6. Enter the name, email, a unique password (at least 10 characters), and the token.
7. After successful creation and sign-in, remove `ADMIN_BOOTSTRAP_TOKEN` from Render Environment.
8. Save and wait for the final redeployment. Confirm `/setup/first-admin` now reports that setup is unavailable and sign-in works.

Do not place the token in a GitHub file, URL, screenshot, support ticket, or chat message.


## AcaSift 0.4.2 database migration

No manual SQL is required. On deployment, the existing `init-db` startup command adds
`first_name`, `last_name` and `other_names` as nullable columns when absent. It preserves
all existing `full_name` values. On PostgreSQL, it also widens `users.full_name` to VARCHAR(255)
when the current column is narrower. Existing accounts should sign in and complete their
structured name fields under **My account**.


## AcaSift 0.5.0 workspace migration

The existing Docker startup command runs `flask --app run.py init-db` before Gunicorn. The command creates the new workspace tables and adds the workspace columns to existing documents and comparisons. It then creates one personal workspace for each existing user, assigns their old submissions and comparisons to that workspace, and labels existing reference documents as platform-curated. No manual SQL is required.

After deployment, sign in with the existing account and open `/app/workspaces`. Confirm that the personal workspace appears. Submit a test document and verify it is associated with the active workspace. Use the platform-admin navigation to review `/app/admin/workspace-requests`.

Organisational workspace approval is a manual platform-admin review. Confirm the requester's identity and authority to represent the organisation before approving. Workspace membership can currently be granted to existing active AcaSift accounts by email.


## AcaSift 0.5.1 — Nylas Transactional Send

Public registration and password recovery use Nylas Transactional Send (currently beta),
not SMTP. The service sends application-generated email through a verified Nylas domain
using the Nylas API key. It does not require Gmail/Outlook grants or individual user OAuth.

Configure these Render Environment variables:

- `NYLAS_API_KEY` — secret API key generated in the Nylas application.
- `NYLAS_API_URI=https://api.us.nylas.com` — US data-residency endpoint.
- `NYLAS_SENDING_DOMAIN=acasift.nylas.email` — verified free Nylas sending domain.
- `NYLAS_FROM_NAME=AcaSift`.
- `NYLAS_FROM_EMAIL_VERIFICATION=verify@acasift.nylas.email`.
- `NYLAS_FROM_EMAIL_PASSWORD_RESET=security@acasift.nylas.email`.
- `NYLAS_FROM_EMAIL_NOTIFICATION=notifications@acasift.nylas.email`.
- `NYLAS_API_TIMEOUT=20`.
- `PUBLIC_APP_URL=https://acasift.onrender.com`.
- `EMAIL_VERIFICATION_HOURS=24`.
- `PASSWORD_RESET_HOURS=1`.

The sender address is selected by message purpose. Verification emails use the `verify@`
sender; password-reset messages use `security@`. All sender addresses must belong to the
verified `acasift.nylas.email` domain. These are sending identities, not inboxes.

`NYLAS_REPLY_TO` is optional. If configured, use a real mailbox that is monitored for replies.
Do not use an unprovisioned `support@acasift.nylas.email` alias as a reply destination. If no
mailbox is configured, verification and reset emails are sent without a reply-to address.

### Nylas dashboard check

1. Open the Nylas Dashboard and select the application associated with `acasift.nylas.email`.
2. Confirm that `acasift.nylas.email` appears under the application's/organisation's Domains
   and has a verified or active sending status.
3. Confirm that the API key belongs to this same Nylas application and US region.
4. Do not share the API key in GitHub, screenshots or chat.

Nylas' free `*.nylas.email` domain is intended for testing and does not require custom DNS
records. Transactional Send is currently documented as a beta feature. For a public production
launch, plan to verify a domain that AcaSift controls and configure its DNS records with Nylas.

### Deployment and test sequence

1. Push the updated source to `main` and wait for Render to deploy.
2. Add `NYLAS_API_KEY` as a secret in Render Environment. Set the other `NYLAS_*` values
   exactly as listed above.
3. Save and wait for the environment-triggered redeploy.
4. Open `/register` and create a test account using an email address you control.
5. Confirm that the message arrives from
   `AcaSift Account Verification <verify@acasift.nylas.email>`.
6. Complete email verification and confirm the account activates.
7. Use `/forgot-password` and confirm the reset email arrives from
   `AcaSift Security <security@acasift.nylas.email>`.
8. Complete the password reset and verify that the old password and prior sessions no longer work.
9. If sending fails, inspect Render logs for the Nylas HTTP status and request ID, then check the
   Nylas domain status and API key.

The database migration remains additive. Existing accounts, workspaces, documents and reports are
preserved. No manual Neon SQL is required.

### Public authentication routes

- `/register` — create an individual account.
- `/verify-email` — confirm email ownership.
- `/resend-verification` — request another verification email.
- `/forgot-password` — request a password reset.
- `/reset-password` — set a new password using a one-time token.

All ordinary registrations receive the `user` platform role. Users cannot select or self-assign
platform administrator privileges. Lecturer/student permissions continue to be assigned within
approved organisational workspaces.


## AcaSift 0.5.2 — Email verification hotfix and branded email

This patch corrects the email-link confirmation flow. A verification or password-reset link
can be opened in a fresh browser session, so the corresponding one-time-token POST endpoints
do not require a prior Flask browser-session CSRF token. They remain POST-only, rate-limited,
expiry-checked and single-use. Other state-changing API endpoints continue to require CSRF.

The verification and password-reset emails now use branded responsive HTML, AcaSift's navy
and teal colours, the tagline "Find the overlap. Follow the source.", clear action buttons,
fallback links and security notices.

The logo is hosted by the application at:

`https://acasift.onrender.com/static/img/acasift-mark.png`

No new Render environment variables are required. Preserve the existing Nylas settings and
ensure `PUBLIC_APP_URL=https://acasift.onrender.com`. After deployment, open the logo URL in
a browser and confirm that it displays the AcaSift mark.

### Post-deployment checks

1. Register a fresh test account and receive the verification email.
2. Open the email link in a private/incognito browser window or a different browser.
3. Select "Verify my email address"; it should activate the account and sign the user in.
4. Confirm that the verification link cannot be reused.
5. Request a password reset and open the reset link in a fresh browser context.
6. Confirm the password reset succeeds without a CSRF/session-token error.
7. Inspect the email in desktop and mobile clients; confirm the logo loads. Some email clients
   block remote images until the recipient chooses to display them.


## AcaSift 0.6.0 — Academic collaboration and assessment

This release adds the academic workflow to the existing application. The existing Docker startup
command runs `flask --app run.py init-db` before Gunicorn. The command uses SQLAlchemy
`create_all()` to create the new academic tables. No manual Neon SQL script or additional Render
environment variable is required. Existing accounts, workspaces, documents, comparison history
and Nylas configuration are preserved.

### After deployment

1. Sign in with an account that belongs to an approved organisational workspace.
2. Ensure the account's workspace role is `owner`, `admin`, or `lecturer` before creating a course.
3. Open **Courses**, create a course and share its 16-character enrolment code with students.
4. Ensure students have first been added to the same organisational workspace with the `student` role.
5. Students open **Courses**, enter the enrolment code and join.
6. The lecturer creates and publishes an assignment, configures its deadline and submission rules.
7. Students submit PDF, DOCX or TXT files from the assignment page.
8. The lecturer uses **Run cohort analysis** to compare all current submissions against one another.
9. The lecturer opens each submission report, reviews matched passages and records an assessment.
10. Confirm that students can see only their own submissions and aggregate similarity overview, not peer identities or matched text.

### Important analysis behaviour

A new submission is initially compared against peer submissions already received for that assignment.
It does not automatically rewrite every earlier student's report. When the cohort has progressed, the
lecturer should run cohort-wide analysis to refresh each submission against the current set of peers.
The analysis is scoped to the same assignment and course; it does not compare against other courses
or the public internet. Similarity scores are indicators for human review, not misconduct findings.

### Role prerequisites

Course creation is available only in an organisational workspace to workspace owners, administrators
and lecturers. Students must have the `student` role in that same workspace before they can enrol
using a course code. A lecturer can add an existing workspace member to a course when that person's
workspace role matches the course role. Workspace membership is managed from the Workspaces page.
