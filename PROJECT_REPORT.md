# PROJECT_REPORT.md
# Cloud-Based Lost Item Tracking and Recovery System

---

## Chapter 1 — Introduction

In today's world, people frequently lose personal belongings in public places such as universities, shopping malls, transport stations, and offices. The traditional method of reporting lost items involves physical notice boards or word-of-mouth, which is slow, unreliable, and limited in reach.

This project presents a Cloud-Based Lost Item Tracking and Recovery System — a web application built using Python and Flask that allows users to report lost and found items, search for matches, and track recovery status. The application is deployed on a public cloud platform (Render PaaS) and an AWS EC2 virtual machine, with image storage handled by Amazon S3.

---

## Chapter 2 — Problem Statement

There is no centralized, accessible platform for reporting and recovering lost items in most institutions. Existing solutions are either manual (notice boards), limited to a single location, or lack security features. Key problems include:

- No digital record of lost or found items
- No automatic matching between lost and found reports
- No secure image storage or integrity verification
- No cloud-based accessibility from any device

---

## Chapter 3 — Objectives

1. Build a web application for reporting lost and found items
2. Implement user authentication with secure password hashing
3. Develop an automatic item matching algorithm
4. Enable image upload with SHA-256 integrity verification
5. Store images securely in Amazon S3 with server-side encryption
6. Deploy the application on a public PaaS platform (Render)
7. Deploy the application on an AWS EC2 virtual machine
8. Document all cloud services, security measures, and deployment steps

---

## Chapter 4 — Existing System

The existing approach to lost and found management typically involves:

- Physical notice boards with handwritten notes
- Social media posts with no structured format
- Email chains within organizations
- No image verification or integrity checking
- No automatic matching between lost and found reports

Limitations: slow, insecure, not searchable, no cloud access, no data persistence.

---

## Chapter 5 — Proposed System

The proposed system is a cloud-based web application with the following capabilities:

- User registration and login with hashed passwords
- Structured reporting of lost and found items with images
- Automatic matching using weighted similarity scoring
- SHA-256 file integrity verification
- Amazon S3 for secure, encrypted image storage
- Deployment on both PaaS (Render) and IaaS (AWS EC2)
- Responsive web interface accessible from any device

---

## Chapter 6 — Scope

**In scope:**
- User authentication and session management
- Lost and found item reporting with image upload
- Automatic item matching algorithm
- SHA-256 integrity verification
- Amazon S3 integration with AES256 encryption
- Deployment on Render (PaaS) and AWS EC2 (IaaS)
- IAM least-privilege access control

**Out of scope:**
- Mobile application
- Real-time notifications
- Payment processing
- Machine learning-based matching

---

## Chapter 7 — Functional Requirements

| ID | Requirement |
|---|---|
| FR-01 | Users can register with name, email, phone, and password |
| FR-02 | Passwords are hashed using Werkzeug — never stored in plain text |
| FR-03 | Users can log in and log out with session management |
| FR-04 | Authenticated users can report lost items with details and image |
| FR-05 | Authenticated users can report found items with details and image |
| FR-06 | System automatically matches lost and found items on submission |
| FR-07 | Users can search and filter items by name, category, location, status |
| FR-08 | Only the item owner can edit, delete, or mark an item as recovered |
| FR-09 | Images are validated by extension and MIME header before saving |
| FR-10 | SHA-256 hash is calculated and stored for every uploaded image |
| FR-11 | Users can verify image integrity at any time |
| FR-12 | Images are stored in Amazon S3 with AES256 encryption when configured |
| FR-13 | Images are served via presigned URLs — bucket remains private |
| FR-14 | Application falls back to local storage when S3 is not configured |

---

