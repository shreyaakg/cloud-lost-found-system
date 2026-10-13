# EC2 Deployment Guide
# Cloud-Based Lost Item Tracking and Recovery System

## Architecture

```
Browser (Internet)
        |  Port 80 (HTTP)
        v
   AWS EC2 Instance
   Ubuntu 22.04 LTS
        |
        v
     Nginx (reverse proxy)
     Listens on port 80
     Serves static files directly
        |  Unix socket: /tmp/lostfound.sock
        v
   Gunicorn (WSGI server)
   3 worker processes
        |
        v
   Flask Application
   Entry point: app:app
        |
        v
   SQLite (local DB)  +  Amazon S3 (image storage)
```

---

## Placeholders Used in This Guide

Replace these with your actual values everywhere they appear:

| Placeholder | Meaning |
|---|---|
| `<EC2_PUBLIC_IP>` | Your EC2 instance public IPv4 address |
| `<YOUR_KEY.pem>` | Your downloaded SSH key pair filename |
| `<YOUR_GITHUB_USERNAME>` | Your GitHub username |
| `<YOUR_REPO_NAME>` | Your GitHub repository name |
| `<YOUR_SECRET_KEY>` | A strong random Flask secret key |
| `<YOUR_S3_BUCKET>` | Your S3 bucket name |
| `<YOUR_AWS_REGION>` | Your AWS region (e.g. ap-southeast-1) |

---

## PART 1 — Launch EC2 Instance

### Step 1 — Open EC2 in AWS Console

1. Go to https://console.aws.amazon.com
2. Sign in to your AWS account.
3. In the top-right corner, select your region (e.g. **ap-southeast-1 Singapore**).
4. In the search bar, type **EC2** and click the EC2 service.
5. Click **Launch instance**.

### Step 2 — Configure the Instance

Fill in the following settings:

**Name and tags**
- Name: `lostfound-cloud-server`

**Application and OS Images (AMI)**
- Click **Browse more AMIs** if needed.
- Select: **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type**
- Architecture: **64-bit (x86)**

**Instance type**
- Select: **t2.micro** (1 vCPU, 1 GB RAM)
- This is Free Tier eligible — suitable for a college project.

**Key pair (login)**
- Click **Create new key pair**.
- Key pair name: `lostfound-key`
- Key pair type: RSA
- Private key file format: `.pem` (for Linux/macOS SSH) or `.ppk` (for PuTTY on Windows)
- Click **Create key pair**.
- The file downloads automatically. **Save it securely — it cannot be downloaded again.**
- On Windows, save it to: `C:\Users\<YourName>\.ssh\lostfound-key.pem`

**Network settings**
- Click **Edit**.
- VPC: leave as default.
- Subnet: leave as default (any availability zone).
- Auto-assign public IP: **Enable**.
- Firewall (Security Groups): **Create security group**.
- Security group name: `lostfound-sg`
- Description: `LostFound Cloud security group`
- Add the following inbound rules:

| Type | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| SSH | TCP | 22 | My IP | Secure SSH access from your machine only |
| HTTP | TCP | 80 | 0.0.0.0/0 | Public web access |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Future HTTPS (optional now) |

> **Important:** For SSH, select **My IP** not **Anywhere**.
> This restricts SSH to your current IP address only.
> Port 5000 (Flask dev server) must NOT be opened publicly.

**Configure storage**
- Size: **20 GiB** (default 8 GiB is fine, 20 gives more room)
- Volume type: gp3

**Summary**
- Number of instances: 1
- Click **Launch instance**.

### Step 3 — Find Your Public IP Address

1. Go to **EC2 → Instances**.
2. Wait until the instance **State** shows **Running** and **Status check** shows **2/2 checks passed**.
3. Click on your instance.
4. In the **Details** tab, copy the **Public IPv4 address**.
   This is your `<EC2_PUBLIC_IP>`.

---

## PART 2 — Connect via SSH

### On Windows (using PowerShell or Git Bash)

First, fix the key file permissions (required by SSH):

```powershell
# In PowerShell — run once to fix permissions
icacls "C:\Users\<YourName>\.ssh\<YOUR_KEY.pem>" /inheritance:r /grant:r "%USERNAME%:R"
```

