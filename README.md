# AcaSift

AcaSift is a document similarity analysis and academic collaboration platform. It helps individuals and groups compare submitted documents with authorised reference materials, inspect overlapping passages and manage academic review workflows. Similarity measurements support human assessment; they do not independently establish plagiarism or academic misconduct.

## What AcaSift provides

- Document upload and text extraction for PDF, DOCX and TXT files.
- Document-level similarity analysis using TF-IDF cosine similarity and n-gram overlap.
- Reports with matched passages and source-level measurements.
- Private personal workspaces and shared workspaces for classes, teams, research groups and other collaborations.
- Workspace ownership, administrators, member roles, workspace settings, member departure and ownership succession.
- Invitation links with administrator-managed expiration, usage limits and revocation.
- Optional course-specific invitations that enrol students or lecturers in a selected course when they join.
- Courses, assignments, submissions, cohort comparison and lecturer assessment workflows.
- Account registration, email verification, password recovery and role-based access controls.

## Requirements for local use

Install the following software before running AcaSift:

- Python 3.11 or later.
- Node.js 20 or later and npm.
- SQLite (included with Python) for a simple local run, or PostgreSQL 14 or later for a production-like setup.
- Git (optional, for cloning the repository).

## Run locally

1. Clone or download the repository and open its root directory.
2. Create and activate a Python virtual environment:

   ```bash
   python -m venv .venv
   ```

   On Windows PowerShell:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

   On macOS or Linux:

   ```bash
   source .venv/bin/activate
   ```

3. Install the Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`. The example uses a local SQLite database, so no database server is required for a basic run. Provide a long, unique `SECRET_KEY` and set `PUBLIC_APP_URL` to `http://localhost:5000`. If you prefer PostgreSQL, replace `DATABASE_URL` with your PostgreSQL connection string. Configure the email provider only if you want to test registration verification and password recovery emails.

5. Install frontend dependencies and build the application:

   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

6. Initialise the database and create the first administrator:

   ```bash
   flask --app run.py init-db
   flask --app run.py create-admin
   ```

   Follow the prompts to create the administrator account. If the project configuration exposes a different first-administrator setup command, use the setup page shown by the application.

7. Start the application:

   ```bash
   python run.py
   ```

8. Open `http://localhost:5000` in your browser and sign in.

The first build compiles the frontend into the application’s static directory. Re-run `npm run build` after frontend changes. For active frontend development, run `npm run dev` from the `frontend` directory while the Flask application is running.

## Configuration

The application reads environment settings from `.env` in local development. At minimum, configure:

- `SECRET_KEY`: a unique secret used to protect sessions and security tokens.
- `DATABASE_URL`: the PostgreSQL connection string.
- `PUBLIC_APP_URL`: the base URL used when generating account and workspace links.
- `MAX_CONTENT_LENGTH_MB`: the maximum upload size in megabytes. The default is 15 MB.

Email delivery settings are optional for basic local exploration, but required for end-to-end testing of email verification and password recovery. Never commit `.env` or production credentials to source control.

## Supported documents and limitations

AcaSift currently accepts PDF, DOCX and TXT documents, subject to the configured upload-size limit. Text extraction is required for analysis; scanned image-only PDFs may not produce usable text. Similarity results identify textual overlap and require review of context, quotations, citations and source attribution.

## Project layout

- `app/`: Flask application, API endpoints, data models, services and static assets.
- `frontend/`: React application, routes, components, pages and styles.
- `tests/`: automated backend regression tests.
- `scripts/`: maintenance and evaluation utilities.
- `sample_documents/`: small sample text files for local evaluation.
- `render.yaml`: deployment service configuration.

## Run tests

With the Python virtual environment active and dependencies installed:

```bash
python -m unittest discover -s tests -v
```

To validate the frontend production build:

```bash
cd frontend
npm run build
```

## Privacy and responsible use

Workspace content is available according to membership and role permissions. Personal documents remain private to their owners. Similarity reports should be interpreted by authorised reviewers and should not be used as the sole basis for academic misconduct decisions.