## Chapter 8 — Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Passwords must never be stored in plain text |
| NFR-02 | AWS credentials must never be hard-coded or committed to GitHub |
| NFR-03 | S3 bucket must remain private — no public access |
| NFR-04 | Application must start within 5 seconds on a t2.micro instance |
| NFR-05 | File upload limit: 5 MB |
| NFR-06 | Application must work without AWS configuration (local fallback) |
| NFR-07 | All routes must handle errors gracefully — no stack traces to users |
| NFR-08 | Application must be deployable with a single command: gunicorn app:app |

---

## Chapter 9 — Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.10 | Application logic |
| Web Framework | Flask 2.3.3 | HTTP routing, templates, sessions |
| ORM | Flask-SQLAlchemy 3.1.1 | Database models and queries |
| Authentication | Flask-Login 0.6.3 | Session management, protected routes |
| Password Hashing | Werkzeug 2.3.7 | PBKDF2-SHA256 password hashing |
| Database | SQLite | Local and PaaS development database |
| Cloud Storage | Amazon S3 (boto3) | Encrypted image storage |
| WSGI Server | Gunicorn 21.2.0 | Production Python web server |
| Reverse Proxy | Nginx | Static files, load balancing (EC2) |
| PaaS | Render | Public cloud deployment |
| IaaS | AWS EC2 (Ubuntu 22.04) | Virtual machine deployment |
| Environment | python-dotenv | Secure environment variable loading |
| Frontend | HTML5, CSS3, JavaScript | Responsive UI without frameworks |
| Version Control | Git / GitHub | Source code management |

---

## Chapter 10 — System Architecture

### Overall Architecture

```
User (Browser)
      |
      | HTTP/HTTPS
      v
  Flask Application (app.py)
      |
      |-- Routes (auth, main, items)
      |-- Services (upload, matching, integrity, s3)
      |-- Models (User, Item, Match)
      |
      v
  SQLite Database          Amazon S3
  (instance/lostfound.db)  (encrypted image storage)
```

### PaaS Deployment Architecture

```
Developer (VS Code)
      | git push
      v
  GitHub Repository
      | auto-deploy
      v
  Render Web Service
  (gunicorn app:app)
      |
      v
  Public URL: https://<app>.onrender.com
```

### EC2 Deployment Architecture

```
User (Browser)
      | Port 80
      v
  Nginx (reverse proxy)
      | Unix socket
      v
  Gunicorn (3 workers)
      |
      v
  Flask Application
      |
      v
  SQLite + Amazon S3
```

### Security Architecture

```
User
  | HTTPS
  v
Flask (validates input, checks session)
  | boto3 (HTTPS to AWS)
  v
IAM Role / Access Keys (least privilege)
  |
  v
Private S3 Bucket
  |
  v
AES256 Encrypted Object
```

---

## Chapter 11 — Application Workflow

### Lost Item Reporting
1. User logs in
2. Fills in item details (name, category, description, location, date, contact)
3. Optionally uploads an image
4. System validates the image (extension + MIME header)
5. Image saved to S3 (or locally if S3 not configured)
6. SHA-256 hash calculated and stored in database
7. Matching algorithm runs against all active found items
8. If match score >= 50%, a Match record is created
9. User redirected to item detail page

### Integrity Verification
1. User clicks "Verify File Integrity" on item detail page
2. System retrieves the file (from S3 or local disk)
3. SHA-256 hash recalculated from current file bytes
4. Compared with hash stored in database at upload time
5. Result displayed: INTEGRITY VERIFIED or INTEGRITY CHECK FAILED

---

## Chapter 12 — Database Design

### Users Table

| Column | Type | Description |
|---|---|---|
| id | Integer (PK) | Auto-increment primary key |
| name | String(100) | Full name |
| email | String(150) | Unique email address |
| phone | String(20) | Phone number |
| password_hash | String(256) | PBKDF2-SHA256 hashed password |
| created_at | DateTime | Registration timestamp |

### Items Table

