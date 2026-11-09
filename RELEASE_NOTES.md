# AcaSift 0.3.1 release notes

## React frontend migration

- Replaced the Flask/Jinja-rendered interface with React 18 and TypeScript.
- Added Vite for local development and production bundling.
- Adopted React Router 6 data routing with nested public and authenticated layouts.
- Added route loaders, actions, protected loaders, lazy page loading, `Form`, `useFetcher`,
  navigation state, request cancellation and a route error boundary.
- Added a same-origin Flask JSON API for authentication, dashboard data, documents,
  comparisons, account administration and reference repository management.
- Preserved Flask session authentication and added explicit CSRF token handling for API writes.
- Kept the existing SQLAlchemy models and Neon PostgreSQL database schema unchanged.
- Added a multi-stage Dockerfile to build React with Node and serve the compiled bundle through
  the existing Flask service.

## Operational notes

- Render's service runtime changes from native Python to Docker. The existing service name,
  branch, database URL and application URL should be retained.
- The first Docker deployment can take longer because it builds both the React frontend and
  Python backend image.
- The original uploaded-file storage limitation remains: files are stored on the ephemeral
  application filesystem and need persistent private object storage for durable retention.

## Verification status

- Python source syntax compilation: passed.
- React TS/TSX syntax transpilation: passed.
- React structural TypeScript check against local declarations: passed.
- Render Blueprint YAML parse: passed.
- Full npm/Vite production build: not run in this environment because the npm registry was
  unreachable. Render's Docker build will install the pinned frontend dependencies and run
  `npm run build` during deployment.
- Flask runtime tests: included in `tests/`, but not executed here because Flask dependencies
  are not installed in this environment.


## Navigation, scrolling and transitions

- Added route-aware scroll-to-top behaviour for public, login and authenticated pages.
- Added a floating scroll-to-top button that appears after 360px of scrolling.
- Added a restrained fade-and-rise page-entry transition on route changes.
- Added keyboard focus styling and accessible labelling for the scroll control.
- Respected `prefers-reduced-motion` for route transitions and scrolling.


# AcaSift 0.3.3 release notes

## Navigation and motion refinement

- Removed the System status link from the public footer. The `/health` endpoint remains active for Render health checks and is not part of visitor navigation.
- Enabled React Router View Transitions on client-side links, navigation links and route forms.
- Added coordinated outgoing and incoming page snapshots with a longer ease-out entrance.
- Replaced browser-dependent smooth scrolling with an interruptible requestAnimationFrame animation using cubic ease-in-out timing.
- Applied the same controlled scroll animation to route changes, hash targets and the floating scroll-to-top control.
- Increased the floating control's fade and movement timing for a less abrupt appearance and dismissal.
- Preserved reduced-motion accessibility behaviour.


## 0.3.3 — Build correction

- Removed the unsupported `viewTransition` prop from the React Router `fetcher.Form` used for sign-out.
- Kept View Transitions enabled on supported `Link`, `NavLink`, and route `Form` navigation elements.
- No backend or database changes.


# AcaSift 0.3.4 release notes

## Deliberate scrolling and slower transitions

- Reworked scroll-to-top timing: travel duration now scales with distance and is capped at 2.8 seconds.
- Changed the scroll easing curve to a sine ease-in-out for a gentler start and finish.
- Disabled browser history scroll restoration so it cannot override AcaSift's route scroll behaviour.
- Started route scroll handling after the destination route commits to the DOM.
- Used the document's root scrolling element for frame-by-frame positioning.
- Increased route View Transition timing to approximately 0.95 seconds.
- Increased the floating scroll control's entrance/exit timing and refined its hover response.
- Slowed common button, card, sidebar and link feedback transitions.
- Preserved manual interruption and `prefers-reduced-motion` support.
- No backend, authentication or database changes.


# AcaSift 0.4.0 release notes

## Detection engine and evaluation

- N-gram token matching now applies Unicode NFKC normalization and case-folding while preserving
  original character offsets for report excerpts.
- Passage merging now uses token-position alignment rather than raw character-offset differences.
- N-gram coverage now counts matched query windows over all query windows, including repeated
  occurrences. Single-token overlap is excluded; short documents use a minimum bigram.
- TF-IDF vectorization now applies Unicode accent normalization and includes one-character tokens.
- Comparison reports explain the difference between document-level TF-IDF similarity and exact
  N-gram overlap, and explicitly state that neither score proves plagiarism.
- Added a synthetic labelled evaluation corpus and a script reporting precision, recall, F1,
  accuracy, confusion matrix and passage-localisation rate.
- Added expanded automated tests for punctuation, case, Unicode, offsets, disjoint passages,
  short documents and repository ranking.
- Added an additive `coverage_method` column to comparison results. Startup migration labels existing rows as legacy so historical metrics are not reinterpreted.


# AcaSift 0.4.1 release notes

## Browser-based first administrator setup

