# AcaSift

AcaSift is an academic document similarity analysis application. It helps individuals and groups
compare documents with authorised reference materials, inspect matching passages and review
similarity indicators. Results support human assessment; they do not automatically determine
plagiarism or academic misconduct.

## What AcaSift does

- Analyse PDF, DOCX and TXT documents for textual similarity.
- Display comparison reports, matching passages and source information.
- Keep personal documents and reports private to their owners.
- Provide shared workspaces for classes, research groups, project teams and other collaborations.
- Support workspace owners, administrators, lecturers, students and members with role-based access.
- Manage workspace invitations, including revocation, optional expiry and usage limits.
- Support courses, assignments, student submissions and lecturer review in eligible shared workspaces.
- Maintain platform reference materials and authorised workspace reference collections.
- Support account registration, email verification and password recovery.

## Project folders

- `frontend/` contains the AcaSift user interface.
- `backend/` contains application services, data access, authentication and analysis features.

## Run AcaSift locally

### Requirements

- Python 3.11 or later.
- Node.js 20 or later and npm.
- SQLite for a simple local installation, or PostgreSQL for a persistent shared database.

### 1. Configure the backend

Open a terminal in the project folder and run:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Install the Python packages:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a private `SECRET_KEY`. The example uses a local SQLite
database. Email verification and password recovery require valid Nylas email settings; without
those settings, public registration is unavailable.

Initialise the database and start the backend:

```bash
flask --app run.py init-db
flask --app run.py run --debug
```

The backend runs at `http://127.0.0.1:5000`.

### 2. Start the frontend

Open a second terminal in the project folder:

```bash
cd frontend
npm install
npm run dev
```

Open the local address printed by Vite, normally `http://127.0.0.1:5173`. During local development,
frontend API requests are forwarded to the backend at `http://127.0.0.1:5000`.

### 3. Build the application

To create the production frontend bundle:

```bash
cd frontend
npm run build
```

The production bundle is placed in `backend/app/static/spa` and is served by the backend in the
current single-origin deployment.

## Deployment

The frontend and backend source code are maintained in separate folders. The current hosted
configuration builds the frontend and backend together so that authentication sessions and
security checks remain same-origin. A separate frontend and API deployment can be introduced when
a shared custom domain and the required cross-origin session configuration are available.

For hosted deployments, configure the database connection, application secret and email delivery
settings in the hosting provider's private environment settings. Never commit real credentials,
API keys or private database connection strings to the repository.