Then connect:

```bash
ssh -i "C:\Users\<YourName>\.ssh\<YOUR_KEY.pem>" ubuntu@<EC2_PUBLIC_IP>
```

### On macOS / Linux

```bash
chmod 400 ~/.ssh/<YOUR_KEY.pem>
ssh -i ~/.ssh/<YOUR_KEY.pem> ubuntu@<EC2_PUBLIC_IP>
```

### Expected output

```
Welcome to Ubuntu 22.04.x LTS ...
ubuntu@ip-xxx-xxx-xxx-xxx:~$
```

You are now inside the EC2 instance.

---

## PART 3 — Install System Dependencies

Run these commands on the EC2 instance (copy and paste each block):

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Install Python 3.10, pip, venv, and build tools
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Install Git
sudo apt install -y git

# Install Nginx
sudo apt install -y nginx

# Install additional system packages needed by Python packages
sudo apt install -y build-essential libssl-dev libffi-dev

# Verify versions
python3 --version
pip3 --version
git --version
nginx -v
```

Expected output:
```
Python 3.10.x
pip 22.x.x
git version 2.x.x
nginx version: nginx/1.x.x
```

---

## PART 4 — Clone the Project

```bash
# Navigate to home directory
cd /home/ubuntu

# Clone your GitHub repository
git clone https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>.git lostfound-cloud

# Enter the project directory
cd lostfound-cloud

# Verify the project structure
ls -la
```

You should see: `app.py`, `config.py`, `requirements.txt`, `models/`, `routes/`, etc.

---

## PART 5 — Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Verify — prompt should show (venv)
which python
# Expected: /home/ubuntu/lostfound-cloud/venv/bin/python

# Upgrade pip
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

# Verify gunicorn is installed
gunicorn --version
# Expected: gunicorn (version 21.2.0)
```

---

## PART 6 — Environment Variables

**Never put secrets in GitHub.** Create the `.env` file directly on the server:

```bash
# Make sure you are in the project directory
cd /home/ubuntu/lostfound-cloud

# Create the .env file
nano .env
```

Paste the following content into nano, replacing all placeholders:

```
SECRET_KEY=<YOUR_SECRET_KEY>
DATABASE_URL=sqlite:///lostfound.db
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=<YOUR_AWS_REGION>
S3_BUCKET_NAME=<YOUR_S3_BUCKET>
FLASK_DEBUG=false
```

To generate a strong SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output and paste it as the SECRET_KEY value.

Save and exit nano: press `Ctrl+X`, then `Y`, then `Enter`.

Protect the file so only the ubuntu user can read it:
```bash
chmod 600 .env
```

### IAM Role (Recommended for S3 on EC2)

Instead of putting `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`,
attach an IAM Role to the EC2 instance:

1. In AWS Console → **IAM** → **Roles** → **Create role**.
2. Trusted entity: **AWS service** → **EC2**.
3. Attach the `LostFoundS3Policy` you created in S3_SETUP.md.
4. Role name: `lostfound-ec2-role`.
5. Click **Create role**.
6. Go to **EC2 → Instances** → select your instance.
7. **Actions → Security → Modify IAM role**.
8. Select `lostfound-ec2-role` → **Update IAM role**.

With the IAM Role attached, boto3 automatically uses the instance credentials.
Leave `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` **blank** in `.env`.

---

## PART 7 — Create Required Directories

```bash
cd /home/ubuntu/lostfound-cloud

# Create logs directory for Gunicorn
mkdir -p logs

# Create uploads directory for local image storage
mkdir -p static/uploads

# Set correct permissions
chmod 755 static/uploads
```

---

## PART 8 — Test Flask Directly

Before configuring Gunicorn and Nginx, verify Flask starts correctly:

```bash
cd /home/ubuntu/lostfound-cloud
source venv/bin/activate

# Run Flask directly on port 5000 (temporary test only)
python app.py
```

