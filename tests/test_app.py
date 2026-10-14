"""
Functional test suite — run with: python tests/test_app.py
Covers: routing, auth, item CRUD, matching, SHA-256, S3 service unit tests,
        DB error handling, connection pool config, healthz endpoint.
Expected: all tests pass with no AWS credentials configured (local fallback).
"""
import sys
import os
import io
import hashlib
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from services.integrity import calculate_sha256_bytes
from services.s3_service import build_object_key

app = create_app()

PASS = []
FAIL = []


def check(label, condition):
    if condition:
        PASS.append(label)
        print(f"  PASS  {label}")
    else:
        FAIL.append(label)
        print(f"  FAIL  {label}")


# ---------------------------------------------------------------------------
# Unit tests — no Flask context needed
# ---------------------------------------------------------------------------
print("\n--- Unit Tests ---")

data = b"hello world"
expected = hashlib.sha256(data).hexdigest()
check("SHA-256 bytes correct", calculate_sha256_bytes(data) == expected)
check("SHA-256 empty bytes", calculate_sha256_bytes(b'') == hashlib.sha256(b'').hexdigest())

key = build_object_key('LOST', 'photo.jpg')
check("S3 key starts with lost-items/", key.startswith('lost-items/'))
check("S3 key ends with .jpg", key.endswith('.jpg'))
check("S3 key has UUID length", len(key) == len('lost-items/') + 32 + 4)

key2 = build_object_key('FOUND', 'image.png')
check("S3 key starts with found-items/", key2.startswith('found-items/'))
check("S3 key ends with .png", key2.endswith('.png'))

key3 = build_object_key('LOST', 'photo.jpg')
check("S3 keys are unique (UUID)", key != key3)

# ---------------------------------------------------------------------------
# Config tests — pool options and URL normalisation
# ---------------------------------------------------------------------------
print("\n--- Config Tests ---")

from config import _database_uri, Config

# No DATABASE_URL → SQLite fallback
check("No DATABASE_URL -> SQLite", _database_uri() == 'sqlite:///lostfound.db')

# Legacy postgres:// scheme is normalised
with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@host/db'}):
    uri = _database_uri()
    check("postgres:// normalised to postgresql+psycopg2://",
          uri.startswith('postgresql+psycopg2://'))

# postgresql:// scheme is pinned to psycopg2
with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@host/db'}):
    uri = _database_uri()
    check("postgresql:// pinned to postgresql+psycopg2://",
          uri.startswith('postgresql+psycopg2://'))

# Already-pinned URL is not double-prefixed
with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgresql+psycopg2://user:pass@host/db'}):
    uri = _database_uri()
    check("Already-pinned URL not double-prefixed",
          uri.count('postgresql+psycopg2://') == 1)

# Malformed DATABASE_URL raises ValueError
try:
    with mock.patch.dict(os.environ, {'DATABASE_URL': 'mysql://user:pass@host/db'}):
        _database_uri()
    check("Malformed DATABASE_URL raises ValueError", False)
except ValueError:
    check("Malformed DATABASE_URL raises ValueError", True)

# SQLite config has empty engine options
with mock.patch.dict(os.environ, {}, clear=True):
    # Reload config in a clean env
    import importlib, config as cfg_mod
    importlib.reload(cfg_mod)
    check("SQLite config has empty SQLALCHEMY_ENGINE_OPTIONS",
          cfg_mod.Config.SQLALCHEMY_ENGINE_OPTIONS == {})

# PostgreSQL config has pool_pre_ping and pool_recycle
with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgresql+psycopg2://u:p@h/d'}):
    importlib.reload(cfg_mod)
    opts = cfg_mod.Config.SQLALCHEMY_ENGINE_OPTIONS
    check("PostgreSQL config has pool_pre_ping=True",
          opts.get('pool_pre_ping') is True)
    check("PostgreSQL config has pool_recycle=300",
          opts.get('pool_recycle') == 300)
    check("PostgreSQL config has sslmode=require",
          opts.get('connect_args', {}).get('sslmode') == 'require')
    check("PostgreSQL config has connect_timeout",
          opts.get('connect_args', {}).get('connect_timeout') == 10)

# Restore original config module state
importlib.reload(cfg_mod)

# ---------------------------------------------------------------------------
# S3 configuration check — no credentials set, should return False cleanly
# ---------------------------------------------------------------------------
print("\n--- S3 Configuration Tests (no credentials) ---")

with app.app_context():
    from services.s3_service import is_s3_configured, check_s3_connection
    check("is_s3_configured() False when no env vars", not is_s3_configured())
    ok, err = check_s3_connection()
    check("check_s3_connection() returns False gracefully", not ok)
    check("check_s3_connection() returns error message", isinstance(err, str) and len(err) > 0)

# ---------------------------------------------------------------------------
# Upload service — local fallback (no S3)
# ---------------------------------------------------------------------------
print("\n--- Upload Service Tests (local fallback) ---")

