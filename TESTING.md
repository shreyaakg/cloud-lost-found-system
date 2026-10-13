# TESTING.md — Test Cases for Lost and Found Cloud System

## Test Environment
- Python 3.10, Flask 2.3.3, SQLite (local)
- AWS S3: tests TC-19 to TC-22 require manual AWS configuration
- EC2/PaaS: tests TC-24 and TC-25 require manual deployment

## Status Key
- PASS — verified by automated test suite (tests/test_app.py)
- PASS (manual) — verified by manual browser testing
- PENDING — requires AWS resources to be manually configured first

---

## TC-01 — User Registration

| Field | Value |
|---|---|
| Test ID | TC-01 |
| Description | Register a new user with valid details |
| Input | Name: Alice Smith, Email: alice@test.com, Phone: 9876543210, Password: secret123 |
| Expected | User created, redirected to login, success flash message shown |
| Actual | User created, redirected to login page, "Registration successful" message shown |
| Status | PASS |

---

## TC-02 — Duplicate Registration

| Field | Value |
|---|---|
| Test ID | TC-02 |
| Description | Attempt to register with an already-used email |
| Input | Email: alice@test.com (already registered) |
| Expected | Registration rejected, "Email already registered" error shown |
| Actual | Error message "Email already registered" displayed, no duplicate created |
| Status | PASS |

---

## TC-03 — Valid Login

| Field | Value |
|---|---|
| Test ID | TC-03 |
| Description | Login with correct credentials |
| Input | Email: alice@test.com, Password: secret123 |
| Expected | Login succeeds, redirected to dashboard |
| Actual | Login succeeds, dashboard shown with user's name |
| Status | PASS |

---

## TC-04 — Invalid Login

| Field | Value |
|---|---|
| Test ID | TC-04 |
| Description | Login with wrong password |
| Input | Email: alice@test.com, Password: wrongpass |
| Expected | Login rejected, "Invalid email or password" shown |
| Actual | Error message shown, user stays on login page |
| Status | PASS |

---

## TC-05 — Logout

| Field | Value |
|---|---|
| Test ID | TC-05 |
| Description | Logged-in user clicks logout |
| Input | Authenticated session |
| Expected | Session cleared, redirected to login, "You have been logged out" shown |
| Actual | Session cleared, redirected to login page with info message |
| Status | PASS |

---

## TC-06 — Dashboard Access

| Field | Value |
|---|---|
| Test ID | TC-06 |
| Description | Authenticated user accesses dashboard |
| Input | Valid session |
| Expected | Dashboard shows total lost, found, active, matched, recovered counts |
| Actual | Dashboard renders with all five statistics |
| Status | PASS |

---

## TC-07 — Report Lost Item (no image)

| Field | Value |
|---|---|
| Test ID | TC-07 |
| Description | Submit a lost item report without an image |
| Input | Item name: Black Wallet, Category: Accessories, Description, Location, Date, Contact |
| Expected | Item saved, redirected to item detail page |
| Actual | Item saved with status ACTIVE, detail page shown |
| Status | PASS |

---

## TC-08 — Report Found Item (no image)

| Field | Value |
|---|---|
| Test ID | TC-08 |
| Description | Submit a found item report without an image |
| Input | Item name: Black Wallet, Category: Accessories, Location: Main Library |
| Expected | Item saved, automatic match triggered against existing lost item |
| Actual | Item saved, match created with score >= 50%, both items set to MATCHED |
| Status | PASS |

---

## TC-09 — Image Upload (valid JPEG)

| Field | Value |
|---|---|
| Test ID | TC-09 |
| Description | Upload a valid JPEG image with a lost item report |
| Input | Valid JPEG file (backpack.jpg) |
| Expected | File saved locally, SHA-256 hash stored in DB, storage indicator shown |
| Actual | File saved to static/uploads/, SHA-256 stored, "Stored locally" shown on detail page |
| Status | PASS |

---

## TC-10 — Invalid Image Upload

| Field | Value |
|---|---|
| Test ID | TC-10 |
| Description | Attempt to upload a PHP file disguised as an image |
| Input | File: evil.php with content-type application/x-php |
| Expected | Upload rejected, error message shown, item not saved |
| Actual | "Only JPG, JPEG, PNG and WEBP files are allowed" error shown |
| Status | PASS |

---

## TC-11 — Search Lost Items

| Field | Value |
|---|---|
| Test ID | TC-11 |
| Description | Search lost items by name keyword |
| Input | Search query: "Wallet" on /lost-items |
| Expected | Only items with "Wallet" in name returned |
| Actual | Filtered results shown correctly |
| Status | PASS |

---

## TC-12 — Automatic Matching

| Field | Value |
|---|---|
| Test ID | TC-12 |
| Description | Report a found item that matches an existing lost item |
| Input | Found item with same name, category, and location as a lost item |
| Expected | Match created with score >= 50%, shown on Matches page |
| Actual | Match created and displayed with matching reasons |
| Status | PASS |

---

## TC-13 — Edit Own Item

