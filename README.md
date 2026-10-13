# Cloud-Based Lost Item Tracking and Recovery System

A Flask web application for reporting, searching and recovering lost and found items.
Built as a college Virtualization and Cloud Computing project — Part 1 (local) + Part 2 (Render PaaS).

## Features

- User registration and login with hashed passwords
- Report lost and found items with image upload
- Automatic item matching using weighted similarity scoring
- SHA-256 file integrity verification
- Search and filter items by name, category, location and status
- Owner-only edit, delete and recovery controls
- Clean responsive UI (no external CSS frameworks)
- Deployed on Render (public PaaS)
- Ready for AWS EC2 deployment (Part 2)

## Tech Stack

- Python 3.10 / Flask 2.3.3
- Flask-SQLAlchemy (SQLite locally, ephemeral on Render)
- Flask-Login
- Werkzeug (password hashing, secure filenames)
- python-dotenv
- Gunicorn (production WSGI server)

## Local Installation

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
copy .env.example .env       # Windows
cp .env.example .env         # macOS/Linux
# Edit .env and set a strong SECRET_KEY

# 5. Run locally
python app.py
```

Open http://127.0.0.1:5000

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| SECRET_KEY | Flask session secret key | Yes |
| DATABASE_URL | SQLite or PostgreSQL URL | No (defaults to SQLite) |
| RENDER | Set to `true` on Render (controls upload path) | Render only |
| AWS_ACCESS_KEY_ID | AWS key | Part 2 only |
| AWS_SECRET_ACCESS_KEY | AWS secret | Part 2 only |
| AWS_S3_BUCKET | S3 bucket name | Part 2 only |
| AWS_REGION | AWS region | Part 2 only |

## Production (Render)

Start command used by Render:

```
gunicorn app:app
```

See `PAAS_DEPLOYMENT.md` for full deployment instructions.

## Folder Structure

```
vcc project/
├── app.py                  # Application factory and WSGI entry point
├── config.py               # Configuration (env vars, upload path logic)
├── extensions.py           # Flask extensions (db, login_manager)
├── Procfile                # Render/Heroku process declaration
├── render.yaml             # Render infrastructure-as-code config
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── PAAS_DEPLOYMENT.md
├── models/
│   ├── user.py             # User model
│   └── item.py             # Item and Match models
├── routes/
│   ├── auth.py             # Register, login, logout
│   ├── main.py             # Home, dashboard
│   └── items.py            # All item CRUD and matching routes
├── services/
│   ├── integrity.py        # SHA-256 hashing
│   ├── upload.py           # File upload validation and saving
│   └── matching.py         # Item matching algorithm
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── dashboard.html
│   ├── auth/
│   ├── items/
│   └── errors/
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── uploads/
├── tests/
│   └── test_app.py         # 28 functional tests
└── instance/               # SQLite database (auto-created, not committed)
```

## Matching Algorithm

Items are compared using weighted token overlap:

| Field | Weight |
|---|---|
| Item name | 35% |
| Category | 25% |
| Location | 25% |
| Description | 15% |

Matches with score ≥ 50% are saved and displayed automatically.

## Running Tests

```bash
python tests/test_app.py
```

Expected: 28 passed, 0 failed.
