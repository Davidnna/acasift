# ACASIFT 0.16.0 upgrade notes

1. Back up the production PostgreSQL database and uploaded-document storage before deployment.
2. Deploy the complete 0.16.0 source using the existing Docker/Render configuration.
3. On startup, `flask --app run.py init-db` applies the new versioned migration.
4. The migration adds external similarity fields/tables and archives old reference-bank entries and persistent scholarly metadata. It does not delete existing documents, uploads, comparison reports or audit records.
5. Existing acquisition/reference UI routes and APIs are no longer exposed. Legacy database tables remain for compatibility and audit history.
6. `rapidfuzz` is installed from the main backend requirements. Local semantic analysis is optional; install `backend/requirements-semantic.txt` and set `ENABLE_LOCAL_SEMANTIC=true` only when the host has sufficient memory and CPU.
7. Run the backend test suite and `cd frontend && npm install && npm run build` in an environment with package access before promoting to production.

Default external-search limits are 24 scholarly metadata records and 8 permitted full-text downloads per run. They can be changed through `MAX_EXTERNAL_SOURCES`, `MAX_EXTERNAL_DOWNLOADS` and `MAX_EXTERNAL_DOWNLOAD_MB`.

External full text is never imported into the permanent document store. Only metadata, source links, metrics and short matched excerpts are retained.