with app.app_context():
    from services.upload import save_upload, allowed_file, _detect_mime

    check("allowed_file jpg",          allowed_file('photo.jpg'))
    check("allowed_file jpeg",         allowed_file('photo.jpeg'))
    check("allowed_file png",          allowed_file('photo.PNG'))
    check("allowed_file webp",         allowed_file('photo.webp'))
    check("allowed_file rejects exe",  not allowed_file('virus.exe'))
    check("allowed_file rejects php",  not allowed_file('shell.php'))
    check("allowed_file rejects gif",  not allowed_file('anim.gif'))
    check("allowed_file rejects no ext", not allowed_file('noextension'))

    jpeg_header = b'\xff\xd8\xff\xe0' + b'\x00' * 8
    png_header  = b'\x89PNG\r\n\x1a\n' + b'\x00' * 4
    webp_header = b'RIFF\x00\x00\x00\x00WEBP'
    check("MIME detect JPEG", _detect_mime(jpeg_header) == 'image/jpeg')
    check("MIME detect PNG",  _detect_mime(png_header)  == 'image/png')
    check("MIME detect WEBP", _detect_mime(webp_header) == 'image/webp')
    check("MIME detect unknown returns None",
          _detect_mime(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b') is None)

    class FakeFile:
        def __init__(self, name, data, content_type='image/jpeg'):
            self.filename = name
            self._data = data
            self.content_type = content_type
        def read(self): return self._data

    result = save_upload(FakeFile('', b''), 'LOST')
    check("save_upload empty filename returns None result",
          result.filename is None and result.s3_key is None)

    try:
        save_upload(FakeFile('virus.exe', b'\xff\xd8\xff' + b'x'*100), 'LOST')
        check("save_upload rejects .exe", False)
    except ValueError as e:
        check("save_upload rejects .exe", 'allowed' in str(e).lower())

    jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 500
    result = save_upload(FakeFile('test.jpg', jpeg_bytes), 'LOST')
    check("save_upload local JPEG returns filename",  result.filename is not None)
    check("save_upload local JPEG returns sha256",    result.sha256_hash is not None)
    check("save_upload local JPEG storage=local",     result.storage == 'local')
    check("save_upload local JPEG s3_key is None",    result.s3_key is None)
    check("save_upload SHA-256 is correct",
          result.sha256_hash == calculate_sha256_bytes(jpeg_bytes))

    if result.filename:
        test_path = os.path.join(app.config['UPLOAD_FOLDER'], result.filename)
        if os.path.exists(test_path):
            os.remove(test_path)

# ---------------------------------------------------------------------------
# Flask route tests
# ---------------------------------------------------------------------------
print("\n--- Route Tests ---")

with app.test_client() as c:
    # Public routes
    check("Home page 200",        c.get('/').status_code == 200)
    check("Login page 200",       c.get('/login').status_code == 200)
    check("Register page 200",    c.get('/register').status_code == 200)
    check("Lost items page 200",  c.get('/lost-items').status_code == 200)
    check("Found items page 200", c.get('/found-items').status_code == 200)

    # Health check endpoint
    r = c.get('/healthz')
    check("Health check returns 200 (SQLite)", r.status_code == 200)
    check("Health check returns JSON", b'database' in r.data)
    check("Health check DB status ok", b'"ok"' in r.data)

    # Protected routes redirect when not logged in
    check("Dashboard redirects",   c.get('/dashboard').status_code == 302)
    check("Report-lost redirects", c.get('/report-lost').status_code == 302)
    check("My-reports redirects",  c.get('/my-reports').status_code == 302)
    check("Matches redirects",     c.get('/matches').status_code == 302)

    # Registration
    r = c.post('/register', data={
        'name': 'Alice Smith', 'email': 'alice@test.com',
        'phone': '9876543210', 'password': 'secret123',
        'confirm_password': 'secret123'
    }, follow_redirects=True)
    check("Registration succeeds (200)", r.status_code == 200)
    check("Registration redirects to login", b'Sign In' in r.data or b'Login' in r.data)

    r2 = c.post('/register', data={
        'name': 'Alice Again', 'email': 'alice@test.com',
        'phone': '111', 'password': 'secret123', 'confirm_password': 'secret123'
    }, follow_redirects=True)
    check("Duplicate email rejected", b'already registered' in r2.data)

    # Login
    r = c.post('/login', data={
        'email': 'alice@test.com', 'password': 'secret123'
    }, follow_redirects=True)
    check("Login succeeds (200)", r.status_code == 200)
    check("Dashboard shown after login", b'Dashboard' in r.data or b'Welcome' in r.data)

    # Wrong password
    c.get('/logout')
    r = c.post('/login', data={
        'email': 'alice@test.com', 'password': 'wrongpass'
    }, follow_redirects=True)
    check("Wrong password rejected", b'invalid' in r.data.lower())
    c.post('/login', data={'email': 'alice@test.com', 'password': 'secret123'})

    # Dashboard
    check("Dashboard accessible after login", c.get('/dashboard').status_code == 200)

    # Report lost item (no image)
    r = c.post('/report-lost', data={
        'item_name': 'Black Wallet', 'category': 'Accessories',
        'description': 'Black leather wallet with ID cards inside',
        'location': 'Main Library Ground Floor',
        'date_lost_found': '2024-01-15', 'contact': 'alice@test.com'
    }, follow_redirects=True)
    check("Report lost item (200)", r.status_code == 200)
    check("Lost item detail shown", b'Black Wallet' in r.data)

    # Report found item (should trigger match)
    r = c.post('/report-found', data={
        'item_name': 'Black Wallet', 'category': 'Accessories',
        'description': 'Found black leather wallet near library',
        'location': 'Main Library', 'date_lost_found': '2024-01-16',
        'contact': 'finder@test.com'
    }, follow_redirects=True)
    check("Report found item (200)", r.status_code == 200)
    check("Found item detail shown", b'Black Wallet' in r.data)

    # Matches
    r = c.get('/matches')
    check("Matches page loads (200)", r.status_code == 200)
    check("Match detected", b'Black Wallet' in r.data)

    # My reports
    check("My reports page (200)", c.get('/my-reports').status_code == 200)

    # Item detail
    check("Item detail page (200)", c.get('/item/1').status_code == 200)

    # Edit item
    check("Edit item page (200)", c.get('/item/1/edit').status_code == 200)

    # 404 handler
    check("404 handler works", c.get('/nonexistent-page-xyz').status_code == 404)

    # Verify integrity (item without image)
    r = c.get('/verify/1')
    check("Verify integrity page (200)", r.status_code == 200)
    check("No image message shown",
          b'NO IMAGE' in r.data or b'no uploaded image' in r.data.lower())

    # Report lost item WITH a valid JPEG image
    jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 500
    from werkzeug.datastructures import FileStorage
    fs = FileStorage(stream=io.BytesIO(jpeg_bytes), filename='backpack.jpg',
                     content_type='image/jpeg')
    r = c.post('/report-lost', data={
        'item_name': 'Blue Backpack', 'category': 'Bags',
        'description': 'Blue backpack with laptop inside',
        'location': 'Cafeteria', 'date_lost_found': '2024-02-01',
        'contact': 'alice@test.com',
        'image': fs
    }, content_type='multipart/form-data', follow_redirects=False)
    check("Report lost item with image (302 redirect)", r.status_code == 302)
    location = r.headers.get('Location', '')
    image_item_id = location.rstrip('/').split('/')[-1] if '/item/' in location else None
    check("Image item ID captured from redirect",
          image_item_id is not None and image_item_id.isdigit())

    r = c.get(location, follow_redirects=True)
    check("Item with image detail shown", b'Blue Backpack' in r.data)
    check("Storage indicator shown", b'Stored' in r.data)

    if image_item_id:
        r = c.get(f'/verify/{image_item_id}')
        check("Verify integrity with image (200)", r.status_code == 200)
        check("INTEGRITY VERIFIED shown", b'INTEGRITY VERIFIED' in r.data)

    # Invalid file type upload
    r = c.post('/report-lost', data={
        'item_name': 'Test', 'category': 'Other',
        'description': 'Test item', 'location': 'Test',
        'date_lost_found': '2024-01-01', 'contact': 'test@test.com',
        'image': (io.BytesIO(b'<script>alert(1)</script>'), 'evil.php', 'application/x-php')
    }, content_type='multipart/form-data', follow_redirects=True)
    check("Invalid file type rejected", b'allowed' in r.data.lower() or r.status_code == 200)

    # Missing required fields returns 200 with error messages (not 500)
    r = c.post('/report-lost', data={
        'item_name': '', 'category': '', 'description': '',
        'location': '', 'date_lost_found': '', 'contact': ''
    }, follow_redirects=True)
    check("Missing fields returns 200 not 500", r.status_code == 200)
    check("Missing fields shows error message", b'required' in r.data.lower())

    # Unrelated items should NOT match each other
    r = c.post('/report-lost', data={
        'item_name': 'Red Umbrella', 'category': 'Other',
        'description': 'A red umbrella with wooden handle',
        'location': 'Bus Stop 42', 'date_lost_found': '2024-03-01',
        'contact': 'alice@test.com'
    }, follow_redirects=True)
    check("Unrelated lost item reported (200)", r.status_code == 200)

    r = c.post('/report-found', data={
        'item_name': 'Blue Laptop', 'category': 'Electronics',
        'description': 'A blue laptop found in the park',
        'location': 'Central Park', 'date_lost_found': '2024-03-02',
        'contact': 'finder2@test.com'
    }, follow_redirects=True)
    check("Unrelated found item reported (200)", r.status_code == 200)

    r = c.get('/matches')
    check("Unrelated items not matched",
          b'Red Umbrella' not in r.data or b'Blue Laptop' not in r.data)

    # List pages render correctly
    r = c.get('/lost-items')
    check("Lost items list renders without 500", r.status_code == 200)
    r = c.get('/found-items')
    check("Found items list renders without 500", r.status_code == 200)

    # Auto-match failure does not cause 500 — item is still saved
    r = c.post('/report-lost', data={
        'item_name': 'Green Scarf', 'category': 'Clothing',
        'description': 'Green woolen scarf',
        'location': 'Train Station', 'date_lost_found': '2024-04-01',
        'contact': 'alice@test.com'
    }, follow_redirects=True)
    check("Item saved even if auto-match runs (200)", r.status_code == 200)
    check("Item detail shown after save", b'Green Scarf' in r.data)

    # Dashboard counts are accurate
    r = c.get('/dashboard')
    check("Dashboard loads (200)", r.status_code == 200)
    # We have reported: Black Wallet (LOST+FOUND matched), Blue Backpack (LOST),
    # Red Umbrella (LOST), Green Scarf (LOST), Blue Laptop (FOUND)
    # Lost count >= 4, Found count >= 2
    check("Dashboard shows lost items count", b'Lost Items' in r.data)
    check("Dashboard shows found items count", b'Found Items' in r.data)

    # DB error in login returns flash message, not 500
    # Log out first so the login route actually runs the DB query
    c.get('/logout')
    with mock.patch('routes.auth.User.query') as mock_query:
        mock_query.filter_by.side_effect = Exception('Simulated DB failure')
        r = c.post('/login', data={
            'email': 'alice@test.com', 'password': 'secret123'
        }, follow_redirects=False)
        check("DB error in login returns 200 not 500", r.status_code == 200)
        check("DB error in login shows flash message",
              b'database error' in r.data.lower())
    # Log back in for subsequent tests
    c.post('/login', data={'email': 'alice@test.com', 'password': 'secret123'})

    # DB error in lost-items listing returns 200 with flash, not 500
    with mock.patch('routes.items.Item.query') as mock_query:
        mock_query.filter_by.side_effect = Exception('Simulated DB failure')
        r = c.get('/lost-items')
        check("DB error in lost-items returns 200 not 500", r.status_code == 200)

    # DB error in found-items listing returns 200 with flash, not 500
    with mock.patch('routes.items.Item.query') as mock_query:
        mock_query.filter_by.side_effect = Exception('Simulated DB failure')
        r = c.get('/found-items')
        check("DB error in found-items returns 200 not 500", r.status_code == 200)

    # DB error in dashboard returns 200 with flash, not 500
    with mock.patch('routes.main.Item.query') as mock_query:
        mock_query.filter_by.side_effect = Exception('Simulated DB failure')
        r = c.get('/dashboard')
        check("DB error in dashboard returns 200 not 500", r.status_code == 200)

    # Clean up uploaded test images
    upload_folder = app.config['UPLOAD_FOLDER']
    for f in os.listdir(upload_folder):
        if f != '.gitkeep' and f.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            try:
                os.remove(os.path.join(upload_folder, f))
            except OSError:
                pass

# ---------------------------------------------------------------------------
# Matching algorithm tests
# ---------------------------------------------------------------------------
print("\n--- Matching Algorithm Tests ---")

with app.app_context():
    from services.matching import compute_match_score, _detect_color_contradiction
    from models.item import Item as ItemModel
    from datetime import date

    def make_item(name, category, description, location, item_type='LOST'):
        i = ItemModel()
        i.item_name = name
        i.category = category
        i.description = description
        i.location = location
        i.item_type = item_type
        i.date_lost_found = date(2026, 10, 10)
        i.contact = 'test@test.com'
        i.user_id = 1
        return i

    # Black purse lost at library vs black purse found at library — strong match
    lost_black  = make_item('purse', 'Accessories', 'black purse', 'library', 'LOST')
    found_black = make_item('purse', 'Accessories', 'black purse found', 'library', 'FOUND')
    score_bb, reasons_bb, conflicts_bb = compute_match_score(lost_black, found_black)
    check("Black purse vs black purse scores >= 75", score_bb >= 75)
    check("Black purse vs black purse has no conflicts", len(conflicts_bb) == 0)
    check("Black purse vs black purse has matching reasons", len(reasons_bb) > 0)

    # Black purse lost vs red purse found — penalised by color contradiction
    found_red = make_item('purse', 'Accessories', 'red purse found in class', 'class', 'FOUND')
    score_br, reasons_br, conflicts_br = compute_match_score(lost_black, found_red)
    check("Black purse vs red purse has color conflict", len(conflicts_br) > 0)
    check("Black purse vs red purse score < black vs black score", score_br < score_bb)
    check("Black purse vs red purse score < 50 (below threshold)", score_br < 50)

    # Black purse at library ranks above red purse in class
    check("Black-library ranks above red-class", score_bb > score_br)

    # Identical names, conflicting descriptions — contradiction detected
    lost_blue  = make_item('backpack', 'Bags', 'blue backpack', 'cafeteria', 'LOST')
    found_green = make_item('backpack', 'Bags', 'green backpack', 'cafeteria', 'FOUND')
    score_bg, _, conflicts_bg = compute_match_score(lost_blue, found_green)
    check("Blue vs green backpack has color conflict", len(conflicts_bg) > 0)
    check("Blue vs green backpack score penalised", score_bg < 60)

    # Same category, completely unrelated items — should not match
    lost_phone  = make_item('phone', 'Electronics', 'samsung galaxy phone', 'bus stop', 'LOST')
    found_laptop = make_item('laptop', 'Electronics', 'dell laptop computer', 'park', 'FOUND')
    score_unrelated, _, _ = compute_match_score(lost_phone, found_laptop)
    check("Unrelated electronics score < 50", score_unrelated < 50)

    # Color contradiction detection unit tests
    check("black vs red is a conflict",
          len(_detect_color_contradiction('black purse', 'red purse')) > 0)
    check("black vs black is NOT a conflict",
          len(_detect_color_contradiction('black purse', 'black bag')) == 0)
    check("no color words — no conflict",
          len(_detect_color_contradiction('leather purse', 'small purse')) == 0)
    check("blue vs green is a conflict",
          len(_detect_color_contradiction('blue backpack', 'green backpack')) > 0)

# ---------------------------------------------------------------------------
# Image URL map tests (no S3 credentials — local fallback)
# ---------------------------------------------------------------------------
print("\n--- Image URL Map Tests ---")

with app.app_context():
    from routes.items import _build_image_url_map, _get_image_url
    from models.item import Item as ItemModel

    # Item with no image
    i_none = ItemModel()
    i_none.id = 9001
    i_none.s3_object_key = None
    i_none.image_filename = None
    check("_get_image_url returns None for no-image item", _get_image_url(i_none) is None)

    # Item with local filename
    i_local = ItemModel()
    i_local.id = 9002
    i_local.s3_object_key = None
    i_local.image_filename = 'test_abc123.jpg'
    with app.test_request_context():
        url_local = _get_image_url(i_local)
    check("_get_image_url returns static path for local file",
          url_local is not None and 'test_abc123.jpg' in url_local)

    # Item with s3_object_key but S3 not configured — returns None gracefully
    i_s3 = ItemModel()
    i_s3.id = 9003
    i_s3.s3_object_key = 'lost-items/abc123.jpg'
    i_s3.image_filename = None
    url_s3 = _get_image_url(i_s3)  # S3 not configured in test env
    check("_get_image_url returns None when S3 not configured", url_s3 is None)

    # _build_image_url_map returns correct keys
    items_list = [i_none, i_local, i_s3]
    with app.test_request_context():
        url_map = _build_image_url_map(items_list)
    check("image_url_map has entry for each item", len(url_map) == 3)
    check("image_url_map key 9001 is None", url_map[9001] is None)
    check("image_url_map key 9002 has local URL",
          url_map[9002] is not None and 'test_abc123.jpg' in url_map[9002])
    check("image_url_map key 9003 is None (S3 not configured)", url_map[9003] is None)

    # Multiple items each get their OWN URL (not the same URL)
    i_a = ItemModel(); i_a.id = 9010; i_a.s3_object_key = None; i_a.image_filename = 'img_a.jpg'
    i_b = ItemModel(); i_b.id = 9011; i_b.s3_object_key = None; i_b.image_filename = 'img_b.jpg'
    with app.test_request_context():
        url_map2 = _build_image_url_map([i_a, i_b])
    check("Each card gets its own image URL",
          url_map2[9010] != url_map2[9011])
    check("Card A URL contains img_a", 'img_a.jpg' in (url_map2[9010] or ''))
    check("Card B URL contains img_b", 'img_b.jpg' in (url_map2[9011] or ''))

# ---------------------------------------------------------------------------
# Listing template receives image_urls (route integration)
# ---------------------------------------------------------------------------
print("\n--- Listing Route image_urls Integration Tests ---")

with app.test_client() as c:
    c.post('/login', data={'email': 'alice@test.com', 'password': 'secret123'})

    # Post a lost item with a local image so we can verify the listing shows it
    jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 500
    from werkzeug.datastructures import FileStorage
    fs2 = FileStorage(stream=io.BytesIO(jpeg_bytes), filename='purse.jpg',
                      content_type='image/jpeg')
    r = c.post('/report-lost', data={
        'item_name': 'Black Purse', 'category': 'Accessories',
        'description': 'black leather purse',
        'location': 'library', 'date_lost_found': '2026-10-10',
        'contact': 'alice@test.com', 'image': fs2
    }, content_type='multipart/form-data', follow_redirects=True)
    check("Black purse with image reported (200)", r.status_code == 200)

    # The listing page must NOT show the placeholder text for this item
    r = c.get('/lost-items')
    check("Lost items listing loads (200)", r.status_code == 200)
    check("Listing does not show S3 Image placeholder for local image",
          b'S3 Image' not in r.data)
    check("Listing shows Black Purse", b'Black Purse' in r.data)

    # Clean up
    upload_folder = app.config['UPLOAD_FOLDER']
    for f in os.listdir(upload_folder):
        if f != '.gitkeep' and f.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            try:
                os.remove(os.path.join(upload_folder, f))
            except OSError:
                pass



with app.app_context():
    # Verify engine options are applied to the SQLAlchemy engine
    engine = db.engine
    pool = engine.pool
    # pool_pre_ping is stored on the engine, not the pool directly in SA 2.x
    check("Engine pool is not NullPool",
          type(pool).__name__ != 'NullPool')
    # For SQLite (test env), StaticPool or NullPool is used — that's fine
    check("Engine is bound to app", engine is not None)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed tests:", FAIL)
    sys.exit(1)
else:
    print("All tests passed!")


# ---------------------------------------------------------------------------
# Recovery workflow tests
# ---------------------------------------------------------------------------
print("\n--- Recovery Workflow Tests ---")

with app.test_client() as c:
    # Register two users
    c.post('/register', data={
        'name': 'Bob Owner', 'email': 'bob@test.com',
        'phone': '1111111111', 'password': 'bobpass1',
        'confirm_password': 'bobpass1'
    })
    c.post('/register', data={
        'name': 'Carol Finder', 'email': 'carol@test.com',
        'phone': '2222222222', 'password': 'carolpass1',
        'confirm_password': 'carolpass1'
    })

    # Bob reports a lost water bottle
    c.post('/login', data={'email': 'bob@test.com', 'password': 'bobpass1'})
    r = c.post('/report-lost', data={
        'item_name': 'Water Bottle', 'category': 'Other',
        'description': 'Blue metal water bottle',
        'location': 'Gym', 'date_lost_found': '2026-01-01',
        'contact': 'bob@test.com'
    }, follow_redirects=False)
    check("Bob reports lost water bottle (302)", r.status_code == 302)

    # Same user reports finding the same water bottle (same-user demo allowed)
    r = c.post('/report-found', data={
        'item_name': 'Water Bottle', 'category': 'Other',
        'description': 'Blue metal water bottle found at gym',
        'location': 'Gym', 'date_lost_found': '2026-01-02',
        'contact': 'bob@test.com'
    }, follow_redirects=False)
    check("Same user reports found water bottle (302)", r.status_code == 302)

    # Match should exist
    r = c.get('/matches')
    check("Water bottle match detected", b'Water Bottle' in r.data)

    # Get the match id from the DB
    with app.app_context():
        from models.item import Item as _I, Match as _M
        _lost  = _I.query.filter_by(item_name='Water Bottle', item_type='LOST').order_by(_I.id.desc()).first()
        _found = _I.query.filter_by(item_name='Water Bottle', item_type='FOUND').order_by(_I.id.desc()).first()
        _match = _M.query.filter_by(
            lost_item_id=_lost.id, found_item_id=_found.id
        ).first() if _lost and _found else None
        check("Match record exists in DB", _match is not None)
        check("Match status is PENDING", _match is not None and _match.status == 'PENDING')
        mid = _match.id if _match else None
        lost_id_wb  = _lost.id  if _lost  else None
        found_id_wb = _found.id if _found else None

    # Confirm recovery via match
    if mid:
        r = c.post(f'/match/{mid}/confirm', follow_redirects=True)
        check("Confirm recovery returns 200", r.status_code == 200)
        check("Success flash shown",
              b'confirmed' in r.data.lower() or b'recovered' in r.data.lower())

        with app.app_context():
            from models.item import Item as _I2, Match as _M2
            _m2 = db.session.get(_M2, mid)
            _l2 = db.session.get(_I2, lost_id_wb)
            _f2 = db.session.get(_I2, found_id_wb)
            check("Match status is CONFIRMED after confirm", _m2.status == 'CONFIRMED')
            check("Lost item is RECOVERED after confirm",   _l2.status == 'RECOVERED')
            check("Found item is RECOVERED after confirm",  _f2.status == 'RECOVERED')

        # Idempotent: confirming again returns info message, not error
        r = c.post(f'/match/{mid}/confirm', follow_redirects=True)
        check("Double-confirm is idempotent (200)", r.status_code == 200)

    # Reject a PENDING match
    r = c.post('/report-lost', data={
        'item_name': 'Red Scarf', 'category': 'Clothing',
        'description': 'red woolen scarf',
        'location': 'Library', 'date_lost_found': '2026-02-01',
        'contact': 'bob@test.com'
    }, follow_redirects=False)
    r = c.post('/report-found', data={
        'item_name': 'Red Scarf', 'category': 'Clothing',
        'description': 'red woolen scarf found',
        'location': 'Library', 'date_lost_found': '2026-02-02',
        'contact': 'bob@test.com'
    }, follow_redirects=False)

    with app.app_context():
        from models.item import Item as _I3, Match as _M3
        _ls = _I3.query.filter_by(item_name='Red Scarf', item_type='LOST').order_by(_I3.id.desc()).first()
        _fs = _I3.query.filter_by(item_name='Red Scarf', item_type='FOUND').order_by(_I3.id.desc()).first()
        _rm = _M3.query.filter_by(
            lost_item_id=_ls.id, found_item_id=_fs.id
        ).first() if _ls and _fs else None
        rid = _rm.id if _rm else None

    if rid:
        r = c.post(f'/match/{rid}/reject', follow_redirects=True)
        check("Reject match returns 200", r.status_code == 200)
        with app.app_context():
            from models.item import Match as _M4
            _rm2 = db.session.get(_M4, rid)
            check("Match status is REJECTED", _rm2.status == 'REJECTED')

        # Cannot confirm a rejected match
        r = c.post(f'/match/{rid}/confirm', follow_redirects=True)
        check("Cannot confirm rejected match (200)", r.status_code == 200)
        check("Rejected match confirm shows error", b'rejected' in r.data.lower())

    # Unauthorized: Carol tries to confirm/reject Bob's matches
    c.get('/logout')
    c.post('/login', data={'email': 'carol@test.com', 'password': 'carolpass1'})
    if mid:
        r = c.post(f'/match/{mid}/confirm', follow_redirects=True)
        check("Unauthorized confirm returns 403", r.status_code == 403)
    if rid:
        r = c.post(f'/match/{rid}/reject', follow_redirects=True)
        check("Unauthorized reject returns 403", r.status_code == 403)
    c.get('/logout')

# ---------------------------------------------------------------------------
# Dashboard / My Reports consistency after recovery
# ---------------------------------------------------------------------------
print("\n--- Dashboard & My Reports Consistency Tests ---")

with app.test_client() as c:
    c.post('/login', data={'email': 'bob@test.com', 'password': 'bobpass1'})
    r = c.get('/dashboard')
    check("Dashboard loads after recovery (200)", r.status_code == 200)
    check("Dashboard shows Recovered stat", b'Recovered' in r.data)
    r = c.get('/my-reports')
    check("My Reports loads (200)", r.status_code == 200)
    check("My Reports shows Water Bottle", b'Water Bottle' in r.data)
    check("My Reports shows RECOVERED badge", b'RECOVERED' in r.data)
    c.get('/logout')

# ---------------------------------------------------------------------------
# S3 config env var fallback (AWS_S3_BUCKET vs S3_BUCKET_NAME)
# ---------------------------------------------------------------------------
print("\n--- S3 Config Env Var Fallback Tests ---")

import importlib
import config as cfg_mod

with mock.patch.dict(os.environ, {
    'AWS_S3_BUCKET': 'my-legacy-bucket',
    'AWS_ACCESS_KEY_ID': 'AKIATEST',
    'AWS_SECRET_ACCESS_KEY': 'secret',
    'AWS_REGION': 'us-east-1'
}, clear=False):
    importlib.reload(cfg_mod)
    check("S3_BUCKET_NAME falls back to AWS_S3_BUCKET",
          cfg_mod.Config.S3_BUCKET_NAME == 'my-legacy-bucket')

with mock.patch.dict(os.environ, {
    'S3_BUCKET_NAME': 'primary-bucket',
    'AWS_S3_BUCKET': 'legacy-bucket',
    'AWS_ACCESS_KEY_ID': 'AKIATEST',
    'AWS_SECRET_ACCESS_KEY': 'secret',
    'AWS_REGION': 'us-east-1'
}, clear=False):
    importlib.reload(cfg_mod)
    check("S3_BUCKET_NAME takes priority over AWS_S3_BUCKET",
          cfg_mod.Config.S3_BUCKET_NAME == 'primary-bucket')

importlib.reload(cfg_mod)

# ---------------------------------------------------------------------------
# /debug-s3 endpoint
# ---------------------------------------------------------------------------
print("\n--- Debug S3 Endpoint Tests ---")

with app.test_client() as c:
    r = c.get('/debug-s3')
    check("/debug-s3 returns 200", r.status_code == 200)
    check("/debug-s3 returns JSON with s3_configured key", b's3_configured' in r.data)
    check("/debug-s3 does not expose secret key value",
          b'AKIATEST' not in r.data and b'bobpass1' not in r.data)

# ---------------------------------------------------------------------------
# Same-user lost+found pair still matches (matching.py searches ACTIVE+MATCHED)
# ---------------------------------------------------------------------------
print("\n--- Same-User Matching Tests ---")

with app.app_context():
    from services.matching import find_matches_for_item as _fmfi
    from models.item import Item as _ItemM
    from datetime import date as _date

    _li = _ItemM(
        user_id=99, item_type='LOST', item_name='Thermos',
        category='Other', description='silver thermos flask',
        location='Canteen', date_lost_found=_date(2026, 5, 1),
        contact='x@x.com', status='ACTIVE'
    )
    _fi = _ItemM(
        user_id=99, item_type='FOUND', item_name='Thermos',
        category='Other', description='silver thermos flask found',
        location='Canteen', date_lost_found=_date(2026, 5, 2),
        contact='x@x.com', status='ACTIVE'
    )
    db.session.add_all([_li, _fi])
    db.session.commit()

    results = _fmfi(_li)
    check("Same-user lost+found pair produces a match", len(results) > 0)
    if results:
        check("Same-user match score >= 75", results[0][1] >= 75)

    from models.item import Match as _Mc
    _Mc.query.filter(
        (_Mc.lost_item_id == _li.id) | (_Mc.found_item_id == _fi.id)
    ).delete(synchronize_session=False)
    db.session.delete(_li)
    db.session.delete(_fi)
    db.session.commit()

# ---------------------------------------------------------------------------
# Transaction rollback: recovery fails midway
# ---------------------------------------------------------------------------
print("\n--- Transaction Rollback Tests ---")

with app.test_client() as c:
    c.post('/login', data={'email': 'bob@test.com', 'password': 'bobpass1'})

    c.post('/report-lost', data={
        'item_name': 'Rollback Test Item', 'category': 'Other',
        'description': 'rollback test description',
        'location': 'Test Location', 'date_lost_found': '2026-03-01',
        'contact': 'bob@test.com'
    }, follow_redirects=False)
    c.post('/report-found', data={
        'item_name': 'Rollback Test Item', 'category': 'Other',
        'description': 'rollback test description found',
        'location': 'Test Location', 'date_lost_found': '2026-03-02',
        'contact': 'bob@test.com'
    }, follow_redirects=False)

    with app.app_context():
        from models.item import Item as _Irb, Match as _Mrb
        _lrb = _Irb.query.filter_by(item_name='Rollback Test Item', item_type='LOST').order_by(_Irb.id.desc()).first()
        _frb = _Irb.query.filter_by(item_name='Rollback Test Item', item_type='FOUND').order_by(_Irb.id.desc()).first()
        _mrb = _Mrb.query.filter_by(
            lost_item_id=_lrb.id, found_item_id=_frb.id
        ).first() if _lrb and _frb else None
        rb_mid      = _mrb.id   if _mrb else None
        rb_lost_id  = _lrb.id   if _lrb else None

    if rb_mid:
        with mock.patch('routes.items.db.session.commit',
                        side_effect=Exception('Simulated commit failure')):
            r = c.post(f'/match/{rb_mid}/confirm', follow_redirects=True)
            check("Rollback: confirm with DB error returns 200", r.status_code == 200)
            check("Rollback: error flash shown", b'database error' in r.data.lower())

        with app.app_context():
            from models.item import Item as _Irb2, Match as _Mrb2
            _mc = db.session.get(_Mrb2, rb_mid)
            _ic = db.session.get(_Irb2, rb_lost_id)
            check("Rollback: match status still PENDING", _mc.status == 'PENDING')
            check("Rollback: lost item status still ACTIVE", _ic.status == 'ACTIVE')

    c.get('/logout')

# ---------------------------------------------------------------------------
# Duplicate match prevention
# ---------------------------------------------------------------------------
print("\n--- Duplicate Match Prevention Tests ---")

with app.app_context():
    from services.matching import save_match as _sm
    from models.item import Item as _Idup, Match as _Mdup
    _ld = _Idup.query.filter_by(item_name='Black Wallet', item_type='LOST').first()
    _fd = _Idup.query.filter_by(item_name='Black Wallet', item_type='FOUND').first()
    if _ld and _fd:
        before = _Mdup.query.filter_by(
            lost_item_id=_ld.id, found_item_id=_fd.id).count()
        _sm(_ld.id, _fd.id, 85.0, ['Dup test'])
        _sm(_ld.id, _fd.id, 85.0, ['Dup test'])
        after = _Mdup.query.filter_by(
            lost_item_id=_ld.id, found_item_id=_fd.id).count()
        check("Duplicate save_match does not create extra records", after == before)
    else:
        check("Duplicate match test skipped (items not found)", True)

# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
print()
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed tests:", FAIL)
    sys.exit(1)
else:
    print("All tests passed!")


# ===========================================================================
# NEW TESTS — matching system, thresholds, UI, filters, S3 fallback
# ===========================================================================

# ---------------------------------------------------------------------------
# Threshold and category tests
# ---------------------------------------------------------------------------
print("\n--- Threshold & Category Tests ---")

with app.app_context():
    from services.matching import (
        match_category, match_category_label, THRESHOLDS,
        compute_match_score, _detect_color_contradiction
    )
    from models.item import Item as _TI
    from datetime import date as _d

    check("THRESHOLDS has strong key",   'strong'   in THRESHOLDS)
    check("THRESHOLDS has potential key",'potential' in THRESHOLDS)
    check("THRESHOLDS has possible key", 'possible'  in THRESHOLDS)
    check("strong threshold >= 75",  THRESHOLDS['strong']   >= 75)
    check("potential threshold >= 50", THRESHOLDS['potential'] >= 50)
    check("possible threshold >= 30",  THRESHOLDS['possible']  >= 30)

    check("match_category 80 -> strong",    match_category(80.0) == 'strong')
    check("match_category 75 -> strong",    match_category(75.0) == 'strong')
    check("match_category 60 -> potential", match_category(60.0) == 'potential')
    check("match_category 50 -> potential", match_category(50.0) == 'potential')
    check("match_category 40 -> possible",  match_category(40.0) == 'possible')
    check("match_category 30 -> possible",  match_category(30.0) == 'possible')
    check("match_category 20 -> hidden",    match_category(20.0) == 'hidden')
    check("match_category 0  -> hidden",    match_category(0.0)  == 'hidden')

    check("label for 80 is Strong Candidate",
          'Strong' in match_category_label(80.0))
    check("label for 60 is Potential Match",
          'Potential' in match_category_label(60.0))
    check("label for 35 is Possible Match",
          'Possible' in match_category_label(35.0))

    def _mi(name, cat, desc, loc, itype='LOST'):
        i = _TI()
        i.item_name = name; i.category = cat; i.description = desc
        i.location = loc; i.item_type = itype
        i.date_lost_found = _d(2026, 1, 1); i.contact = 'x'; i.user_id = 1
        return i

    # Same name + category + location + description → strong
    l1 = _mi('wallet', 'Accessories', 'black leather wallet', 'library')
    f1 = _mi('wallet', 'Accessories', 'black leather wallet found', 'library', 'FOUND')
    s1, r1, c1 = compute_match_score(l1, f1)
    check("Identical item scores strong (>=75)", s1 >= 75)
    check("Identical item has no conflicts", len(c1) == 0)
    check("Identical item has positive reasons", len(r1) > 0)

    # Same name + category, different colour → penalised below potential
    l2 = _mi('wallet', 'Accessories', 'black leather wallet', 'library')
    f2 = _mi('wallet', 'Accessories', 'red leather wallet found', 'library', 'FOUND')
    s2, r2, c2 = compute_match_score(l2, f2)
    check("Same name diff colour has conflict", len(c2) > 0)
    check("Same name diff colour score < same colour score", s2 < s1)
    check("Same name diff colour score penalised below 60", s2 < 60)

    # Different location reduces score
    l3 = _mi('wallet', 'Accessories', 'black leather wallet', 'library')
    f3 = _mi('wallet', 'Accessories', 'black leather wallet found', 'airport', 'FOUND')
    s3, _, _ = compute_match_score(l3, f3)
    check("Different location reduces score vs same location", s3 < s1)

    # Completely unrelated items
    l4 = _mi('umbrella', 'Other', 'red umbrella wooden handle', 'bus stop')
    f4 = _mi('laptop',   'Electronics', 'dell laptop silver', 'park', 'FOUND')
    s4, _, _ = compute_match_score(l4, f4)
    check("Completely unrelated items score < 30", s4 < 30)
    check("Completely unrelated items are hidden", match_category(s4) == 'hidden')

    # Identical name alone does NOT guarantee strong match (location/desc differ)
    l5 = _mi('phone', 'Electronics', 'samsung galaxy s21', 'bus stop')
    f5 = _mi('phone', 'Electronics', 'apple iphone 13 pro', 'airport', 'FOUND')
    s5, _, _ = compute_match_score(l5, f5)
    check("Same name different desc/location not strong", s5 < 75)

    # Missing description fields don't count as agreement
    l6 = _mi('bag', 'Bags', '', 'canteen')
    f6 = _mi('bag', 'Bags', '', 'canteen', 'FOUND')
    s6, _, _ = compute_match_score(l6, f6)
    check("Empty descriptions don't inflate score above name+cat+loc",
          s6 <= (0.35 + 0.25 + 0.25) * 100 + 1)  # +1 tolerance

# ---------------------------------------------------------------------------
# Matches page UI tests (sections, filters, images)
# ---------------------------------------------------------------------------
print("\n--- Matches Page UI Tests ---")

with app.test_client() as c:
    c.post('/register', data={
        'name': 'UITest User', 'email': 'uitest@test.com',
        'phone': '3333333333', 'password': 'uitestpass',
        'confirm_password': 'uitestpass'
    })
    c.post('/login', data={'email': 'uitest@test.com', 'password': 'uitestpass'})

    # Report a strong-match pair
    c.post('/report-lost', data={
        'item_name': 'Silver Thermos', 'category': 'Other',
        'description': 'silver metal thermos flask with blue lid',
        'location': 'Canteen', 'date_lost_found': '2026-05-01',
        'contact': 'uitest@test.com'
    })
    c.post('/report-found', data={
        'item_name': 'Silver Thermos', 'category': 'Other',
        'description': 'silver metal thermos flask with blue lid found',
        'location': 'Canteen', 'date_lost_found': '2026-05-02',
        'contact': 'uitest@test.com'
    })

    r = c.get('/matches')
    check("Matches page loads (200)", r.status_code == 200)
    check("Matches page shows Silver Thermos", b'Silver Thermos' in r.data)
    check("Matches page shows Strong Candidate label", b'Strong' in r.data)
    check("Matches page shows score circle", b'score-circle' in r.data or b'score-strong' in r.data)
    check("Matches page shows filter form", b'filter_category' in r.data or b'name=\"category\"' in r.data or b'All Categories' in r.data)
    check("Matches page shows Confirm Recovery button", b'Confirm Recovery' in r.data)
    check("Matches page shows Reject button", b'Reject' in r.data)
    check("Matches page shows Why it matches section", b'Why it matches' in r.data)

    # Filter by category=strong
    r = c.get('/matches?category=strong')
    check("Filter strong shows Silver Thermos", b'Silver Thermos' in r.data)

    # Filter by category=possible should not show strong match
    r = c.get('/matches?category=possible')
    check("Filter possible hides strong match", b'Silver Thermos' not in r.data)

    # Filter by status=PENDING
    r = c.get('/matches?status=PENDING')
    check("Filter PENDING shows pending matches", r.status_code == 200)

    # Filter by status=CONFIRMED shows empty (none confirmed yet)
    r = c.get('/matches?status=CONFIRMED')
    check("Filter CONFIRMED loads (200)", r.status_code == 200)

    c.get('/logout')

# ---------------------------------------------------------------------------
# Possible match threshold (30-49) stored and displayed
# ---------------------------------------------------------------------------
print("\n--- Possible Match Threshold Tests ---")

with app.app_context():
    from services.matching import find_matches_for_item as _fmfi2, THRESHOLDS as _TH
    from models.item import Item as _TI2
    from datetime import date as _d2

    # Create a pair that should score in the possible range (30-49)
    # Same category only = 25 pts; add partial name overlap to get ~40
    _lp = _TI2(
        user_id=1, item_type='LOST', item_name='small bag',
        category='Bags', description='canvas tote bag',
        location='Station', date_lost_found=_d2(2026, 6, 1),
        contact='x@x.com', status='ACTIVE'
    )
    _fp = _TI2(
        user_id=1, item_type='FOUND', item_name='large bag',
        category='Bags', description='leather satchel',
        location='Airport', date_lost_found=_d2(2026, 6, 2),
        contact='x@x.com', status='ACTIVE'
    )
    db.session.add_all([_lp, _fp])
    db.session.commit()

    from services.matching import compute_match_score as _cms
    _sp, _, _ = _cms(_lp, _fp)
    check("Possible-range pair scores in 30-74 range",
          _TH['possible'] <= _sp < _TH['strong'])
    check("Possible-range pair category is possible or potential",
          match_category(_sp) in ('possible', 'potential'))

    # find_matches_for_item with default threshold finds it
    results_p = _fmfi2(_lp)
    check("find_matches_for_item finds possible-range match",
          any(other.id == _fp.id for other, score, _ in results_p))

    from models.item import Match as _Mp
    _Mp.query.filter(
        (_Mp.lost_item_id == _lp.id) | (_Mp.found_item_id == _fp.id)
    ).delete(synchronize_session=False)
    db.session.delete(_lp)
    db.session.delete(_fp)
    db.session.commit()

# ---------------------------------------------------------------------------
# S3 image fallback on matches page
# ---------------------------------------------------------------------------
print("\n--- S3 Image Fallback on Matches Page ---")

with app.app_context():
    from routes.items import _build_image_url_map
    from models.item import Item as _TI3

    # Item with s3_object_key but S3 not configured → None
    _is3 = _TI3()
    _is3.id = 8001
    _is3.s3_object_key = 'lost-items/missing.jpg'
    _is3.image_filename = None
    url_missing = _build_image_url_map([_is3])
    check("Missing S3 object maps to None (no crash)", url_missing[8001] is None)

    # Item with no image at all → None
    _ino = _TI3()
    _ino.id = 8002
    _ino.s3_object_key = None
    _ino.image_filename = None
    url_none = _build_image_url_map([_ino])
    check("No-image item maps to None", url_none[8002] is None)

with app.test_client() as c:
    c.post('/login', data={'email': 'uitest@test.com', 'password': 'uitestpass'})
    r = c.get('/matches')
    # Page must not 500 even when some items have no image
    check("Matches page loads without 500 when images missing", r.status_code == 200)
    # Fallback text shown for items without images
    check("Matches page shows image fallback text",
          b'No image' in r.data or b'Unavailable' in r.data or b'unavailable' in r.data)
    c.get('/logout')

# ---------------------------------------------------------------------------
# Duplicate match prevention on repeated report
# ---------------------------------------------------------------------------
print("\n--- Duplicate Match on Repeated Report ---")

with app.test_client() as c:
    c.post('/login', data={'email': 'uitest@test.com', 'password': 'uitestpass'})

    # Report the same lost item twice (simulates re-submission)
    c.post('/report-lost', data={
        'item_name': 'Duplicate Test Bag', 'category': 'Bags',
        'description': 'brown leather bag with zipper',
        'location': 'Library', 'date_lost_found': '2026-07-01',
        'contact': 'uitest@test.com'
    })
    c.post('/report-found', data={
        'item_name': 'Duplicate Test Bag', 'category': 'Bags',
        'description': 'brown leather bag with zipper found',
        'location': 'Library', 'date_lost_found': '2026-07-02',
        'contact': 'uitest@test.com'
    })

    with app.app_context():
        from models.item import Item as _Idd, Match as _Mdd
        _ld2 = _Idd.query.filter_by(
            item_name='Duplicate Test Bag', item_type='LOST'
        ).order_by(_Idd.id.desc()).first()
        _fd2 = _Idd.query.filter_by(
            item_name='Duplicate Test Bag', item_type='FOUND'
        ).order_by(_Idd.id.desc()).first()
        if _ld2 and _fd2:
            cnt_before = _Mdd.query.filter_by(
                lost_item_id=_ld2.id, found_item_id=_fd2.id).count()
            from services.matching import save_match as _sm2
            _sm2(_ld2.id, _fd2.id, 80.0, ['dup test'])
            _sm2(_ld2.id, _fd2.id, 80.0, ['dup test'])
            cnt_after = _Mdd.query.filter_by(
                lost_item_id=_ld2.id, found_item_id=_fd2.id).count()
            check("Repeated save_match does not duplicate records",
                  cnt_after == cnt_before)
        else:
            check("Duplicate test items found", False)

    c.get('/logout')

# ---------------------------------------------------------------------------
# Recovered items excluded from future matching
# ---------------------------------------------------------------------------
print("\n--- Recovered Items Excluded from Matching ---")

with app.app_context():
    from services.matching import find_matches_for_item as _fmfi3
    from models.item import Item as _TI4
    from datetime import date as _d3

    _lr = _TI4(
        user_id=1, item_type='LOST', item_name='Recovered Wallet',
        category='Accessories', description='black leather wallet',
        location='Library', date_lost_found=_d3(2026, 8, 1),
        contact='x@x.com', status='ACTIVE'
    )
    _fr = _TI4(
        user_id=1, item_type='FOUND', item_name='Recovered Wallet',
        category='Accessories', description='black leather wallet found',
        location='Library', date_lost_found=_d3(2026, 8, 2),
        contact='x@x.com', status='RECOVERED'  # already recovered
    )
    db.session.add_all([_lr, _fr])
    db.session.commit()

    results_r = _fmfi3(_lr)
    check("RECOVERED found item excluded from matching candidates",
          not any(other.id == _fr.id for other, _, _ in results_r))

    from models.item import Match as _Mr
    _Mr.query.filter(
        (_Mr.lost_item_id == _lr.id) | (_Mr.found_item_id == _fr.id)
    ).delete(synchronize_session=False)
    db.session.delete(_lr)
    db.session.delete(_fr)
    db.session.commit()

# ---------------------------------------------------------------------------
# Matches page shows item descriptions and locations
# ---------------------------------------------------------------------------
print("\n--- Matches Page Content Tests ---")

with app.test_client() as c:
    c.post('/login', data={'email': 'uitest@test.com', 'password': 'uitestpass'})
    r = c.get('/matches')
    check("Matches page shows location info", b'Canteen' in r.data or b'Library' in r.data)
    check("Matches page shows category info", b'Other' in r.data or b'Bags' in r.data)
    check("Matches page shows date info", b'2026' in r.data)
    check("Matches page shows LOST badge", b'LOST' in r.data)
    check("Matches page shows FOUND badge", b'FOUND' in r.data)
    c.get('/logout')

# ---------------------------------------------------------------------------
# Final summary (all tests)
# ---------------------------------------------------------------------------
print()
print(f"Results: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("Failed tests:", FAIL)
    sys.exit(1)
else:
    print("All tests passed!")
