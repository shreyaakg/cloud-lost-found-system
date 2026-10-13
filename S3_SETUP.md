# AWS S3 Setup Guide

## Overview

This guide covers the manual AWS steps required to enable S3 image storage for the
Lost and Found Cloud application. The application works fully without S3 (local fallback).
S3 is activated by setting four environment variables — no code changes are needed.

---

## Storage Architecture

```
Without S3 (local fallback):
  Upload → static/uploads/<uuid>.jpg  →  SHA-256 stored in DB
  Image served via: /static/uploads/<uuid>.jpg

With S3 configured:
  Upload → S3 bucket (lost-items/<uuid>.jpg or found-items/<uuid>.jpg)
         → AES256 server-side encryption applied automatically
         → SHA-256 stored in DB
         → S3 object key stored in DB
  Image served via: presigned URL (15-minute expiry, private bucket)

Integrity verification:
  Local: read file from disk → SHA-256 → compare with DB
  S3:    download object from S3 → SHA-256 → compare with DB
```

---

## Step 1 — Sign In to AWS Console

1. Go to https://console.aws.amazon.com
2. Sign in with your AWS account.
3. In the top-right region selector, choose the region closest to you.
   Recommended for this project: **ap-southeast-1** (Singapore).

---

## Step 2 — Create the S3 Bucket

1. In the search bar, type **S3** and click the S3 service.
2. Click **Create bucket**.
3. Fill in:

   | Setting | Value |
   |---|---|
   | Bucket name | `lostfound-cloud-uploads` (must be globally unique — add your name/date if needed) |
   | AWS Region | ap-southeast-1 (or your chosen region) |
   | Object Ownership | ACLs disabled (recommended) |
   | Block Public Access | **Keep ALL four checkboxes ticked** (bucket stays private) |
   | Bucket Versioning | Enable (optional but recommended — allows recovery of overwritten files) |
   | Default encryption | Server-side encryption with Amazon S3 managed keys (SSE-S3) |
   | Encryption key type | Amazon S3 managed key (SSE-S3) |

4. Click **Create bucket**.

> The application also applies `ServerSideEncryption='AES256'` on every upload via the
> boto3 `put_object` call, so encryption is enforced at the application level as well.

---

## Step 3 — Create an IAM User with Least-Privilege Permissions

The application only needs three S3 permissions, restricted to your specific bucket.
Never use root account credentials or AdministratorAccess.

### 3a — Create an IAM Policy

1. Go to **IAM** → **Policies** → **Create policy**.
2. Click the **JSON** tab and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LostFoundS3Access",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::lostfound-cloud-uploads/*"
    },
    {
      "Sid": "LostFoundS3ListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::lostfound-cloud-uploads"
    }
  ]
}
```

   Replace `lostfound-cloud-uploads` with your actual bucket name.

3. Click **Next**, name the policy: `LostFoundS3Policy`.
4. Click **Create policy**.

### 3b — Create an IAM User

1. Go to **IAM** → **Users** → **Create user**.
2. Username: `lostfound-app-user`
3. Select **Attach policies directly**.
4. Search for and select `LostFoundS3Policy`.
5. Click **Create user**.

### 3c — Create Access Keys

1. Click on the user `lostfound-app-user`.
2. Go to the **Security credentials** tab.
3. Under **Access keys**, click **Create access key**.
4. Use case: **Application running outside AWS**.
5. Click **Create access key**.
6. **Copy both values immediately** — the secret key is shown only once:
   - Access key ID: `AKIA...`
   - Secret access key: `...`
7. Store them securely (e.g. a password manager). Never commit them to Git.

### IAM Role Note (for EC2 — Part 2)

When deploying to EC2, use an **IAM Role** instead of access keys:
- Create a role with the `LostFoundS3Policy` attached.
- Assign the role to the EC2 instance.
- Remove `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from the environment.
- boto3 automatically uses the instance role — no credentials in code or env vars.

---

## Step 4 — Configure Environment Variables

### Local development (.env file)

```
AWS_ACCESS_KEY_ID=AKIA...your-key...
AWS_SECRET_ACCESS_KEY=...your-secret...
AWS_REGION=ap-southeast-1
S3_BUCKET_NAME=lostfound-cloud-uploads
```

### On Render (dashboard → Environment)

Add these four variables in the Render web service environment panel:

| Key | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Your access key ID |
| `AWS_SECRET_ACCESS_KEY` | Your secret access key |
| `AWS_REGION` | `ap-southeast-1` |
| `S3_BUCKET_NAME` | `lostfound-cloud-uploads` |

