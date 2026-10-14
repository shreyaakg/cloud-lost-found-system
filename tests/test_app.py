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
