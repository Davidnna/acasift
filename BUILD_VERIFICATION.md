# Build and verification status — AcaSift 0.16.0

## Checks completed

- Python syntax compilation: all backend Python source files passed.
- Similarity-engine unit tests: 15 passed, 0 failed.
- Scholarly provider smoke checks: passed using mocked provider responses; all seven provider adapters were exercised concurrently (21 mocked provider-query calls in the test scenario).
- Licence-policy checks: unrecognised licences and unlicensed article XML were rejected.
- Temporary retrieval check: source full text was not included in the returned evidence report; only short excerpts and source metadata were retained.
- Frontend TypeScript/TSX syntax transpilation: 20 source files parsed with no syntax errors.
- Retired reference-bank/acquisition imports and active UI/API references were removed. Historical ORM mappings remain only for migration and production-record compatibility.

## Checks not completed in this environment

The complete Flask/SQLAlchemy backend test suite and database migration execution could not be run because the environment did not have the project's Python dependencies installed and package installation was blocked by unavailable network/DNS access.

The full Vite production build and React/TypeScript type-check could not be run because frontend npm dependencies were not installed and package access was unavailable. The TypeScript/TSX syntax-only transpilation did pass.

## Required pre-production checks

In an environment with package access:

1. `cd backend && pip install -r requirements.txt`
2. Run the full backend test suite: `python -m unittest discover -s tests -v`
3. `cd frontend && npm install && npm run build`
4. Back up the production PostgreSQL database and uploaded-document storage.
5. Deploy 0.16.0 and verify the new migration ledger entry, reviewer report access, source links and external-search limits.

No live scholarly API calls were made during the isolated provider smoke tests.
