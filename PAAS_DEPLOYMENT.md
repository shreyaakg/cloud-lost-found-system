# PaaS Deployment Guide — Render

## What is PaaS?

Platform as a Service (PaaS) is a cloud computing model where the provider manages the
underlying infrastructure (servers, OS, networking, runtime) and you only deploy your
application code. You do not configure virtual machines, install Python, or manage web
servers manually.

Examples: Render, Heroku, Railway, Google App Engine, AWS Elastic Beanstalk.

## Why Render?

| Reason | Detail |
|---|---|
| Free tier | Provides a free web service tier suitable for college projects |
| GitHub integration | Automatic deploys on every git push |
| No credit card required | Free tier requires no payment details |
| Python support | Native Python/gunicorn support, no Docker required |
| Simple UI | Straightforward dashboard, easy to explain in a viva |
| Custom domains | Free subdomain provided (yourapp.onrender.com) |

## Deployment Architecture

```
Developer (VS Code)
        |
        | git push
        v
  GitHub Repository
        |
        | Render pulls on push
        v
  Render Build Server
    - pip install -r requirements.txt
        |
        v
  Render Web Service (Linux container)
    - gunicorn app:app
    - SQLite database (ephemeral)
    - /tmp/uploads (ephemeral file storage)
        |
        v
  Public URL: https://lostfound-cloud.onrender.com
```

## Important: SQLite on Render

Render's free tier uses an **ephemeral filesystem**. This means:

- The SQLite database (`instance/lostfound.db`) is recreated fresh on every deploy.
- Uploaded images stored in `/tmp/uploads/` are lost when the service restarts.
- This is **acceptable for a college project demonstration**.
- For production use, you would use a persistent PostgreSQL database (Render offers one)
  and AWS S3 for file storage (covered in Part 2).

The application handles this automatically:
- `db.create_all()` runs on every startup, recreating tables if needed.
- `config.py` detects the `RENDER` environment variable and uses `/tmp/uploads/`.

---

## Step-by-Step Deployment

### Step 1 — Install Git

Download and install Git from https://git-scm.com/download/win

Verify installation:
```
git --version
```

### Step 2 — Create GitHub Repository

1. Go to https://github.com and sign in (or create a free account).
2. Click **New repository**.
3. Name it: `lostfound-cloud`
4. Set visibility: **Public** (required for Render free tier).
5. Do NOT initialise with README (your project already has one).
6. Click **Create repository**.
7. Copy the repository URL shown — it will look like:
   `https://github.com/<your-username>/lostfound-cloud.git`

### Step 3 — Push Project to GitHub

Open a terminal in VS Code (`Ctrl+`` `) in your project folder and run these commands
**one at a time**:

```bash
git init
git add .
git status
```

Review the output of `git status`. Confirm that these files are NOT listed:
- `.env`
- `instance/`
- `venv/`
- `static/uploads/` (except `.gitkeep`)
- `*.db`
- `app_output.log`

If any of those appear, stop and check `.gitignore` before continuing.

```bash
git commit -m "Initial commit: Lost and Found Cloud application"
git branch -M main
git remote add origin https://github.com/<your-username>/lostfound-cloud.git
git push -u origin main
```

Replace `<your-username>` with your actual GitHub username.

After this, refresh your GitHub repository page — all project files should be visible.

### Step 4 — Create a Render Account

1. Go to https://render.com
2. Click **Get Started for Free**.
3. Sign up using your GitHub account (recommended — enables automatic deploys).

### Step 5 — Create a New Web Service on Render

1. From the Render dashboard, click **New +** → **Web Service**.
2. Click **Connect a repository**.
3. Authorise Render to access your GitHub account if prompted.
4. Find and select your `lostfound-cloud` repository.
5. Click **Connect**.

### Step 6 — Configure the Web Service

Fill in the following settings exactly:

| Setting | Value |
|---|---|
| Name | `lostfound-cloud` |
| Region | Singapore (or closest to you) |
| Branch | `main` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Instance Type | `Free` |

### Step 7 — Set Environment Variables

