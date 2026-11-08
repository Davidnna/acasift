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