| Field | Value |
|---|---|
| Test ID | TC-13 |
| Description | Owner edits their own item |
| Input | Authenticated as item owner, update item name |
| Expected | Item updated, success message shown |
| Actual | Item updated in DB, "Item updated successfully" shown |
| Status | PASS |

---

## TC-14 — Unauthorized Edit

| Field | Value |
|---|---|
| Test ID | TC-14 |
| Description | User attempts to edit another user's item |
| Input | Authenticated as different user, GET /item/1/edit |
| Expected | 403 Forbidden response |
| Actual | 403 error page shown |
| Status | PASS |

---

## TC-15 — Delete Item

| Field | Value |
|---|---|
| Test ID | TC-15 |
| Description | Owner deletes their own item |
| Input | POST /item/1/delete by item owner |
| Expected | Item and associated matches deleted, redirected to dashboard |
| Actual | Item deleted from DB, matches removed, dashboard shown |
| Status | PASS |

---

## TC-16 — Mark Item Recovered

| Field | Value |
|---|---|
| Test ID | TC-16 |
| Description | Owner marks their item as recovered |
| Input | POST /item/1/recover by item owner |
| Expected | Item status changed to RECOVERED |
| Actual | Status updated to RECOVERED, shown on detail page |
| Status | PASS |

---

## TC-17 — SHA-256 Generation

| Field | Value |
|---|---|
| Test ID | TC-17 |
| Description | SHA-256 hash is calculated and stored when image is uploaded |
| Input | Upload valid JPEG image |
| Expected | 64-character hex SHA-256 hash stored in item.sha256_hash |
| Actual | Hash stored correctly, visible on item detail page |
| Status | PASS |

---

## TC-18 — SHA-256 Verification (local)

| Field | Value |
|---|---|
| Test ID | TC-18 |
| Description | Verify integrity of a locally stored image |
| Input | GET /verify/<item_id> for item with local image |
| Expected | "INTEGRITY VERIFIED" shown, stored and current hashes match |
| Actual | INTEGRITY VERIFIED displayed, both hashes identical |
| Status | PASS |

---

## TC-19 — S3 Upload

| Field | Value |
|---|---|
| Test ID | TC-19 |
| Description | Upload image to S3 when AWS credentials are configured |
| Input | Valid JPEG, S3 env vars set |
| Expected | File stored in S3 under lost-items/ or found-items/, s3_object_key saved in DB |
| Actual | PENDING — requires manual AWS S3 configuration |
| Status | PENDING |

---

## TC-20 — S3 Retrieval (presigned URL)

| Field | Value |
|---|---|
| Test ID | TC-20 |
| Description | Image displayed via presigned URL from private S3 bucket |
| Input | Item with s3_object_key, S3 configured |
| Expected | Image loads in browser via time-limited presigned URL |
| Actual | PENDING — requires manual AWS S3 configuration |
| Status | PENDING |

---

## TC-21 — S3 Delete

| Field | Value |
|---|---|
| Test ID | TC-21 |
| Description | Deleting an item removes its object from S3 |
| Input | Delete item that has s3_object_key |
| Expected | Object removed from S3 bucket |
| Actual | PENDING — requires manual AWS S3 configuration |
| Status | PENDING |

---

## TC-22 — S3 Encryption

| Field | Value |
|---|---|
| Test ID | TC-22 |
| Description | Uploaded S3 objects have AES256 server-side encryption |
| Input | Upload image with S3 configured |
| Expected | Object properties in AWS Console show SSE-S3 encryption |
| Actual | PENDING — requires manual AWS S3 configuration |
| Status | PENDING |

---

## TC-23 — Missing AWS Configuration (fallback)

| Field | Value |
|---|---|
| Test ID | TC-23 |
| Description | Application works normally when S3 env vars are not set |
| Input | No AWS env vars, upload image |
| Expected | Image saved locally, no crash, no error shown to user |
| Actual | Image saved to static/uploads/, S3 fallback logged internally |
| Status | PASS |

---

## TC-24 — EC2 Deployment

| Field | Value |
|---|---|
| Test ID | TC-24 |
| Description | Application runs on EC2 via Nginx + Gunicorn |
| Input | EC2 instance with Ubuntu 22.04, project cloned, .env configured |
| Expected | Application accessible at http://<EC2_PUBLIC_IP>, all features working |
| Actual | PENDING — requires manual EC2 instance creation and deployment |
| Status | PENDING |

---

## TC-25 — PaaS Deployment (Render)

| Field | Value |
|---|---|
| Test ID | TC-25 |
| Description | Application deployed and running on Render |
| Input | GitHub repository connected to Render, env vars set |
| Expected | Application accessible at https://<app>.onrender.com |
| Actual | PENDING — requires manual Render deployment |
| Status | PENDING |

---

## Automated Test Summary

Run: `python tests/test_app.py`

| Category | Tests | Result |
|---|---|---|
| Unit (SHA-256, S3 keys) | 8 | 8 PASS |
| S3 configuration (no credentials) | 3 | 3 PASS |
| Upload service (local fallback) | 11 | 11 PASS |
| Route and functional tests | 43 | 43 PASS |
| **Total** | **65** | **65 PASS** |