Expected output:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: off
```

Press `Ctrl+C` to stop.

> Do NOT open port 5000 in the Security Group.
> This test is only to confirm Flask starts without errors.
> The public will access the app through Nginx on port 80.

---

## PART 9 — Configure Gunicorn

The `gunicorn.conf.py` file is already in the project. Verify it:

```bash
cat gunicorn.conf.py
```

Test Gunicorn manually:

```bash
cd /home/ubuntu/lostfound-cloud
source venv/bin/activate

gunicorn --config gunicorn.conf.py app:app
```

Expected output:
```
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: unix:/tmp/lostfound.sock
[INFO] Worker booting (pid: XXXX)
[INFO] Booting worker with pid: XXXX
```

Press `Ctrl+C` to stop.

---

## PART 10 — Configure Systemd Service

This makes Gunicorn start automatically on boot and restart on failure.

```bash
# Copy the example service file from the project
sudo cp lostfound.service.example /etc/systemd/system/lostfound.service

# Open it to verify the paths are correct
sudo nano /etc/systemd/system/lostfound.service
```

Verify these lines match your setup exactly:
```
WorkingDirectory=/home/ubuntu/lostfound-cloud
EnvironmentFile=/home/ubuntu/lostfound-cloud/.env
ExecStart=/home/ubuntu/lostfound-cloud/venv/bin/gunicorn \
          --config /home/ubuntu/lostfound-cloud/gunicorn.conf.py \
          app:app
```

Save and exit (`Ctrl+X`, `Y`, `Enter`).

```bash
# Reload systemd to pick up the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable lostfound

# Start the service now
sudo systemctl start lostfound

# Check the status
sudo systemctl status lostfound
```

Expected output:
```
● lostfound.service - LostFound Cloud — Gunicorn WSGI Server
     Loaded: loaded (/etc/systemd/system/lostfound.service; enabled)
     Active: active (running) since ...
```

Check logs if there are errors:
```bash
sudo journalctl -u lostfound -n 50 --no-pager
```

---

## PART 11 — Configure Nginx

```bash
# Copy the example Nginx config from the project
sudo cp nginx.conf.example /etc/nginx/sites-available/lostfound

# Edit it — replace <EC2_PUBLIC_IP> with your actual IP
sudo nano /etc/nginx/sites-available/lostfound
```

Change this line:
```nginx
server_name <EC2_PUBLIC_IP>;
```
to your actual IP, for example:
```nginx
server_name 54.123.45.67;
```

Save and exit.

```bash
# Enable the site by creating a symlink
sudo ln -s /etc/nginx/sites-available/lostfound /etc/nginx/sites-enabled/

# Remove the default Nginx site to avoid conflicts
sudo rm -f /etc/nginx/sites-enabled/default

# Test the Nginx configuration for syntax errors
sudo nginx -t
```

Expected output:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

```bash
# Reload Nginx to apply the new configuration
sudo systemctl reload nginx

# Ensure Nginx starts on boot
sudo systemctl enable nginx

# Check Nginx status
sudo systemctl status nginx
```

---

## PART 12 — Fix File Permissions

Nginx runs as `www-data`. It needs read access to static files:

```bash
# Add www-data to the ubuntu group
sudo usermod -aG ubuntu www-data

# Set correct ownership and permissions on the project
sudo chown -R ubuntu:www-data /home/ubuntu/lostfound-cloud
sudo chmod -R 750 /home/ubuntu/lostfound-cloud
sudo chmod -R 755 /home/ubuntu/lostfound-cloud/static

# The instance/ directory needs write permission for SQLite
sudo chmod 775 /home/ubuntu/lostfound-cloud/instance
sudo chmod 775 /home/ubuntu/lostfound-cloud/static/uploads

# Restart both services to apply permission changes
sudo systemctl restart lostfound
sudo systemctl restart nginx
```

---

## PART 13 — Test the Deployment

Open a browser and go to:

```
http://<EC2_PUBLIC_IP>
```

You should see the LostFound Cloud home page.

Test each feature:

```
http://<EC2_PUBLIC_IP>/register
http://<EC2_PUBLIC_IP>/login
http://<EC2_PUBLIC_IP>/dashboard
http://<EC2_PUBLIC_IP>/report-lost
http://<EC2_PUBLIC_IP>/report-found
http://<EC2_PUBLIC_IP>/lost-items
http://<EC2_PUBLIC_IP>/found-items
http://<EC2_PUBLIC_IP>/matches
http://<EC2_PUBLIC_IP>/my-reports
```

---

## PART 14 — Useful Management Commands

```bash
# View Gunicorn logs (live)
sudo journalctl -u lostfound -f