---

## Step 5 — Start the Application

```bash
python app.py
```

On startup you will see in the console:

- If S3 is configured correctly: no warning, uploads go to S3.
- If S3 is not configured: `INFO - S3 not configured — using local file storage fallback.`

---

## Step 6 — Test Image Upload to S3

1. Register and log in.
2. Go to **Report Lost Item**.
3. Fill in all fields and attach a JPG image.
4. Submit the form.
5. You should be redirected to the item detail page showing:
   - The image (loaded via presigned URL)
   - `☁️ Stored in AWS S3`
   - The S3 object key (e.g. `lost-items/3f8a1c2d...jpg`)
   - The SHA-256 hash

---

## Step 7 — Verify the Object in the AWS Console

1. Go to **S3** → your bucket → **Objects**.
2. You should see a folder `lost-items/` or `found-items/`.
3. Click into it — you will see the uploaded file with a UUID filename.
4. Click the object → **Properties** tab.
   - Confirm **Server-side encryption**: Amazon S3 managed key (SSE-S3).
5. The object has **no public URL** — it is private.

---

## Step 8 — Test Image Access via Presigned URL

1. On the item detail page, right-click the image → **Copy image address**.
2. The URL will look like:
   ```
   https://lostfound-cloud-uploads.s3.ap-southeast-1.amazonaws.com/lost-items/abc123.jpg
   ?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Expires=900...
   ```
3. This URL expires in 15 minutes. After expiry, the image is no longer accessible
   via that URL — the user must reload the page to get a fresh presigned URL.
4. AWS credentials are never exposed in the URL — only a temporary signed token.

---

## Step 9 — Test SHA-256 Integrity Verification

1. On the item detail page, click **Verify File Integrity (SHA-256)**.
2. The application:
   - Downloads the object from S3.
   - Calculates its SHA-256 hash.
   - Compares it with the hash stored in the database at upload time.
3. Expected result: **INTEGRITY VERIFIED** ✅
4. The page shows:
   - Storage location (S3 object key)
   - Stored hash (from DB)
   - Current hash (recalculated from S3 object)
   - Match confirmation

---

## Step 10 — Test Delete

1. On the item detail page, click **Delete**.
2. Confirm the deletion.
3. The application calls `s3.delete_object()` to remove the file from S3.
4. Go back to the S3 console and refresh — the object should be gone.

---

## Step 11 — Test Error Handling

### Invalid credentials
Set `AWS_ACCESS_KEY_ID=INVALID` in `.env`, restart, try to upload.
Expected: flash message "AWS credentials are missing or invalid." — app does not crash.

### Wrong bucket name
Set `S3_BUCKET_NAME=nonexistent-bucket-xyz`, restart, try to upload.
Expected: flash message "S3 bucket not found." — app does not crash.

### Missing S3 object (integrity check)
Manually delete an object from the S3 console, then click Verify on that item.
Expected: "S3 RETRIEVAL FAILED" with an error message.

---

## Security Summary (for viva)

| Concern | How it is addressed |
|---|---|
| Credentials in code | Never — all from environment variables |
| Public bucket | Blocked — all four Block Public Access settings enabled |
| Encryption at rest | AES256 SSE-S3 applied on every PutObject call |
| Encryption in transit | HTTPS enforced by boto3 by default |
| Image access | Presigned URLs only — expire in 15 minutes |
| Credentials in browser | Never — presigned URL contains only a signed token |
| IAM least privilege | Only s3:PutObject, s3:GetObject, s3:DeleteObject on one bucket |
| File type validation | Extension + MIME header byte check before any upload |
| Filename safety | UUID filenames — original filename never used |
| File size limit | 5 MB enforced by Flask MAX_CONTENT_LENGTH |
| Integrity | SHA-256 calculated before upload, stored in DB, verified on demand |

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `InvalidAccessKeyId` | Wrong AWS_ACCESS_KEY_ID | Check the key in IAM |
| `SignatureDoesNotMatch` | Wrong AWS_SECRET_ACCESS_KEY | Regenerate access key |
| `NoSuchBucket` | Wrong S3_BUCKET_NAME | Check bucket name spelling |
| `AccessDenied` | IAM policy missing or wrong bucket ARN | Re-check the policy JSON |
| `NoSuchKey` on verify | Object was deleted from S3 | Re-upload the image |
| Image not showing | Presigned URL expired | Reload the page |
| Local fallback used | S3 env vars not set | Set all four env vars |
