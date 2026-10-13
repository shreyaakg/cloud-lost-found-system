# REQUIREMENT_MAPPING.md
# 40-Mark Requirement Evidence Map

---

## Requirement 1 — Public PaaS Deployment (8 marks)

**Platform:** Render (render.com)
**Marks:** 8

### What was implemented
- Flask application prepared for Render with `Procfile` and `render.yaml`
- `gunicorn app:app` confirmed as the correct start command
- `config.py` detects `RENDER=true` environment variable and uses `/tmp/uploads`
- All environment variables documented in `.env.example`
- `PAAS_DEPLOYMENT.md` provides step-by-step deployment instructions

### Evidence to show
| Evidence | File/Location |
|---|---|
| Procfile with start command | `Procfile` |
| Render infrastructure config | `render.yaml` |
| Deployment guide | `PAAS_DEPLOYMENT.md` |
| Screenshot: Render Live status | SS-36 |
| Screenshot: Build logs | SS-34, SS-35 |
| Screenshot: App running on Render URL | SS-38, SS-39, SS-40 |
| Screenshot: Environment variables panel | SS-37 |

### Viva talking points
- PaaS means the provider manages servers, OS, and runtime
- We only push code to GitHub; Render handles the rest
- Build command installs dependencies; start command launches Gunicorn
- SQLite resets on redeploy (ephemeral) — acceptable for demonstration
- S3 resolves image persistence on PaaS

---

## Requirement 2 — Amazon EC2 (8 marks)

**Service:** AWS EC2 (t2.micro, Ubuntu 22.04)
**Marks:** 8

### What was implemented
- `EC2_DEPLOYMENT.md` — complete step-by-step guide
- `gunicorn.conf.py` — production Gunicorn configuration (Unix socket, workers, logging)
- `nginx.conf.example` — Nginx reverse proxy configuration
- `lostfound.service.example` — systemd service for auto-start and auto-restart
- Security Group documented: ports 22 (SSH, My IP), 80 (HTTP), 443 (HTTPS)
- Port 5000 explicitly NOT opened

### Evidence to show
| Evidence | File/Location |
|---|---|
| Deployment guide | `EC2_DEPLOYMENT.md` |
| Gunicorn config | `gunicorn.conf.py` |
| Nginx config | `nginx.conf.example` |
| Systemd service | `lostfound.service.example` |
| Screenshot: EC2 instance running | SS-46, SS-47 |
| Screenshot: Security Group rules | SS-48 |
| Screenshot: SSH terminal | SS-49 |
| Screenshot: systemctl status | SS-53, SS-54 |
| Screenshot: App on EC2 URL | SS-55, SS-56, SS-57 |

### Viva talking points
- EC2 is IaaS — we control the OS and all software
- Nginx serves static files directly (faster), proxies dynamic requests to Gunicorn
- Gunicorn runs 3 workers (2×CPU+1) for concurrent request handling
- Systemd ensures Gunicorn restarts automatically if it crashes
- SSH key pair uses asymmetric encryption — more secure than passwords

---

## Requirement 3 — Amazon S3 (8 marks)

**Service:** Amazon S3
**Marks:** 8

### What was implemented
- `services/s3_service.py` — complete S3 service with upload, download, delete, presigned URL, connection check
- Object keys: `lost-items/<uuid>.<ext>` and `found-items/<uuid>.<ext>`
- `Item` model stores `s3_object_key` and `sha256_hash`
- Local fallback when S3 not configured
- `S3_SETUP.md` — manual AWS setup guide

### Evidence to show
| Evidence | File/Location |
|---|---|
| S3 service implementation | `services/s3_service.py` |
| Object key builder | `build_object_key()` in s3_service.py |
| Database field | `s3_object_key` in `models/item.py` |
| Setup guide | `S3_SETUP.md` |
| Screenshot: S3 bucket | SS-60 |
| Screenshot: Objects in bucket | SS-63, SS-65 |
| Screenshot: App showing S3 badge | SS-66 |
| Screenshot: Presigned URL in browser | SS-67 |
| Screenshot: Object deleted | SS-68 |

