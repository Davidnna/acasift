# AcaSift

AcaSift is an independent document similarity analysis and plagiarism detection platform. It helps
individuals and groups compare documents with authorised reference materials, inspect matching
passages and review similarity indicators. It does not require institutional affiliation. Results
support human assessment; they do not automatically determine plagiarism or misconduct.

## What AcaSift does

- Analyse PDF, DOCX and TXT documents for textual similarity.
- Display comparison reports, matching passages and source information.
- Keep personal documents and reports private to their owners.
- Provide private personal workspaces and shared workspaces for teams, groups and other collaborations.
- Support workspace owners, administrators and members with role-based access.
- Manage workspace invitations, including revocation, optional expiry and usage limits.
- Provide a generic Submission Request model for collecting documents and organising review.
- Assign request-level reviewers without granting workspace administration privileges.
- Preserve historical submissions and reports while legacy academic records are migrated.
- Maintain platform reference materials and authorised workspace reference collections.
- Support account registration, email verification and password recovery.
- Let users upload, replace and remove a profile picture from their account page.
- Let users request an email address change, confirmed through a one-time verification link sent to the new address.
- Provide keyboard-friendly navigation, visible focus states, screen-reader announcements and responsive layouts.

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
database. Email verification, password recovery and email address changes require valid Nylas
email settings; without those settings, public registration is unavailable.

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

## Document submission workflow

A shared workspace owner or administrator can create a Submission Request to collect documents
for a defined purpose. A request has a title, description, instructions, accepted file types,
maximum file size, resubmission settings and a status. Workspace members can discover open
requests and join them. Request-level reviewers can be assigned independently of workspace
administration privileges.

The generic data model includes request-specific invitation records for external participation;
the external account onboarding and document upload workflow is being introduced in a subsequent
implementation phase. A request's submissions are intended to be compared against eligible global references,
workspace references and other eligible submissions belonging to that same request. Private
material from unrelated users or workspaces is not exposed by this comparison policy.

Existing course and assignment records are retained as legacy source records during migration.
Each legacy assignment is copied into a Submission Request, and its submissions, comparison links,
participant relationships and review feedback are preserved in the generic records. The legacy
records are not deleted by this release.

## Reference materials

AcaSift distinguishes personal, workspace, global and request-level reference sources. A document
is not added to the global reference collection merely because it is uploaded. Global contribution
requires explicit permission from a person who has the necessary rights. Reference acquisition
must retain source and licence provenance; publicly accessible does not automatically mean
reusable.

## Deployment

The frontend and backend source code are maintained in separate folders. The current hosted
configuration builds the frontend and backend together so that authentication sessions and
security checks remain same-origin. A separate frontend and API deployment can be introduced when
a shared custom domain and the required cross-origin session configuration are available.

For hosted deployments, configure the database connection, application secret and email delivery
settings in the hosting provider's private environment settings. Never commit real credentials,
API keys or private database connection strings to the repository.