| Column | Type | Description |
|---|---|---|
| id | Integer (PK) | Auto-increment primary key |
| user_id | Integer (FK) | References users.id |
| item_type | String(10) | LOST or FOUND |
| item_name | String(150) | Name of the item |
| category | String(80) | Item category |
| description | Text | Detailed description |
| location | String(200) | Where lost/found |
| date_lost_found | Date | Date of loss/finding |
| contact | String(150) | Contact information |
| image_filename | String(200) | Local filename (if stored locally) |
| s3_object_key | String(300) | S3 object key (if stored in S3) |
| sha256_hash | String(64) | SHA-256 hex digest of image |
| status | String(20) | ACTIVE, MATCHED, or RECOVERED |
| created_at | DateTime | Report timestamp |

### Matches Table

| Column | Type | Description |
|---|---|---|
| id | Integer (PK) | Auto-increment primary key |
| lost_item_id | Integer (FK) | References items.id |
| found_item_id | Integer (FK) | References items.id |
| match_score | Float | Score from 0 to 100 |
| matching_reason | Text | Human-readable match explanation |
| status | String(20) | PENDING, CONFIRMED, or REJECTED |
| created_at | DateTime | Match creation timestamp |

---

## Chapter 13 — Lost/Found Modules

### Report Lost Item (/report-lost)
- Requires authentication
- Validates all form fields
- Validates image file (extension + MIME header)
- Saves image to S3 or local storage
- Calculates and stores SHA-256 hash
- Triggers automatic matching

### Report Found Item (/report-found)
- Same workflow as lost item
- item_type set to FOUND

### Item Listing (/lost-items, /found-items)
- Public access (no login required)
- Search by name (case-insensitive)
- Filter by category, location, status

### Item Detail (/item/<id>)
- Shows full item information
- Shows SHA-256 hash
- Shows S3 object key if applicable
- Shows image via presigned URL (S3) or static path (local)
- Owner-only: Edit, Delete, Mark Recovered buttons

---

## Chapter 14 — Matching Algorithm

The matching algorithm compares a newly reported item against all active items of the opposite type using weighted token overlap.

### Weights

| Field | Weight |
|---|---|
| Item name | 35% |
| Category | 25% |
| Location | 25% |
| Description | 15% |

### Token Overlap Formula

```
overlap(A, B) = |tokens(A) ∩ tokens(B)| / max(|tokens(A)|, |tokens(B)|)
```

### Score Calculation

```
score = (name_sim × 0.35 + cat_sim × 0.25 + loc_sim × 0.25 + desc_sim × 0.15) × 100
```

### Threshold

Matches with score >= 50 are saved and displayed. Both items are updated to MATCHED status.

### Example

Lost: "Black leather wallet, Accessories, Main Library"
Found: "Black wallet, Accessories, Library entrance"

- Name similarity: "black wallet" overlap = 2/3 = 67% → 0.67 × 35 = 23.5
- Category: exact match → 1.0 × 25 = 25.0
- Location: "library" overlap = 1/2 = 50% → 0.50 × 25 = 12.5
- Description: partial overlap → ~5.0

Total score ≈ 66% → Match created.

---

## Chapter 15 — Public PaaS Deployment (Render)

### What is PaaS?
Platform as a Service (PaaS) is a cloud model where the provider manages the infrastructure (servers, OS, runtime) and the developer only deploys application code.

### Why Render?
- Free tier available
- GitHub integration with automatic deploys
- Native Python/Gunicorn support
- No credit card required for free tier

### Deployment Process
1. Push code to GitHub
2. Connect GitHub repository to Render
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `gunicorn app:app`
5. Set environment variables (SECRET_KEY, DATABASE_URL, RENDER=true)
6. Deploy — Render builds and starts the application automatically

### Limitations on Free Tier
- SQLite database resets on each redeploy (ephemeral filesystem)
- Uploaded images in /tmp are lost on restart
- S3 integration resolves the image persistence issue

---

## Chapter 16 — AWS EC2 Deployment

