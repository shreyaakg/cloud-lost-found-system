# DEMO_SCRIPT.md
# 5–10 Minute Live Demonstration Script

---

## Before You Start

Open these tabs in your browser:
1. Your live application (Render URL or EC2 URL)
2. AWS S3 Console — your bucket
3. AWS EC2 Console — your instance

Have ready:
- A small JPG image file (< 5MB) to upload
- Your SSH terminal connected to EC2

---

## Step 1 — Open the Application (30 seconds)

Open your browser to the live URL.

**Say:**
"This is our Cloud-Based Lost Item Tracking and Recovery System. It is deployed on [Render / AWS EC2]. The application is built with Python and Flask."

Point to the URL bar — show the public URL.

---

## Step 2 — Register and Login (1 minute)

Click Register. Fill in your name, email, phone, and password.

**Say:**
"Passwords are never stored in plain text. We use PBKDF2-SHA256 hashing via Werkzeug. Even if the database is compromised, the actual passwords cannot be recovered."

After registering, log in.

**Say:**
"Flask-Login manages the session. Protected routes like the dashboard require authentication — unauthenticated users are redirected to login."

---

## Step 3 — Report a Lost Item with Image (1.5 minutes)

Click "Report Lost Item". Fill in:
- Item name: Black Leather Wallet
- Category: Accessories
- Description: Black leather wallet with student ID inside
- Location: Main Library Ground Floor
- Date: today's date
- Contact: your email
- Upload a JPG image

Click Submit.

**Say:**
"When the image is uploaded, the application validates the file extension AND checks the actual file header bytes — not just the extension. This prevents someone from renaming a PHP file to .jpg."

Point to the item detail page.

**Say:**
"The SHA-256 hash has been calculated from the image bytes and stored in the database. The S3 object key shows where the file is stored in AWS S3."

---

## Step 4 — Show S3 Object (1 minute)

Switch to the AWS S3 Console tab.

Navigate to your bucket → lost-items/ folder.

**Say:**
"The image is stored in our private S3 bucket under lost-items/ with a UUID filename. The original filename is never used — this prevents path traversal attacks and filename guessing."

Click on the object → Properties tab.

**Say:**
"The object has AES256 server-side encryption. AWS encrypts the data before writing it to disk. This ensures confidentiality at rest."

Point to Block Public Access settings.

**Say:**
"The bucket is completely private. There is no public URL for this object."

---

## Step 5 — Show SHA-256 Integrity Verification (1 minute)

Go back to the application. On the item detail page, click "Verify File Integrity (SHA-256)".

**Say:**
"The application downloads the image from S3, recalculates its SHA-256 hash, and compares it with the hash stored in the database at upload time."

Point to the result.

**Say:**
"INTEGRITY VERIFIED means the file has not been modified since it was uploaded. If anyone tampered with the file in S3, the hash would change and we would see INTEGRITY CHECK FAILED."

Point to the two hash values.

**Say:**
"SHA-256 is a one-way cryptographic hash function. The same input always produces the same 64-character output. Any change to the file — even one byte — produces a completely different hash."

---

## Step 6 — Report a Found Item and Show Matching (1 minute)

Click "Report Found Item". Fill in similar details:
- Item name: Black Wallet
- Category: Accessories
- Location: Library

Click Submit.

**Say:**
"The matching algorithm automatically runs when a new item is reported. It compares the found item against all active lost items using weighted token overlap."

Go to the Matches page.

**Say:**
"A match has been created with a score of [X]%. The algorithm gives 35% weight to item name, 25% to category, 25% to location, and 15% to description. Any match above 50% is saved and displayed."

---

## Step 7 — Mark as Recovered (30 seconds)

Go to the lost item detail page. Click "Mark Recovered".

**Say:**
"Only the owner of an item can edit, delete, or mark it as recovered. If another user tries to access the edit URL for someone else's item, they get a 403 Forbidden error."

---

## Step 8 — Show EC2 Deployment (1 minute)

Switch to your SSH terminal.

**Say:**
"This is our AWS EC2 instance — a t2.micro Ubuntu 22.04 virtual machine. This is IaaS — we have full control over the operating system."

Run:
```bash
sudo systemctl status lostfound
sudo systemctl status nginx
```

**Say:**
"Gunicorn runs as a systemd service — it starts automatically on boot and restarts if it crashes. Nginx sits in front as a reverse proxy. It serves static files directly and forwards dynamic requests to Gunicorn via a Unix socket. Port 5000 is never exposed publicly."

---

## Step 9 — Explain PaaS vs EC2 (30 seconds)

**Say:**
"We have two deployments. On Render — a PaaS platform — we just push code to GitHub and Render handles everything automatically. On EC2 — IaaS — we manually configured Ubuntu, Nginx, Gunicorn, and systemd. PaaS is faster to deploy. EC2 gives more control."

---

## Step 10 — Explain Security Summary (30 seconds)

**Say:**
"To summarize the security:
- Passwords: PBKDF2-SHA256 hashing — never stored in plain text
- S3: private bucket, AES256 encryption, presigned URLs expire in 15 minutes
- IAM: least privilege — only 3 S3 permissions on 1 bucket
- SHA-256: integrity verification detects any file tampering
- Credentials: all from environment variables — never in code or GitHub"

---

## Backup Questions to Prepare For

- "What happens if S3 is not configured?" → Local fallback, app still works
- "What is a presigned URL?" → Time-limited signed URL, credentials never in browser
- "Why not use Flask's built-in server?" → Single-threaded, not production-safe
- "What is the difference between PaaS and IaaS?" → Control vs convenience
- "How does SHA-256 detect tampering?" → Hash changes completely if file changes
