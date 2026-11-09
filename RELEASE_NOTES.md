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
