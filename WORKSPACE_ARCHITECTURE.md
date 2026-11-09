# AcaSift workspace architecture (0.5.0)

## Product model

AcaSift is institution-agnostic. A person can use an individual workspace without an institutional email, matriculation number, staff number or school affiliation. An organisation can request a separate shared workspace. A request remains pending until a platform administrator reviews it.

## Roles

### Platform role

- `user`: ordinary AcaSift account.
- `admin`: AcaSift platform administrator. This role can review organisational workspace requests and manage platform-level reference sources and accounts.

### Workspace membership role

- `owner`: controls the organisational workspace and membership.
- `admin`: manages workspace membership.
- `lecturer`: reserved for lecturer-facing academic workflows.
- `student`: reserved for student-facing academic workflows.
- `member`: ordinary workspace participant.

A user's platform role and workspace role are separate. A user may be a lecturer in one workspace and a member in another.

## Workspace lifecycle

1. Every existing account receives one private personal workspace during the 0.5.0 migration.
2. The user can submit an organisational workspace request with its name, type, website and intended use.
3. The request remains pending. It does not create an active workspace.
4. A platform administrator reviews the request and verifies that the requester is authorised to represent the organisation.
5. Approval creates the organisation workspace and makes the requester its owner.
6. The owner or a workspace administrator can add existing active AcaSift accounts and assign membership roles.

## Data visibility rules in 0.5.0

- A user's submissions are private to that user and their selected workspace.
- A user sees their own submissions in the active workspace.
- Platform-curated reference documents remain available as shared comparison sources.
- Workspace-scoped reference documents are visible only to active members of that workspace. Workspace owners/admins can add references to an organisation workspace; personal workspace owners can add private references.
- Private reference documents are visible only to their uploader.
- Comparison reports are visible only to their owner in this release. Platform administrator status does not automatically grant access to another user's private report.

## Deferred academic permissions

The `student` and `lecturer` workspace roles are stored now, but lecturer access to other members' submissions is intentionally not enabled yet. That permission must be implemented through course and assignment membership, with explicit assignment-level access checks. Student-to-student comparison (the selected Option C behaviour) will be introduced only after those boundaries exist.

## Migration safety

The startup migration is additive. It creates the new workspace tables, adds nullable workspace identifiers and visibility scopes to existing document/comparison tables, creates a personal workspace for each existing user, assigns legacy submissions and comparisons to their owner's personal workspace, and preserves existing administrator-curated reference documents as platform references. It does not delete users, documents, comparison results or reports.
