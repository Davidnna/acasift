# AcaSift 0.7.0 — Workspace architecture

## 1. Workspace types

AcaSift has two workspace types:

- **Personal workspace**: created automatically for every account. Documents and comparisons
  remain private to the user.
- **Shared workspace**: created instantly by any verified account. It is a collaboration
  container for a class, assignment cohort, research group, project, organisation or any group.

A shared workspace does not represent or require a registered institution. Name and description
are user-defined. New shared workspaces do not require platform-administrator approval.

## 2. Workspace authority

Each shared workspace has one owner and may have multiple administrators.

| Role | Workspace permissions |
|---|---|
| Owner | Full control; appoint/change/remove administrators; manage members and invites |
| Admin | Manage ordinary members and invitation links; manage shared workspace resources |
| Lecturer | Create courses and manage courses to which they are assigned |
| Student | Join courses and submit assignment work |
| Member | Participate in ordinary shared workspace collaboration |

The platform administrator role is separate from workspace roles. An invitation link cannot grant
owner or administrator access. A workspace owner can appoint an existing member as an admin after
they join. An admin cannot appoint or remove another admin.

## 3. Invitation links

A workspace owner or admin can create an invitation link for:

- Member
- Student
- Lecturer

Each invitation can have:
- An optional expiration date and exact time.
- An optional maximum-use count.
- Unlimited uses when the maximum-use field is blank.
- Immediate revocation by an owner or admin.
- Optional access to one active course.

A course-specific invitation must grant Student or Lecturer. Accepting it creates the workspace
membership and the matching course membership in the same operation. This lets a lecturer create
a shared workspace, create a course, generate a Student invitation for that course and share one
link with a class. Students do not need to be entered one by one or separately type a course code.

A workspace-only invitation joins the workspace but leaves course enrolment separate. This is
useful for general collaboration spaces or workspaces containing several courses.

### Token handling

Invitation secrets are generated using a cryptographically secure random generator. The raw token
is returned only once when the link is created. A SHA-256 hash is stored in PostgreSQL. Preview
and acceptance check the hash, workspace status, revocation, expiration and use limit. Acceptance
is authenticated, CSRF-protected and rate-limited.

If a recipient is signed out, the invitation page redirects them to sign-in and preserves the
invitation URL as the post-login destination. A new user must complete normal account registration
and email verification before accepting. If the verification flow takes them away from the invite,
they can reopen the original invitation link afterwards.

## 4. Existing-workspace migration

The 0.7.0 startup migration:
1. Adds `workspaces.description` if it is missing.
2. Changes existing `workspace_type='organization'` rows to `workspace_type='shared'`.
3. Creates `workspace_invites` through SQLAlchemy `create_all()`.
4. Adds `workspace_invites.course_id` if an earlier table exists without it.

The migration preserves workspace IDs, owners, memberships, documents, comparisons, courses,
assignments, submissions and assessments. Personal workspaces remain private. No manual SQL or
new Render environment variables are required.

## 5. Recommended lecturer workflow

1. Create a shared workspace named for the class or assignment cohort.
2. Create a course inside the shared workspace.
3. Create an invitation link with the Student role.
4. Select the course in the invitation form to enable automatic course enrolment.
5. Optionally set an expiry date/time or maximum-use count.
6. Share the link with the class.
7. Students sign in or register, verify their email and accept the invitation.
8. Create and publish assignments. Students submit their work from the assignment page.
9. Run cohort analysis and review results.

A lecturer who creates the workspace is its owner. A lecturer invited into another person's
workspace can manage courses assigned to them; workspace owners/admins manage workspace-level
invitation links and membership.

## 6. Data boundaries

- Personal documents remain private to their owners.
- Shared workspace references are accessible only to active workspace members under the existing
  reference permissions.
- Course assignments and submissions remain scoped to the course and shared workspace.
- Students can view their own submission records and anonymised similarity summaries.
- Authorised course lecturers and workspace managers can review submissions and peer-source
  evidence within the relevant course.
- Similarity scores remain indicators for human review, not automatic plagiarism findings.
