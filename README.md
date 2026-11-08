# AcaSift — Academic Similarity Analysis

**Tagline:** Find the overlap. Follow the source.

AcaSift is a web-based academic document similarity analysis platform developed with Flask
and PostgreSQL. It supports PDF, DOCX and TXT text extraction, TF-IDF/Cosine Similarity,
word-based N-gram matching, matched-passage review and source-level comparison reports.

AcaSift is the software brand for the final-year research project titled **“Design and
Implementation of a Plagiarism Detection System.”** The brand name does not change the
approved academic research topic.

**Current release:** 0.2.0

> Similarity results are indicators of textual overlap. They are not automatic findings
> of plagiarism. Human review is required.

## 1. Public website and application access

Unauthenticated visitors can access the public homepage and the About, Features, How It
Works, FAQ and Get Access pages. The private dashboard, document workspace, reports and
administration routes remain protected by authentication and role checks. Self-service
registration is not enabled: accounts are created by an authorised administrator.

The public pages describe the current product scope accurately. AcaSift compares submissions
against an administrator-curated internal reference repository; it does not search the entire
internet, perform OCR on scanned PDFs, or provide semantic paraphrase detection.

## 2. Features in this development milestone

- Administrator and registered-user accounts.
- Administrator-managed account creation.
- Administrator upload of reference documents.
- User upload of academic submissions.
- PDF, DOCX and TXT text extraction.
- Text normalisation through tokenisation and case folding.
- TF-IDF vectorisation and Cosine Similarity.
- Word-based N-gram overlap and passage offsets.
- Comparison history and source-level reports.
- PostgreSQL support, with SQLite available for local development.

Scanned/image-only PDFs are not supported in this version because OCR is outside the
initial project scope.

## 3. Requirements

- Python 3.10 or later (Python 3.11 is recommended).
- PostgreSQL 14 or later for the database configuration used in the final project.
- A modern web browser.

## 4. Installation (Windows PowerShell)

Open PowerShell in the extracted project folder.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

For a first local run, the example `.env` uses SQLite. This allows you to verify the
application before configuring PostgreSQL.

For PostgreSQL, create a database and user, then edit `DATABASE_URL` in `.env`:

```text
DATABASE_URL=postgresql+psycopg://acasift_user:your_password@localhost:5432/acasift_db
```

Do not commit `.env` or disclose its secret values.

## 5. Initialise the database and create an administrator

```powershell
flask --app run.py init-db
flask --app run.py create-admin
```

The create-admin command prompts for the administrator's name, email and password.
Use a password of at least 10 characters.

## 6. Start the application

```powershell
flask --app run.py run --debug
```

Open:

```text
http://127.0.0.1:5000
```

Sign in using the administrator account created in step 4.

## 7. First-use workflow

1. Sign in as administrator.
2. Open **Add reference document**.
3. Upload the two synthetic `.txt` examples in `sample_documents/` to populate the
   reference repository.
4. Open **Manage users** and create a normal user account.
5. Sign out and sign in as the normal user.
6. Upload a test document containing some sentences from one of the sample references.
7. Review the generated comparison report.
8. Sign in as administrator to add or manage reference documents.

The sample reference files are synthetic demonstration material. They are not published
academic sources and must not be represented as research evidence.

## 8. Run the tests

```powershell
python -m unittest discover -s tests -v
```

## 9. Similarity calculations

### Document-level score

The application fits a TF-IDF vectoriser to the submitted text and the available
reference texts, then calculates Cosine Similarity. The displayed value is:

`cosine_similarity * 100`

This is a vector similarity score, not the percentage of plagiarised content.

### Passage-level coverage

The application creates unique word-based N-grams from the submitted text and checks
which of those sequences occur in each reference document:

`matched_ngram_coverage = unique_matching_query_ngrams / unique_query_ngrams * 100`

The report stores offsets into the submitted and reference text to support passage review.
The current implementation uses one selected N-gram size (default 5); for documents
shorter than that size, the size is reduced to the available token count.

## 10. Important implementation notes

- The current comparison process is synchronous and is suitable for a student-project
  prototype and modest test repositories. Comparisons use administrator-curated reference
  documents only; users' private submissions are not automatically exposed as sources.
  Large repositories should use background jobs and indexed candidate retrieval.
- The comparison query currently examines up to `MAX_COMPARISON_SOURCES` processed
  documents, ordered by upload time. Review and document this limit in experiments.
- File uploads are stored in the local `instance/uploads` folder. For production
  deployment, use private object storage or a protected persistent volume.
- Add HTTPS, secure production secrets, database backups, rate limiting, audit logging,
  and deployment-specific hardening before public deployment.
- The initial system does not perform internet-wide search, OCR, source-code matching,
  cross-language matching or semantic paraphrase detection.

## 11. Project structure

```text
acasift/
├── app/
│   ├── routes/
│   ├── services/
│   ├── templates/
│   ├── static/
│   ├── extensions.py
│   ├── models.py
│   └── decorators.py
├── sample_documents/
├── tests/
├── config.py
├── run.py
├── requirements.txt
└── README.md
```

## 12. Next development tasks

- Add pagination and document-retention controls.
- Add downloadable PDF reports if required.
- Add asynchronous processing for larger repositories.
- Add a labelled evaluation corpus and calculate precision, recall, F1-score and
  processing time for Chapter Five.
- Capture screenshots of the actual running application for Chapter Four.


## 13. GitHub + Render deployment

The repository includes `render.yaml` for an AcaSift Render Blueprint deployment.

1. Push the complete project to a GitHub repository using the `main` branch.
2. In Render, choose **New > Blueprint** and connect the GitHub repository.
3. Render reads `render.yaml` and configures the Python web service.
4. During Blueprint setup, provide `DATABASE_URL` from the Neon Console. Use the connection string for the correct Neon project, branch, database and role. Keep its TLS parameters (such as `sslmode=require`).
5. Render generates `SECRET_KEY` automatically.
6. Complete the initial deployment and check `/health`.
7. Create the first administrator from your own computer, pointing the local CLI at the
   Neon database. Temporarily set `DATABASE_URL` in your local `.env` to the Neon connection
   string, run `flask --app run.py create-admin`, follow the prompts, then restore your local
   development URL if needed. Do not paste the connection string or password into chat.

AcaSift normalises standard `postgresql://` and `postgres://` connection strings to SQLAlchemy's
Psycopg 3 dialect. The `DATABASE_URL` must never be committed to GitHub. Render's Free web
services do not provide Shell access, so use the local CLI method above on the free plan.

### Automatic redeployment

The Blueprint sets `autoDeployTrigger: commit` and watches the `main` branch. A push to that
branch triggers a new build and deployment. Use GitHub as the source of truth: make code
changes locally, test them, commit, and push. Do not edit production files manually in Render.

### Database and uploaded files

PostgreSQL/Neon stores application records and extracted document text. AcaSift 0.2.0
stores uploaded originals on the application filesystem but does not yet provide a download
feature. Render's free web service filesystem is ephemeral; uploaded originals may disappear
when the service restarts or redeploys. Before adding file downloads or treating original
uploads as durable records, move originals to private object storage or another persistent
storage service. The database itself remains external in Neon.

### Important deployment note

`flask --app run.py init-db` creates missing tables at startup. It does not alter existing
tables when the schema changes. Before introducing database schema changes after launch,
we must add and run database migrations (for example, with Flask-Migrate/Alembic).
