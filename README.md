# AcaSift

AcaSift is an independent document similarity analysis platform built around shared workspaces and structured document submissions. Workspace administrators create Submission Requests, participants submit documents, and AcaSift compares eligible submissions made to the same request. Workspace owners, administrators and reviewers assigned to a request can inspect similarity results and matching passages. Contributors receive a submission receipt and any reviewer feedback recorded for them.

AcaSift does not require institutional affiliation. Similarity indicators support human assessment; they do not automatically determine plagiarism or misconduct.

## What AcaSift does

- Analyse PDF, DOCX and TXT documents for textual similarity.
- Extract readable text and identify overlapping word sequences.
- Provide shared workspaces with owner, administrator and member permissions.
- Allow verified users to create workspaces or join through invitation links.
- Let workspace administrators create Submission Requests with instructions, accepted formats, deadlines and submission rules.
- Accept submissions from workspace members and authenticated external participants using request-specific links.
- Compare each submission only with eligible submissions made to the same Submission Request.
- Restrict similarity reports, matching passages and peer-submission details to workspace administrators and reviewers assigned to the request.
- Give contributors submission receipts and access to reviewer feedback without exposing similarity reports.
- Support request-level review outcomes and reviewer assignment.
- Support account registration, email verification, password recovery, profile pictures and verified email changes.
- Provide responsive, keyboard-accessible interfaces and visible focus states.

## Project structure

- `backend/` contains the Flask application, API routes, database models, migrations, authentication and document-analysis services.
- `frontend/` contains the React and TypeScript application.
- `Dockerfile` builds the frontend and backend into the current single-origin production service.

## Shared-workspace workflow

1. A user creates an AcaSift account and verifies the email address.
2. The user creates a shared workspace or joins one through an invitation link.
3. A workspace owner or administrator creates a Submission Request describing the documents to be collected.
4. Workspace members or authenticated external participants submit documents to that request.
5. AcaSift extracts the text and compares each submission with eligible peer submissions belonging to the same request. A contributor's own submissions and previous attempts are excluded from peer-source comparison.
6. Workspace administrators and assigned reviewers inspect the similarity results and matching passages, then record a review outcome and optional feedback.
7. Contributors can return to the request to see their submission receipt and any feedback. They cannot view similarity scores, matching passages or other participants' documents.

Documents from unrelated requests are not included in a request's comparison. The current release does not perform internet-wide searches, semantic paraphrase detection, cross-language comparison or OCR of scanned image-only PDFs.

## Historical data and migration

AcaSift previously supported personal workspaces. The shared-workspace-only migration archives active personal workspaces and leaves their stored documents, comparison records and historical membership rows intact. These archived personal workspaces are not returned by active workspace queries and cannot be used for new document uploads or comparisons. Existing shared workspaces, accounts, Submission Requests, submissions and review records are retained.

Database changes are managed through the versioned migration ledger `acasift_schema_migrations`. Do not delete or manually edit the migration ledger. Future schema or data changes must be implemented as new, idempotent migrations.

## Platform-managed reference services

Platform administrators can use **Administration → Reference Acquisition** to discover scholarly records through OpenAlex, Crossref, Europe PMC, DOAJ, Zenodo, Semantic Scholar and arXiv. The acquisition service stores scholarly metadata, preserves resumable pagination state and attempts bounded full-text retrieval where a recognised reuse licence is confirmed. Records without confirmed reuse rights remain metadata-only.

The platform-managed reference collection is administered separately. In the current release, shared Submission Request comparisons use peer submissions from the same request; the reference collection is not included in those request reports. Do not treat public accessibility or an open-access label alone as permission to retain or reuse a document.

Optional environment settings:

```env
OPENALEX_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
ACQUISITION_CONTACT_EMAIL=
```

Keep API keys and other credentials in the hosting provider's private environment settings or a local `.env` file. Never commit real credentials, API keys or database connection strings.

## Run AcaSift locally

### Requirements

- Python 3.11 or later.
- Node.js 20 or later and npm.
- SQLite for a simple local installation, or PostgreSQL for a persistent shared database.

### 1. Configure the backend

Open a terminal in the project folder:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install the Python packages:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a private `SECRET_KEY`. The example configuration uses a local SQLite database. Email verification, password recovery and email address changes require valid Nylas email settings; without those settings, public registration is unavailable.

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

Open the local address printed by Vite, normally `http://127.0.0.1:5173`. During local development, frontend API requests are forwarded to the backend at `http://127.0.0.1:5000`.

### 3. Build the production frontend

```bash
cd frontend
npm run build
```

The production bundle is placed in `backend/app/static/spa` and is served by the backend in the current single-origin deployment.

## Production deployment

The current hosted configuration builds the frontend and backend together so that authentication sessions and security checks remain same-origin. The application expects the hosting provider to supply the database connection, application secret, email delivery settings and any optional scholarly API credentials as environment variables.

The web process must bind to the port supplied by the hosting provider. Database initialisation runs through the versioned migration system before Gunicorn starts. A separate frontend/API deployment can be introduced later if a shared custom domain and the required cross-origin session configuration are available.