- Added a token-protected one-time first-administrator API.
- Added `/setup/first-admin` React page, not exposed in public navigation.
- Requires a high-entropy `ADMIN_BOOTSTRAP_TOKEN` environment variable.
- Rechecks for an existing administrator inside a database transaction.
- Uses a PostgreSQL advisory transaction lock to prevent concurrent first-admin creation.
- Hashes the new administrator password using the existing Werkzeug password hashing.
- Reuses the application's CSRF-protected JSON request layer.
- Automatically signs in the newly created administrator.
- Setup becomes unavailable after the first administrator exists; remove the environment token after setup.
- No database schema changes.


# AcaSift 0.4.2 release notes

## Structured names and account management

- Added first name, last name and optional other names to user records.
- Added an additive startup migration for existing databases; legacy full_name values are preserved.
- Widened PostgreSQL full_name storage to support structured names.
- Updated first-administrator setup and administrator-created account forms to use structured names.
- Added an authenticated account page with personal information, read-only account identity/role/status, recent activity and password change.
- Added current-password verification and password confirmation checks.
- Added account navigation from the workspace sidebar and account identity control.
- No open self-registration in this release; account provisioning policy remains unchanged.


# AcaSift 0.5.0 — Global workspace foundation

- Establishes AcaSift as an institution-agnostic platform architecture.
- Adds private personal workspaces for every existing account.
- Adds organisational workspace requests, with activation only after platform-admin approval.
- Adds workspace membership roles: owner, admin, lecturer, student and member.
- Adds workspace switching and member addition for workspace owners/admins.
- Adds workspace-scoped document and comparison records.
- Migrates existing submissions and comparisons into each owner's personal workspace.
- Preserves existing administrator-curated reference documents as platform-wide reference sources.
- Restricts comparison history to its owner; platform administrator status does not bypass private report ownership.
- Does not yet implement public self-registration, email verification, course/assignment permissions or student-to-student comparison.

- Adds workspace-scoped reference uploads: personal references remain private to the uploader; organisational references are shared with active workspace members.


# AcaSift 0.5.1 — Open registration and account security

## Public account access
- Added public individual registration using personal or work email addresses.
- No institutional email, matriculation number, staff ID or organisation membership is required.
- Every new account starts with the ordinary `user` platform role. Privileged platform roles are not selectable at registration.
- A personal workspace is created with the pending account.

## Email verification and recovery
- Added one-time email verification links with configurable expiry.
- Added verification-email resend flow.
- Added password-reset request and one-time reset confirmation.
- Password reset invalidates existing login sessions through an authentication-version field.
- Reset-request and resend responses do not disclose whether an email address has an account.
- Email links require an explicit POST confirmation; a GET request alone does not consume the token.

## Authentication security
- Verification and reset tokens are stored as SHA-256 hashes, not plaintext.
- Added database-backed rate limits for login, registration, verification, resend and password reset.
- Added `Retry-After` headers for throttled requests.
- Added no-store and no-referrer response headers on sensitive authentication routes.
- Existing active accounts are marked verified during additive migration to preserve access.
- Existing sessions remain valid until their credentials change; password changes and resets revoke older sessions.

## Deployment requirements
- SMTP environment variables must be configured in Render before public registration can send email.
- The migration is additive and runs through the existing `init-db` startup command.
- No manual Neon SQL or external Redis service is required.


## 0.5.1 integration update — Nylas Transactional Send

- Replaced SMTP delivery with Nylas Transactional Send over HTTPS.
- Configured US API endpoint and `acasift.nylas.email` sending domain.
- Verification messages use `verify@acasift.nylas.email`.
- Password-reset messages use `security@acasift.nylas.email`.
- Added a separate notification sender identity for future system emails.
- Added optional monitored `NYLAS_REPLY_TO` support.
- Added request timeouts, idempotency keys, provider error logging and domain-bound sender validation.
- Added offline tests for endpoint, authentication header, payload, sender selection and reply-to behavior.
- No SMTP username, password, host or port is required.


# AcaSift 0.5.2 — Email verification and branded authentication messages

## Verification flow correction
- Exempted only the one-time email verification endpoint from browser-session CSRF validation.
- Exempted only the one-time password-reset confirmation endpoint from browser-session CSRF validation.
- Both endpoints remain POST-only, rate-limited, expiry-checked and single-use.
- The high-entropy email bearer token is the proof of mailbox control; the frontend no longer requests a pre-existing CSRF session for these two email-link actions.
- All other state-changing API routes continue to require CSRF protection.

## Branded email design
- Replaced the minimal verification and password-reset messages with responsive, table-based HTML templates.
- Added AcaSift's navy and teal visual identity, tagline, clear calls to action, fallback URLs, expiry information and security guidance.
- Added the AcaSift logo as a PNG asset for broad email-client compatibility.
- The logo is served from `/static/img/acasift-mark.png`; `PUBLIC_APP_URL` must point to the public AcaSift origin.
- Verification and password-reset sender identities remain separate.

