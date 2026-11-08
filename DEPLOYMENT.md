# AcaSift 0.1.2 — GitHub and Render deployment checklist

## 1. Upload to GitHub
- [ ] Create a repository named `acasift`.
- [ ] Set the default branch to `main`.
- [ ] Extract the supplied ZIP archive.
- [ ] Open the extracted `acasift` folder and upload its CONTENTS to the repository root.
- [ ] Confirm that `README.md`, `render.yaml`, `run.py`, `config.py`, `.gitignore`,
      `.env.example`, `app/`, `tests/` and `sample_documents/` are at the repository root.
- [ ] Do not upload a real `.env` file, passwords, API keys or database connection strings.

Suggested first commit message:

`feat: initialize AcaSift academic similarity analysis platform`

## 2. Neon database
- [ ] Create or select a Neon PostgreSQL project and database.
- [ ] Copy the connection string from Neon Console > Connect.
- [ ] Preserve TLS parameters such as `sslmode=require`.
- [ ] Keep the connection string private. Do not put it in GitHub or this chat.

## 3. Render deployment
- [ ] Sign in to Render.
- [ ] Choose **New > Blueprint**.
- [ ] Connect the GitHub repository named `acasift`.
- [ ] Render should detect the root `render.yaml` and configure `acasift`.
- [ ] Set `DATABASE_URL` to the Neon connection string.
- [ ] Confirm Render generates `SECRET_KEY`.
- [ ] Complete the initial deployment and inspect the build logs.
- [ ] Open `https://YOUR-RENDER-SERVICE.onrender.com/health` and verify `{"status":"ok"}`.

## 4. Create the first administrator
Render Free web services do not provide Shell access. Run the Flask CLI from your
computer after installing the project requirements:

1. Temporarily set `DATABASE_URL` in your local `.env` file to the Neon connection string.
2. Run `flask --app run.py create-admin`.
3. Enter the administrator name, email and password when prompted.
4. Restore your local development `DATABASE_URL` after the administrator is created.
5. Sign in to the deployed AcaSift application.

## 5. Automatic redeployment
- [ ] Confirm Render is linked to the GitHub repository and the `main` branch.
- [ ] Confirm auto-deploy is set to **On Commit**.
- [ ] Make future code changes locally, test them, commit and push to `main`.
- [ ] Render will automatically build and redeploy each new commit.

## 6. Important storage limitation
Neon stores relational records and extracted document text. Uploaded original files are
currently written to the application filesystem. Render Free web services have an
ephemeral filesystem, so original uploads may disappear after a restart, spin-down or
redeployment. Do not treat original uploads as permanent until private object storage or
another persistent storage solution is implemented.

## 7. Free-plan behaviour
Render Free web services spin down after 15 minutes without inbound traffic and can take
about a minute to start again on the next request. Free services do not provide persistent
disks or Shell access. Check the provider's current limits before relying on the free tier.