# View Nginx access log
sudo tail -f /var/log/nginx/access.log

# View Nginx error log
sudo tail -f /var/log/nginx/error.log

# View Gunicorn application logs
tail -f /home/ubuntu/lostfound-cloud/logs/gunicorn_error.log

# Restart Gunicorn after code changes
sudo systemctl restart lostfound

# Reload Nginx after config changes
sudo systemctl reload nginx

# Pull latest code from GitHub and restart
cd /home/ubuntu/lostfound-cloud
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart lostfound
```

---

## PART 15 — Troubleshooting

### SSH: Permission denied (publickey)

```bash
# Fix key permissions on Windows (PowerShell)
icacls "C:\Users\<YourName>\.ssh\<YOUR_KEY.pem>" /inheritance:r /grant:r "%USERNAME%:R"

# Fix key permissions on macOS/Linux
chmod 400 ~/.ssh/<YOUR_KEY.pem>
```

If still failing: verify the key pair matches the one selected at instance launch.

---

### SSH: Connection timed out

- Check the Security Group inbound rules — port 22 must be open.
- Check that **My IP** is selected, not a stale IP.
- Your ISP may have changed your IP — update the Security Group rule.

```
EC2 → Security Groups → lostfound-sg → Inbound rules → Edit → Update SSH source to My IP
```

---

### Port 80 not accessible in browser

```bash
# Check Nginx is running
sudo systemctl status nginx

# Check Gunicorn socket exists
ls -la /tmp/lostfound.sock

# Check Nginx error log
sudo tail -20 /var/log/nginx/error.log

# Verify Security Group has port 80 open to 0.0.0.0/0
```

---

### Gunicorn fails to start

```bash
# Check the service log
sudo journalctl -u lostfound -n 100 --no-pager

# Common causes:
# 1. Wrong path in lostfound.service
# 2. .env file missing or has wrong permissions
# 3. Python package missing

# Test manually
cd /home/ubuntu/lostfound-cloud
source venv/bin/activate
python -c "from app import app; print('OK')"
```

---

### Flask import error / ModuleNotFoundError

```bash
cd /home/ubuntu/lostfound-cloud
source venv/bin/activate
pip install -r requirements.txt

# Verify the specific missing module
pip show flask flask-sqlalchemy flask-login
```

---

### Nginx 502 Bad Gateway

This means Nginx cannot reach Gunicorn. Check:

```bash
# Is the socket file present?
ls -la /tmp/lostfound.sock

# Is Gunicorn running?
sudo systemctl status lostfound

# Check socket permissions
# www-data must be able to read the socket
sudo chmod 660 /tmp/lostfound.sock
sudo chown ubuntu:www-data /tmp/lostfound.sock
```

---

### Database permission error

```bash
# SQLite needs write access to the instance/ directory
sudo chmod 775 /home/ubuntu/lostfound-cloud/instance
sudo chown ubuntu:www-data /home/ubuntu/lostfound-cloud/instance

# If the DB file already exists
sudo chmod 664 /home/ubuntu/lostfound-cloud/instance/lostfound.db
sudo chown ubuntu:www-data /home/ubuntu/lostfound-cloud/instance/lostfound.db
```

---

### S3 Access Denied

```bash
# Check environment variables are loaded
cd /home/ubuntu/lostfound-cloud
source venv/bin/activate
python3 -c "
from app import create_app
app = create_app()
with app.app_context():
    from services.s3_service import check_s3_connection
    ok, err = check_s3_connection()
    print('S3 OK:', ok)
    print('Error:', err)
"
```

If using IAM Role: verify the role is attached to the instance in EC2 console.
If using access keys: verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`.

---

### Environment variable missing

