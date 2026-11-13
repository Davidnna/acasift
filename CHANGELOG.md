# Changelog

## 0.16.0 — 13 November 2026

### Added
- Concurrent targeted scholarly discovery through OpenAlex, Crossref, Europe PMC, DOAJ, Zenodo, Semantic Scholar and arXiv.
- Temporary in-memory retrieval of full text only where a recognised reuse licence is confirmed.
- Exact N-gram, fuzzy sentence, TF-IDF lexical and optional local semantic sentence comparison.
- Reviewer-facing external source evidence with bibliographic metadata, DOI/source links and short matched excerpts.
- PostgreSQL tables for external comparison metadata and short evidence passages.
- A versioned, non-destructive migration for new metrics and external evidence.

### Retired
- Administrator-facing persistent scholarly acquisition.
- The permanent AcaSift Reference Bank interface and upload/verification endpoints.
- User-managed and workspace reference upload endpoints.
- The old acquisition CLI command and persistent full-text ingestion service.

### Preserved
- Shared workspaces, memberships and invitations.
- Submission Requests, external participants and reviewer assignments.
- Same-request peer-submission comparison.
- Reviewer-only comparison reports and contributor-only receipts/review feedback.
- Existing accounts, documents, historical comparison reports and legacy database records.

### Data handling
- External full-text bytes and extracted full text are processed in memory and discarded after the run.
- The database stores source metadata, similarity metrics and short evidence excerpts only.
- Existing legacy reference/acquisition rows and source documents are archived/retained, not deleted.
- Semantic embeddings are optional and run locally when configured; they are disabled by default.
