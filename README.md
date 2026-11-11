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
- Create Submission Requests to collect documents from workspace members and authenticated external participants.
- Generate restricted request links with optional expiration, usage limits and revocation.
- Assign request-level reviewers without granting workspace administration privileges.
- Compare private-workspace documents against AcaSift's central Reference Bank.
- Compare shared Submission Request documents against other eligible submissions in that same request.
- Provide request-level review outcomes and feedback while protecting peer-submission identities and excerpts in contributor reports.
- Preserve historical submissions and reports while older records are migrated into the generic workflow.
- Maintain one administrator-managed Reference Bank with source, licence and permission records.
- Discover scholarly publications through OpenAlex, Crossref, Europe PMC, DOAJ, Zenodo, Semantic Scholar and arXiv APIs.
- Deduplicate discovered records by DOI or a normalised title/year fingerprint and retain resumable provider pagination state.
- Automatically retrieve and index a small bounded batch of full texts only when the source supplies a recognised reuse licence; retain other results as metadata without using them in comparisons.
- Support account registration, email verification and password recovery.
- Let users upload, replace and remove a profile picture from their account page.
- Let users request an email address change, confirmed through a one-time verification link sent to the new address.
- Provide keyboard-friendly navigation, visible focus states, screen-reader announcements and responsive layouts.

## Project folders

- `frontend/` contains the AcaSift user interface.
- `backend/` contains application services, data access, authentication and analysis features.


## Version 0.14.2 correction

This maintenance release fixes a SQLAlchemy model-name collision in the scholarly acquisition models. The Python attributes are named `search_query`, while the existing database column remains `query`; this preserves the production schema and existing acquisition records. The administrator acquisition dashboard and resumable search-state lookups can therefore use Flask-SQLAlchemy's inherited `Model.query` interface correctly. No database migration is required for this attribute-only mapping correction.

## Scholarly reference acquisition

Platform administrators can open **Administration → Reference Acquisition** to search connected scholarly services. The initial connector set includes:

- OpenAlex — large-scale scholarly metadata discovery, with cursor pagination.
- Crossref — DOI and publication metadata, with offset pagination.
- Europe PMC — biomedical metadata and open-access full-text XML retrieval; the article XML licence is checked before indexing.
- DOAJ — open-access journal article discovery and licence metadata.
- Zenodo — research record and file discovery, including record-level licence metadata.
- Semantic Scholar — paper metadata and open-access locations; an open-access PDF link alone is not treated as a reuse licence.
- arXiv — preprint metadata and licence-aware PDF locations.

The acquisition process stores a canonical scholarly metadata record, deduplicates records across providers, preserves search pagination state, and attempts no more than two full-text imports in one administrator-triggered run. A run discovers up to 25 records. Repeating the same provider and query continues from its saved cursor, page or offset. Use a different query to start a separate search.

Only exact, recognised CC BY 2.0/3.0/4.0 and CC0 1.0 licence declarations are automatically eligible in this initial release. Public availability, an open-access flag, an abstract, or a PDF link alone is not sufficient. Documents without a confirmed eligible licence remain metadata-only and are not placed in the active comparison corpus. Third-party material exclusions and provider terms still apply; administrators must not treat automated licence detection as a substitute for reviewing source conditions.

### Optional environment settings

```env
OPENALEX_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
ACQUISITION_CONTACT_EMAIL=
```

An OpenAlex API key is recommended for cursor paging beyond the first page. A Semantic Scholar API key can improve request access. The contact email is included in polite-pool requests where supported. Keep all API keys in Render environment variables or a local `.env` file; never commit real credentials.

### Controlled scheduled acquisition

A bounded command is available for a local deployment or a separately configured scheduled service:

```bash
flask --app run.py acquisition-discover --provider openalex --query "computer science" --limit 25 --admin-email administrator@example.com
```

The command must run with the same database and environment configuration as AcaSift. A production schedule should use a dedicated scheduled job or worker, not the web request process. Render Cron Jobs are a separate billable service; they are not created automatically by this repository. The administrator dashboard runs a bounded acquisition directly when requested.

### Current scale boundary

This release establishes multi-provider discovery, resumable pagination, deduplication, licence-aware retrieval and local full-text ingestion. It is not yet a bulk snapshot importer or a million-document comparison index. The current similarity engine still loads the eligible reference documents for a comparison; large-scale deployment requires a separate inverted-index/search architecture, object storage capacity planning, and background ingestion workers before the corpus grows to hundreds of thousands or millions of full texts.

CORE is not enabled in this release because product use requires a separate licensing arrangement. OpenAIRE bulk dumps and Crossref/OpenAlex bulk snapshot ingestion are candidates for a later high-volume acquisition phase.

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
for a defined purpose. A request has a title, description, instructions, opening time, optional deadline, accepted file types,
maximum file size, late-submission and resubmission settings, and a status. Workspace members can
discover open requests and join them. Request-level reviewers can be assigned independently of
workspace administration privileges.

Administrators can create request-specific links for external participants. A link grants access to
one request only; participants must sign in with a verified AcaSift account and do not become
workspace members. Links support optional expiration, usage limits and revocation. Participants
can upload documents, view their own reports and receive review feedback.

Each request submission is compared only against other eligible submissions belonging to that same
request. It is not compared against the global Reference Bank, workspace documents or submissions
from unrelated requests. A contributor's own submissions and previous attempts are excluded from
peer-source comparison. Contributor reports hide peer identities and peer excerpts; authorised
reviewers and workspace administrators can inspect the underlying evidence. Private material from
unrelated users or workspaces is not exposed by this comparison policy.

Older structured records from previous releases are retained as migration sources. They are
converted into Submission Requests, preserving their documents, comparison links, participant
relationships and review feedback. The original records are not exposed through the active product
interface and are not deleted by this release.

## Reference materials

AcaSift maintains one central **Reference Bank**, managed by platform administrators. It contains
documents that have an appropriate recorded basis for retention and use in private similarity
checks. Each record retains its source, licence or permission basis, and verification information.
Public accessibility alone does not establish permission to reuse a document.

Users do not upload or manage personal or workspace reference documents. A document uploaded in a
personal workspace is compared with eligible documents in the central Reference Bank. Documents
submitted to a shared Submission Request are compared with other eligible submissions in that same
request; they are not added to the Reference Bank.

Older personal, workspace and request-level reference registry entries are archived by the
simplified reference-policy migration. Their underlying document records and files are retained to
protect historical data, but they are no longer eligible for new comparisons. Existing comparison
reports retain their original source records and labels for historical traceability.

## Deployment

The frontend and backend source code are maintained in separate folders. The current hosted
configuration builds the frontend and backend together so that authentication sessions and
security checks remain same-origin. A separate frontend and API deployment can be introduced when
a shared custom domain and the required cross-origin session configuration are available.

Database initialisation uses a versioned migration ledger named `acasift_schema_migrations`.
The initial schema is created during first-time bootstrap. Existing databases are checked against
migration invariants before an already-completed legacy migration baseline is recorded. Completed
migrations are not rerun on ordinary application restarts. Future schema or data changes must be
implemented as new, versioned migrations; do not delete or manually edit the migration ledger.
Startup logs report database-initialisation duration and the start of the Gunicorn web server.

For hosted deployments, configure the database connection, application secret and email delivery
settings in the hosting provider's private environment settings. Private checks use all eligible
documents in the central Reference Bank; Submission Request checks use all eligible peer submissions
within the same request. Never commit real credentials, API keys or private database connection
strings to the repository.