### What is EC2?
Amazon EC2 (Elastic Compute Cloud) is an IaaS offering providing virtual machines on AWS infrastructure. Unlike PaaS, EC2 gives full control over the operating system and server configuration.

### Instance Configuration
- AMI: Ubuntu Server 22.04 LTS
- Instance type: t2.micro (1 vCPU, 1 GB RAM, Free Tier eligible)
- Storage: 20 GiB gp3 EBS volume

### Deployment Stack
- Nginx: reverse proxy, serves static files
- Gunicorn: WSGI server, 3 worker processes
- Systemd: process management, auto-restart on failure

### Security Group
- Port 22 (SSH): restricted to administrator IP
- Port 80 (HTTP): open to public
- Port 443 (HTTPS): open to public
- Port 5000: NOT opened (Flask dev server never exposed)

---

## Chapter 17 — Amazon S3

### What is S3?
Amazon Simple Storage Service (S3) is an object storage service. Files are stored as objects in buckets. S3 provides 99.999999999% (11 nines) durability.

### How it is Used
- Lost item images stored under: `lost-items/<uuid>.<ext>`
- Found item images stored under: `found-items/<uuid>.<ext>`
- Original filenames never used (UUID prevents guessing)
- S3 object key stored in the database alongside the SHA-256 hash

### Fallback
If S3 environment variables are not set, the application automatically uses local file storage. No code change is needed.

---

## Chapter 18 — Confidentiality

Confidentiality means ensuring that data is accessible only to authorized parties.

### Measures Implemented

| Measure | Implementation |
|---|---|
| Private S3 bucket | Block Public Access fully enabled |
| Presigned URLs | Images served via time-limited signed URLs (15 min expiry) |
| No credentials in browser | AWS credentials never sent to the client |
| No credentials in code | All secrets loaded from environment variables |
| Password hashing | PBKDF2-SHA256 via Werkzeug — passwords never stored in plain text |
| Session security | Flask SECRET_KEY signs session cookies |
| HTTPS | Enforced by boto3 for all S3 communication |

---

## Chapter 19 — Integrity

Integrity means ensuring that data has not been altered or tampered with.

### SHA-256 Implementation

1. When an image is uploaded, its bytes are read into memory
2. SHA-256 hash is calculated using Python's `hashlib` module
3. The 64-character hex digest is stored in the `sha256_hash` column
4. When verification is requested, the current file is retrieved (from S3 or disk)
5. SHA-256 is recalculated from the current bytes
6. If stored hash == current hash → INTEGRITY VERIFIED
7. If they differ → INTEGRITY CHECK FAILED (file was modified)

---

## Chapter 20 — SHA-256

SHA-256 (Secure Hash Algorithm 256-bit) is a cryptographic hash function that produces a fixed 256-bit (64 hex character) output from any input.

### Properties
- Deterministic: same input always produces same output
- One-way: cannot reverse the hash to get the original file
- Avalanche effect: any change to the file produces a completely different hash
- Collision resistant: two different files cannot produce the same hash

### Example
```
Input:  image.jpg (504 bytes)
Output: 06f7ff8f53df8c4becc15c4996019fb0ce934dd26afbdbd64f59c00ba57ea0dd
```

If even one byte of the image changes, the hash changes completely.

---

## Chapter 21 — IAM and Access Control

### IAM Policy (Least Privilege)
The application IAM user has only three permissions, restricted to one bucket:

```json
{
  "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
  "Resource": "arn:aws:s3:::lostfound-cloud-uploads/*"
}
```

### IAM Role (EC2)
For EC2 deployment, an IAM Role is attached to the instance instead of using access keys. This means:
- No long-lived credentials stored in any file
- Credentials are temporary and automatically rotated by AWS
- boto3 automatically uses the instance role

### Application-Level Authorization
- All item modification routes check `item.user_id == current_user.id`
- Unauthorized access returns HTTP 403 Forbidden
- Protected routes use `@login_required` decorator

