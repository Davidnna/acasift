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