Scroll down to the **Environment Variables** section and add:

| Key | Value |
|---|---|
| `SECRET_KEY` | A long random string, e.g. `a8f3k2m9x7q1p5n6r4t0w8v2y3z6j1h4` |
| `DATABASE_URL` | `sqlite:///lostfound.db` |
| `RENDER` | `true` |

To generate a strong SECRET_KEY, run this locally:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as the value for `SECRET_KEY`.

Do NOT set `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` — these are for Part 2.

### Step 8 — Deploy

1. Click **Create Web Service**.
2. Render will begin the build process. You will see live build logs.
3. The build runs: `pip install -r requirements.txt`
4. Then starts: `gunicorn app:app`
5. Wait for the status to show **Live** (green).

Build typically takes 2–4 minutes on first deploy.

### Step 9 — Access the Public URL

Once deployed, Render provides a public URL in the format:

```
https://lostfound-cloud.onrender.com
```

(The exact subdomain depends on the name you chose.)

Click the URL to open your live application.

### Step 10 — Test the Deployed Application

Test each feature in order:

- [ ] Home page loads
- [ ] Register a new account
- [ ] Login with that account
- [ ] Dashboard shows statistics
- [ ] Report a Lost item (with and without image)
- [ ] Report a Found item
- [ ] Verify automatic match appears on Matches page
- [ ] Search lost items by name
- [ ] Filter by category
- [ ] View item detail page
- [ ] Edit an item (owner only)
- [ ] Mark item as Recovered
- [ ] SHA-256 integrity verification page
- [ ] Logout
- [ ] Confirm unauthenticated user is redirected to login

---

## Automatic Redeploys

Every time you push to the `main` branch on GitHub, Render automatically rebuilds and
redeploys the application. No manual action needed.

```bash
# Make a change, then:
git add .
git commit -m "Your change description"
git push
```

---

## Environment Variables Reference

| Variable | Where set | Purpose |
|---|---|---|
| `SECRET_KEY` | Render dashboard | Flask session signing key |
| `DATABASE_URL` | Render dashboard | Database connection string |
| `RENDER` | Render dashboard | Switches upload path to /tmp |
| `AWS_ACCESS_KEY_ID` | Render dashboard (Part 2) | AWS S3 access |
| `AWS_SECRET_ACCESS_KEY` | Render dashboard (Part 2) | AWS S3 secret |
| `AWS_S3_BUCKET` | Render dashboard (Part 2) | S3 bucket name |
| `AWS_REGION` | Render dashboard (Part 2) | AWS region |

---

## Screenshots to Capture (for submission)

1. GitHub repository showing all project files
2. Render dashboard showing the web service as **Live**
3. Render build logs showing successful `pip install` and `gunicorn` start
4. Render environment variables panel (blur the SECRET_KEY value)
5. Live application home page with the Render URL visible in the browser
6. Successful registration on the live URL
7. Dashboard on the live URL
8. A reported lost item on the live URL
9. Matches page on the live URL
10. SHA-256 verification page on the live URL

---

## Troubleshooting

### Build fails with "No module named X"
- Check `requirements.txt` includes all dependencies.
- Run `pip install -r requirements.txt` locally to verify.

### App crashes on start — "Address already in use"
- Render manages the port automatically via the `PORT` environment variable.
- Gunicorn on Render binds to `0.0.0.0:$PORT` automatically. No manual port config needed.

### App shows 500 error after deploy
- Check Render logs (Dashboard → your service → Logs tab).
- Most common cause: missing `SECRET_KEY` environment variable.

### Database is empty after redeploy
- This is expected with SQLite on Render's ephemeral filesystem.
- Re-register and re-add test data after each deploy.
- This is documented and acceptable for a college project.

### Images not showing after redeploy
- Also expected — `/tmp/uploads/` is cleared on restart.
- Re-upload images after each deploy.
- Part 2 will fix this using AWS S3 for persistent storage.

---

## Public URL

```
https://<your-service-name>.onrender.com
```

Replace with your actual Render URL after deployment.