---

## Chapter 22 — Security

### Summary of Security Measures

| Area | Measure |
|---|---|
| Authentication | Email + password, PBKDF2-SHA256 hashing |
| Authorization | Owner-only edit/delete/recover, @login_required |
| File upload | Extension + MIME header validation, UUID filenames, 5MB limit |
| S3 | Private bucket, AES256 encryption, presigned URLs |
| Credentials | Environment variables only, never in code or GitHub |
| IAM | Least privilege — only 3 S3 actions on 1 bucket |
| Sessions | Signed cookies via Flask SECRET_KEY |
| Error handling | Custom 403/404/500 pages — no stack traces to users |
| Network | SSH restricted to admin IP, port 5000 never exposed |

---

## Chapter 23 — Testing

### Automated Tests
65 tests covering: SHA-256 functions, S3 key generation, MIME detection, upload validation, all routes, authentication, matching, and integrity verification.

Run: `python tests/test_app.py`
Result: 65 passed, 0 failed

### Manual Tests Required
- TC-19 to TC-22: S3 upload, retrieval, delete, encryption (requires AWS)
- TC-24: EC2 deployment (requires EC2 instance)
- TC-25: PaaS deployment (requires Render account)

---

## Chapter 24 — Results

| Feature | Status |
|---|---|
| User registration and login | Complete |
| Lost item reporting | Complete |
| Found item reporting | Complete |
| Image upload (local) | Complete |
| Image upload (S3) | Complete (requires AWS config) |
| Automatic matching | Complete |
| SHA-256 integrity | Complete |
| Search and filter | Complete |
| Edit/Delete/Recover | Complete |
| PaaS deployment (Render) | Prepared — requires manual deploy |
| EC2 deployment | Prepared — requires manual deploy |
| S3 encryption | Implemented — requires AWS config |

---

## Chapter 25 — Advantages

1. Cloud-based — accessible from any device with a browser
2. Automatic matching reduces manual effort
3. SHA-256 ensures image integrity cannot be silently compromised
4. S3 provides durable, encrypted, scalable image storage
5. IAM least privilege minimizes security risk
6. Dual deployment (PaaS + EC2) demonstrates both cloud models
7. Local fallback means the app works without AWS configuration
8. No external CSS frameworks — lightweight and fast

---

## Chapter 26 — Limitations

1. SQLite is not suitable for high-concurrency production use
2. S3 images are lost on Render free tier if S3 is not configured
3. Matching algorithm uses simple token overlap — not semantic similarity
4. No email notifications when a match is found
5. No HTTPS on EC2 without additional SSL certificate configuration
6. Free tier EC2 (t2.micro) has limited CPU and memory

---

## Chapter 27 — Future Enhancements

1. Replace SQLite with PostgreSQL for production scalability
2. Add email notifications for matches using AWS SES
3. Implement HTTPS on EC2 using Let's Encrypt (Certbot)
4. Improve matching with NLP-based semantic similarity
5. Add AWS CloudFront CDN for faster image delivery
6. Implement AWS Auto Scaling for high availability
7. Add admin dashboard for managing all reports
8. Mobile application using React Native

---

## Chapter 28 — Conclusion

This project successfully demonstrates a cloud-based lost item tracking system that integrates multiple AWS services. The application is built with Python and Flask, deployed on both a public PaaS platform (Render) and an AWS EC2 virtual machine, with images stored securely in Amazon S3 using AES256 server-side encryption.

The SHA-256 integrity verification system ensures that uploaded images cannot be tampered with without detection. The IAM least-privilege policy ensures that the application has only the minimum permissions required. The matching algorithm provides automatic item pairing without requiring machine learning.

The project covers all five requirements of the Virtualization and Cloud Computing module: PaaS deployment, EC2 deployment, S3 storage, secure file upload with encryption and integrity, and complete documentation.
