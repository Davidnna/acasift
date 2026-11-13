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
- Compare each submission with all eligible peer submissions made to the same Submission Request.
- Run concurrent, targeted scholarly searches across OpenAlex, Crossref, Europe PMC, DOAJ, Zenodo, Semantic Scholar and arXiv.
- Temporarily retrieve publicly accessible full text only when a recognised reuse licence is confirmed; discard the full text after comparison.
- Report source-linked exact N-gram matches, fuzzy sentence matches, TF-IDF lexical similarity and optional local semantic sentence matches.
- Retain bibliographic metadata, source/DOI links, similarity metrics and short evidence excerpts—not permanent copies of external papers.
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

Documents from unrelated requests are not included in a request's peer comparison. Each report also includes any permitted external scholarly sources found during the live search. Semantic sentence matching is available only when the optional local embedding model is installed and enabled. Cross-language comparison and OCR of scanned image-only PDFs are not supported.

## Historical data and migration

AcaSift previously supported personal workspaces. The shared-workspace-only migration archives active personal workspaces and leaves their stored documents, comparison records and historical membership rows intact. These archived personal workspaces are not returned by active workspace queries and cannot be used for new document uploads or comparisons. Existing shared workspaces, accounts, Submission Requests, submissions and review records are retained.

Database changes are managed through the versioned migration ledger `acasift_schema_migrations`. Do not delete or manually edit the migration ledger. Future schema or data changes must be implemented as new, idempotent migrations.

## Live external scholarly comparison (0.16.0)

Each Submission Request comparison now performs targeted scholarly discovery across OpenAlex, Crossref, Europe PMC, DOAJ, Zenodo, Semantic Scholar and arXiv. Provider searches run concurrently. Search queries are derived from a small set of document title/keyword phrases; the complete submitted document is not sent to scholarly metadata providers.

A source's full text is retrieved only when it is publicly accessible and a recognised reuse licence is confirmed in provider metadata or, for eligible Europe PMC XML, in the article XML itself. Retrieved PDF, HTML, XML or text is processed in memory for the current comparison and discarded. To bound request time and memory use, the default run limit is 24 scholarly metadata records and 8 permitted full-text downloads; these limits are configurable. Every full text successfully retrieved within those limits is compared. AcaSift does not create a permanent external reference-document repository.

Reviewer reports retain bibliographic metadata, DOI and source links, similarity metrics, and short matched evidence excerpts. External full-text content is not retained. The report distinguishes TF-IDF lexical similarity, exact N-gram coverage, fuzzy sentence coverage and semantic sentence coverage. The combined overlap indicator is a reviewer-prioritisation measure, not a probability of plagiarism or a misconduct finding.

Semantic sentence matching uses a local SentenceTransformer model and is optional because it requires additional memory and CPU resources. To enable it, install `backend/requirements-semantic.txt`, set `ENABLE_LOCAL_SEMANTIC=true`, and configure `SEMANTIC_MODEL_NAME`. It is disabled by default in the Render configuration. When it is not enabled, the report clearly marks semantic analysis as not enabled; if the model is configured but cannot load, it is marked unavailable. The combined indicator reweights the other coverage measures when semantic coverage is unavailable.

The former administrator reference-acquisition workflow and permanent reference-bank interface are retired in 0.16.0. Historical database tables and production records are retained for compatibility and audit purposes. The 0.16.0 migration archives legacy reference entries and retires old acquisition metadata without deleting source documents, uploaded files or audit history. These records are not used by new comparisons and are no longer exposed through the application interface.

Optional environment settings:

```env
OPENALEX_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
SCHOLARLY_SEARCH_CONTACT_EMAIL=
MAX_EXTERNAL_SOURCES=24
MAX_EXTERNAL_DOWNLOADS=8
MAX_EXTERNAL_DOWNLOAD_MB=12
ENABLE_LOCAL_SEMANTIC=false
SEMANTIC_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
SEMANTIC_MATCH_THRESHOLD=0.82
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