```bash
# Verify .env is present and readable
cat /home/ubuntu/lostfound-cloud/.env

# Verify systemd loads it
sudo systemctl show lostfound | grep EnvironmentFile

# After editing .env, always restart the service
sudo systemctl restart lostfound
```

---

## Security Group Summary

| Rule | Protocol | Port | Source | Reason |
|---|---|---|---|---|
| SSH | TCP | 22 | My IP only | Secure admin access |
| HTTP | TCP | 80 | 0.0.0.0/0 | Public web access |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Future SSL (optional) |

Port 5000 must NOT be opened. Flask dev server is never exposed publicly.

---

## Screenshot Checklist (for submission)

Capture these screenshots in order:

1. **EC2 Launch Wizard** — AMI selection screen showing Ubuntu 22.04
2. **EC2 Launch Wizard** — Instance type showing t2.micro (Free Tier eligible)
3. **EC2 Launch Wizard** — Key pair creation dialog
4. **EC2 Launch Wizard** — Security Group configuration showing ports 22, 80, 443
5. **EC2 Console** — Instances list showing instance in **Running** state
6. **EC2 Console** — Instance details panel showing Public IPv4 address
7. **EC2 Console** — Security Group inbound rules
8. **SSH Terminal** — Successful connection showing `ubuntu@ip-xxx-xxx-xxx-xxx:~$`
9. **SSH Terminal** — `git clone` command and output
10. **SSH Terminal** — `pip install -r requirements.txt` completing successfully
11. **SSH Terminal** — `python app.py` running without errors (then Ctrl+C)
12. **SSH Terminal** — `sudo systemctl status lostfound` showing **active (running)**
13. **SSH Terminal** — `sudo systemctl status nginx` showing **active (running)**
14. **Browser** — `http://<EC2_PUBLIC_IP>` showing the home page
15. **Browser** — Registration page on the EC2 URL
16. **Browser** — Dashboard after login on the EC2 URL
17. **Browser** — Report Lost Item form on the EC2 URL
18. **Browser** — Item detail page showing uploaded image (S3 or local)
19. **Browser** — SHA-256 Integrity Verification page showing INTEGRITY VERIFIED
20. **Browser** — Matches page showing a detected match
21. **EC2 Console** — IAM Role attached to instance (if using IAM Role for S3)
22. **S3 Console** — Bucket showing uploaded objects in lost-items/ or found-items/

---

## Viva Explanation

### What is EC2?

Amazon EC2 (Elastic Compute Cloud) is an IaaS (Infrastructure as a Service) offering.
Unlike PaaS (Render), EC2 gives you a full virtual machine — you control the OS,
the web server, the process manager, and all configuration.

### Why Nginx + Gunicorn?

- **Gunicorn** is a Python WSGI server. It runs multiple worker processes of the Flask
  application and handles concurrent requests efficiently.
- **Nginx** is a high-performance reverse proxy. It sits in front of Gunicorn and:
  - Serves static files (CSS, JS, images) directly without involving Python.
  - Handles slow clients without blocking Gunicorn workers.
  - Provides security headers and hides the internal server details.
- Flask's built-in development server (`python app.py`) is single-threaded and not
  suitable for production — it is never exposed publicly.

### Why systemd?

Systemd manages the Gunicorn process as a system service:
- Starts automatically when the EC2 instance boots.
- Restarts automatically if Gunicorn crashes.
- Logs are accessible via `journalctl`.

### Why IAM Role instead of access keys on EC2?

- Access keys are long-lived credentials that can be leaked if `.env` is exposed.
- An IAM Role is attached to the EC2 instance itself — credentials are temporary,
  automatically rotated by AWS, and never stored in any file.
- boto3 automatically detects and uses the instance role with no code changes.
- This follows the AWS security best practice of least privilege with no static credentials.

### EC2 vs Render (PaaS)

| Aspect | Render (PaaS) | EC2 (IaaS) |
|---|---|---|
| Control | Limited | Full OS control |
| Setup effort | Minimal | Manual configuration |
| Scaling | Automatic | Manual |
| Cost | Free tier available | Free tier (t2.micro) |
| Persistence | Ephemeral filesystem | Persistent EBS volume |
| Use case | Quick deployment | Production-grade control |
