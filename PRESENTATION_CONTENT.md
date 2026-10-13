# PRESENTATION_CONTENT.md
# Slide content for viva/presentation

---

## Slide 1 — Title

**Cloud-Based Lost Item Tracking and Recovery System**

Student: [Your Name]
Course: Virtualization and Cloud Computing
Year: 2024

Technologies: Python | Flask | AWS EC2 | Amazon S3 | Render PaaS

---

## Slide 2 — Problem Statement

**The Problem**

- People lose belongings every day in public places
- No centralized digital platform to report or search
- Manual notice boards are slow and unreliable
- No automatic matching between lost and found reports
- No secure image storage or integrity verification

**Impact**
Lost items are rarely recovered due to lack of a proper system.

---

## Slide 3 — Objectives

1. Build a web application for reporting lost and found items
2. Implement automatic item matching algorithm
3. Enable secure image upload with SHA-256 integrity verification
4. Store images in Amazon S3 with AES256 encryption
5. Deploy on public PaaS (Render) — Requirement 1
6. Deploy on AWS EC2 virtual machine — Requirement 2
7. Implement S3 bucket and object management — Requirement 3
8. Implement secure upload with encryption and IAM — Requirement 4

---

## Slide 4 — Proposed System

**Cloud-Based Solution**

- User registers and logs in securely
- Reports lost or found items with image
- System automatically matches items using weighted scoring
- Images stored in private S3 bucket with AES256 encryption
- SHA-256 hash verifies image has not been tampered with
- Deployed on both PaaS and EC2 for cloud coverage

**Key Benefit:** Accessible from any device, anywhere, anytime.

---

## Slide 5 — System Architecture

```
User (Browser)
      |
   Nginx (EC2) / Render (PaaS)
      |
   Gunicorn + Flask
      |
   SQLite Database
      |
   Amazon S3 (encrypted images)
```

**Two Deployments:**
- Render PaaS: https://<app>.onrender.com
- AWS EC2: http://<EC2_PUBLIC_IP>

---

## Slide 6 — Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10 |
| Framework | Flask 2.3.3 |
| Database | SQLite + SQLAlchemy |
| Authentication | Flask-Login + Werkzeug |
| Cloud Storage | Amazon S3 (boto3) |
| WSGI Server | Gunicorn |
| Reverse Proxy | Nginx (EC2) |
| PaaS | Render |
| IaaS | AWS EC2 (Ubuntu 22.04) |
| Version Control | Git + GitHub |

---

## Slide 7 — Application Features

**Authentication**
- Register, Login, Logout with hashed passwords

**Item Management**
- Report Lost / Found items with image upload
- Edit, Delete, Mark Recovered (owner only)

**Search and Matching**
- Filter by name, category, location, status
- Automatic matching with weighted score

**Security**
- SHA-256 integrity verification
- S3 AES256 encryption
- Presigned URLs for private image access

---

## Slide 8 — Public PaaS Deployment (Render)

**What is PaaS?**
Provider manages infrastructure. Developer only deploys code.

**Deployment Steps:**
1. Push code to GitHub
2. Connect GitHub to Render
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `gunicorn app:app`
5. Set environment variables
6. Deploy automatically

**Live URL:** https://<app>.onrender.com

[Screenshot: Render dashboard showing Live status]

---

## Slide 9 — AWS EC2 Deployment

**What is EC2?**
IaaS — full virtual machine on AWS. Full OS control.

**Setup:**
- Ubuntu 22.04 LTS, t2.micro (Free Tier)
- Nginx → Gunicorn → Flask
- Systemd for auto-restart

**Security Group:**
- Port 22: SSH (admin only)
- Port 80: HTTP (public)
- Port 5000: NOT opened

**Live URL:** http://<EC2_PUBLIC_IP>

[Screenshot: EC2 instance running + browser showing app]

---

## Slide 10 — Amazon S3

**What is S3?**
Object storage service. 11 nines durability. Scalable.

**How we use it:**
- Images stored as: `lost-items/<uuid>.jpg`
- Bucket is PRIVATE — no public access
- AES256 server-side encryption on every upload
- Images served via presigned URLs (15-minute expiry)
- SHA-256 hash stored in database for integrity

**IAM Policy (Least Privilege):**
Only s3:PutObject, s3:GetObject, s3:DeleteObject on one bucket.

[Screenshot: S3 bucket with objects + encryption property]

---

## Slide 11 — Security: Encryption + SHA-256

**Confidentiality (S3)**
- Private bucket — Block Public Access enabled
- AES256 encryption at rest
- HTTPS in transit (boto3 default)
- Presigned URLs — credentials never in browser

**Integrity (SHA-256)**
```
Upload:  File → SHA-256 → Store hash in DB
Verify:  Retrieve file → SHA-256 → Compare with DB
Result:  INTEGRITY VERIFIED  or  INTEGRITY CHECK FAILED
```

SHA-256 is a one-way cryptographic hash.
Any change to the file produces a completely different hash.

[Screenshot: INTEGRITY VERIFIED page]

---

## Slide 12 — Results and Conclusion

**Results**
- 65 automated tests: 65 passed, 0 failed
- All core features implemented and verified locally
- PaaS deployment prepared and documented
- EC2 deployment prepared and documented
- S3 integration with encryption implemented

**Conclusion**
The system demonstrates practical use of cloud computing:
- PaaS for rapid deployment
- IaaS for full control
- S3 for scalable encrypted storage
- IAM for least-privilege access
- SHA-256 for data integrity

**All 5 requirements of the VCC module are addressed.**