## Validation
- Python source syntax parsed successfully.
- TypeScript/TSX source transpilation passed.
- Added backend regression tests for email-link requests without a pre-existing CSRF session.
- Added email-template and public-logo asset tests.
- Full Flask integration tests could not be executed in the authoring environment because Flask/Werkzeug dependencies were not installed; execute the included tests in Render's build/test environment or a configured Python environment.


# AcaSift 0.6.0 — Academic collaboration and assessment

## Academic workspace
- Added organisational courses with course codes, descriptions and secure enrolment codes.
- Added course-level lecturer and student membership, scoped to active organisational workspace membership.
- Added assignment lifecycle states: draft, published and closed.
- Added assignment deadlines, late-submission and resubmission controls.
- Added private student assignment submissions with attempt tracking and file-hash duplicate prevention.
- Added assignment-specific peer similarity comparisons using the existing TF-IDF cosine and N-gram analysis engine.
- Added lecturer-triggered cohort-wide reanalysis so earlier submissions can be compared with later cohort submissions.
- Course enrolment codes use 64-bit random values (16 hexadecimal characters), are stored only as SHA-256 hashes and are protected by database-backed attempt throttling.
- Added lecturer assessment outcomes and written feedback.

## Privacy and access control
- Students can list only their own submissions for an assignment and view only an aggregate similarity overview.
- Student-facing reports do not expose peer names, filenames, documents or matched passages.
- Course lecturers and authorised workspace managers can view submissions and peer-source evidence for courses in their active organisational workspace.
- Generic personal comparison routes and dashboard history exclude assignment-based comparison reports.
- Course creation and membership require the appropriate organisational workspace role.
- Course enrolment codes are stored as SHA-256 hashes and can be rotated.

## Database and deployment
- Added `courses`, `course_memberships`, `assignments`, `academic_submissions` and `assignment_assessments` tables.
- Tables are created by the existing `flask init-db` startup command through SQLAlchemy `create_all()`.
- No existing tables are dropped or rebuilt. No new Render environment variables are required.
- Existing accounts, workspaces, documents, comparisons and Nylas settings are retained.

## Validation
- Python source syntax compilation passed.
- TypeScript/TSX syntax transpilation passed.
- Backend regression tests added for course creation, role enforcement, enrolment, assignment submission, peer comparison, privacy, cohort reanalysis and lecturer assessment.
- Full Flask integration tests and full TypeScript project type-check could not be executed in the authoring environment because Flask/Flask-SQLAlchemy and frontend npm dependencies were unavailable. They must be verified by the deployment build and the included test suite.


# AcaSift 0.7.0 — Flexible shared workspaces

## Workspace model
- Replaces the organisation-specific workspace concept with a generic shared workspace.
- Any verified account can create a shared workspace without institutional information or
  platform-admin approval.
- Existing `organization` workspace rows are migrated in place to `shared`; IDs and related
  academic data remain unchanged.
- Adds workspace descriptions and member counts.
- Preserves private personal workspaces.

## Roles and membership
- Supports an owner and multiple administrators in each shared workspace.
- Only the owner can appoint, change or remove administrators.
- Workspace administrators can manage ordinary members and invitation links.
- Adds member-role updates and member removal endpoints.
- Platform administrator privileges remain separate from workspace roles.

## Invitation links
- Adds cryptographically random invitation tokens with SHA-256 hashes stored in the database.
- Supports Member, Student and Lecturer invitation roles.
- Supports optional course-scoped invitations that automatically create matching course
  membership for Student or Lecturer recipients.
- Supports optional expiration date/time and optional maximum-use counts.
- Supports immediate revocation.
- Requires recipients to sign in or register and verify their email before joining.
- Invitation links cannot grant administrator or owner privileges.
- Adds invite preview and acceptance routes and a React invitation landing page.

## Academic workflow
- Course creation and enrolment now operate in shared workspaces rather than requiring an
  approved organisational workspace.
- Student invitations establish workspace membership; course enrolment remains a separate
  course-level permission step through course codes or lecturer assignment.
- Existing assignments, submissions, similarity comparisons and assessment records are retained.

## Deployment and migration
- Adds the `workspace_invites` table through SQLAlchemy `create_all()`.
- Adds `workspaces.description` when missing.
- Updates legacy `organization` workspace types to `shared`.
- No manual Neon SQL or new Render environment variables are required.
- Existing Nylas email configuration is unchanged.

## Security notes
- Invite secrets are returned only once when generated; only token hashes are persisted.
- Invite expiration, revocation and usage limits are checked on both preview and acceptance.
- Acceptance is rate-limited and protected by authenticated session + CSRF.
- Open invitation links grant only member/student/lecturer roles.
- Workspace isolation and course-level access checks remain in force.

## Validation notes
- Added regression tests for shared workspace creation, hashed invitation tokens, invitation
  preview, acceptance, usage limits, expiration, revocation and administrator privilege control.
- Python and TypeScript source validation plus the Render Docker production build should be run
  before treating this release as deployed. Full runtime integration depends on the configured
  Flask and frontend dependencies.