### Viva talking points
- S3 stores objects (files) in buckets — not a file system
- UUID filenames prevent guessing and path traversal
- Bucket is private — no public URLs
- Presigned URLs give temporary access without exposing credentials
- boto3 is the AWS SDK for Python

---

## Requirement 4 — Secure File Upload (Encryption + IAM + SHA-256) (8 marks)

**Services:** S3 SSE-AES256, IAM, SHA-256 (hashlib)
**Marks:** 8

### What was implemented

**Confidentiality:**
- S3 bucket: Block Public Access fully enabled
- `ServerSideEncryption='AES256'` on every `put_object` call
- Presigned URLs (15-minute expiry) — credentials never in browser
- HTTPS enforced by boto3

**File Security:**
- Extension validation: only jpg, jpeg, png, webp
- MIME header byte check (not just extension)
- 5MB file size limit (Flask `MAX_CONTENT_LENGTH`)
- UUID filenames via `secure_filename()`

**IAM Least Privilege:**
- Policy: only `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on one bucket
- IAM Role recommended for EC2 (no long-lived credentials)

**Integrity (SHA-256):**
- Hash calculated from file bytes before upload
- Stored in `item.sha256_hash` (64-char hex)
- Verification: retrieve file → recalculate → compare → VERIFIED or FAILED

### Evidence to show
| Evidence | File/Location |
|---|---|
| AES256 in upload | `upload_file()` in s3_service.py line with ServerSideEncryption |
| MIME validation | `_detect_mime()` in services/upload.py |
| SHA-256 implementation | `services/integrity.py` |
| IAM policy JSON | `S3_SETUP.md` Step 3 |
| Screenshot: S3 encryption property | SS-62, SS-64 |
| Screenshot: IAM policy | SS-69 |
| Screenshot: INTEGRITY VERIFIED | SS-72, SS-73 |
| Screenshot: Block Public Access | SS-61 |

### Viva talking points
- AES256 is symmetric encryption — same key encrypts and decrypts
- SSE-S3 means AWS manages the encryption keys
- SHA-256 is a one-way hash — cannot reverse it to get the original file
- Any change to the file produces a completely different hash (avalanche effect)
- Least privilege: if credentials are compromised, damage is limited to S3 only

---

## Requirement 5 — Documentation, Presentation, Viva (8 marks)

**Marks:** 8

### What was created
| Document | File |
|---|---|
| Project report (28 chapters) | `PROJECT_REPORT.md` |
| Test cases (25 test cases) | `TESTING.md` |
| Screenshot checklist (74 items) | `SCREENSHOT_CHECKLIST.md` |
| Presentation content (12 slides) | `PRESENTATION_CONTENT.md` |
| Viva questions and answers (35 Q&A) | `VIVA_QUESTIONS.md` |
| Requirement mapping | `REQUIREMENT_MAPPING.md` |
| Demo script | `DEMO_SCRIPT.md` |
| PaaS deployment guide | `PAAS_DEPLOYMENT.md` |
| EC2 deployment guide | `EC2_DEPLOYMENT.md` |
| S3 setup guide | `S3_SETUP.md` |
| README | `README.md` |

### Evidence to show
- All documentation files present in repository
- 65 automated tests passing
- Complete architecture diagrams in PROJECT_REPORT.md
- All viva questions answered in VIVA_QUESTIONS.md

---

## Total Mark Summary

| Requirement | Topic | Marks |
|---|---|---|
| 1 | PaaS — Render deployment | 8 |
| 2 | EC2 — Instance + deployment + access | 8 |
| 3 | S3 — Bucket + object management | 8 |
| 4 | Secure upload — encryption + IAM + SHA-256 | 8 |
| 5 | Documentation + presentation + viva | 8 |
| **Total** | | **40** |
