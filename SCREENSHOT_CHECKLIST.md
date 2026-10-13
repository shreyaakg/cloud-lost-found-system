# SCREENSHOT_CHECKLIST.md
# Complete screenshot list for submission and viva

Mark each screenshot as captured: [ ] → [x]

---

## APPLICATION SCREENSHOTS

### Home Page
- [ ] SS-01: Home page at http://127.0.0.1:5000 showing hero section and features

### Authentication
- [ ] SS-02: Registration form (empty)
- [ ] SS-03: Registration form filled in
- [ ] SS-04: Registration success message on login page
- [ ] SS-05: Login form
- [ ] SS-06: Invalid login — error message shown
- [ ] SS-07: Logout — redirected to login with "logged out" message

### Dashboard
- [ ] SS-08: Dashboard showing all five statistics (lost, found, active, matched, recovered)

### Report Items
- [ ] SS-09: Report Lost Item form (empty)
- [ ] SS-10: Report Lost Item form filled in with image selected
- [ ] SS-11: Item detail page after submitting lost item (no image)
- [ ] SS-12: Item detail page after submitting lost item WITH image — showing SHA-256 hash
- [ ] SS-13: Report Found Item form
- [ ] SS-14: Item detail page after submitting found item

### Item Listings
- [ ] SS-15: Lost Items page showing list of items
- [ ] SS-16: Found Items page showing list of items
- [ ] SS-17: Search results — filtered by item name
- [ ] SS-18: Search results — filtered by category

### Matching
- [ ] SS-19: Matches page showing at least one match with score
- [ ] SS-20: Item detail page showing "Possible Matches" section

### Item Management
- [ ] SS-21: Edit Item form
- [ ] SS-22: Item after editing — success message
- [ ] SS-23: Item marked as RECOVERED — status badge shown
- [ ] SS-24: Confirmation dialog before delete

### SHA-256 Integrity
- [ ] SS-25: Integrity verification page showing INTEGRITY VERIFIED
- [ ] SS-26: Stored hash and current hash displayed (both identical)
- [ ] SS-27: Item detail page showing SHA-256 hash value

---

## GITHUB SCREENSHOTS

- [ ] SS-28: GitHub repository main page showing all project files
- [ ] SS-29: GitHub repository showing README.md rendered
- [ ] SS-30: GitHub code view — app.py
- [ ] SS-31: GitHub — .gitignore showing .env excluded
- [ ] SS-32: GitHub — no .env file present in repository (confirm secrets excluded)

---

## PAAS (RENDER) SCREENSHOTS

- [ ] SS-33: Render dashboard showing web service
- [ ] SS-34: Render — build logs showing "pip install" completing successfully
- [ ] SS-35: Render — build logs showing "gunicorn app:app" starting
- [ ] SS-36: Render — service status showing "Live" (green)
- [ ] SS-37: Render — environment variables panel (blur SECRET_KEY value)
- [ ] SS-38: Browser — home page at https://<app>.onrender.com
- [ ] SS-39: Browser — registration on Render URL
- [ ] SS-40: Browser — dashboard on Render URL
- [ ] SS-41: Browser — report lost item on Render URL

---

## EC2 SCREENSHOTS

### Instance Creation
- [ ] SS-42: EC2 Launch Wizard — AMI selection (Ubuntu 22.04)
- [ ] SS-43: EC2 Launch Wizard — Instance type (t2.micro, Free Tier eligible)
- [ ] SS-44: EC2 Launch Wizard — Key pair creation dialog
- [ ] SS-45: EC2 Launch Wizard — Security Group configuration (ports 22, 80, 443)

### Running Instance
- [ ] SS-46: EC2 Instances list — instance in Running state
- [ ] SS-47: EC2 Instance details — Public IPv4 address visible
- [ ] SS-48: EC2 Security Group — inbound rules showing ports 22, 80, 443

### SSH and Setup
- [ ] SS-49: SSH terminal — successful connection (ubuntu@ip-xxx prompt)
- [ ] SS-50: SSH terminal — git clone command and output
- [ ] SS-51: SSH terminal — pip install -r requirements.txt completing
- [ ] SS-52: SSH terminal — python app.py running without errors
- [ ] SS-53: SSH terminal — sudo systemctl status lostfound (active/running)
- [ ] SS-54: SSH terminal — sudo systemctl status nginx (active/running)

### Application on EC2
- [ ] SS-55: Browser — home page at http://<EC2_PUBLIC_IP>
- [ ] SS-56: Browser — registration on EC2 URL
- [ ] SS-57: Browser — dashboard on EC2 URL
- [ ] SS-58: Browser — report lost item on EC2 URL
- [ ] SS-59: Browser — SHA-256 verification on EC2 URL

---

## S3 SCREENSHOTS

- [ ] SS-60: S3 Console — bucket list showing your bucket
- [ ] SS-61: S3 Console — bucket properties showing Block Public Access (all enabled)
- [ ] SS-62: S3 Console — bucket properties showing default encryption (SSE-S3)
- [ ] SS-63: S3 Console — objects list showing lost-items/ or found-items/ folder
- [ ] SS-64: S3 Console — individual object properties showing encryption: SSE-S3
- [ ] SS-65: S3 Console — object after upload (filename is UUID, not original name)
- [ ] SS-66: Browser — item detail page showing "Stored in AWS S3" badge
- [ ] SS-67: Browser — image loading via presigned URL (check URL in browser address bar)
- [ ] SS-68: S3 Console — object deleted after item deletion

---

## SECURITY SCREENSHOTS

### IAM
- [ ] SS-69: IAM Console — policy JSON showing only 3 S3 actions
- [ ] SS-70: IAM Console — user with policy attached
- [ ] SS-71: EC2 Console — IAM Role attached to instance (if using role)

### SHA-256 and Integrity
- [ ] SS-72: Integrity verification page — INTEGRITY VERIFIED result
- [ ] SS-73: Integrity verification page — stored hash and current hash (matching)
- [ ] SS-74: Code view of services/integrity.py showing SHA-256 implementation

---

## TOTAL: 74 screenshots

Priority screenshots for viva (minimum set):
SS-08, SS-12, SS-19, SS-25, SS-36, SS-38, SS-46, SS-55, SS-62, SS-64, SS-66, SS-72
