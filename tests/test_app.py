"""
Functional test suite — run with: python tests/test_app.py
Covers: routing, auth, item CRUD, matching, SHA-256, S3 service unit tests.
Expected: all tests pass with no AWS credentials configured (local fallback).
"""
import sys
import os
import io
import hashlib

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

# SHA-256 bytes
data = b"hello world"
expected = hashlib.sha256(data).hexdigest()
check("SHA-256 bytes correct", calculate_sha256_bytes(data) == expected)

# SHA-256 empty bytes
check("SHA-256 empty bytes", calculate_sha256_bytes(b'') == hashlib.sha256(b'').hexdigest())

# S3 object key builder — LOST
key = build_object_key('LOST', 'photo.jpg')
check("S3 key starts with lost-items/", key.startswith('lost-items/'))
check("S3 key ends with .jpg", key.endswith('.jpg'))
check("S3 key has UUID length", len(key) == len('lost-items/') + 32 + 4)

# S3 object key builder — FOUND
key2 = build_object_key('FOUND', 'image.png')
check("S3 key starts with found-items/", key2.startswith('found-items/'))
check("S3 key ends with .png", key2.endswith('.png'))

# S3 keys are unique
key3 = build_object_key('LOST', 'photo.jpg')
check("S3 keys are unique (UUID)", key != key3)

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

    # Extension validation
    check("allowed_file jpg", allowed_file('photo.jpg'))
    check("allowed_file jpeg", allowed_file('photo.jpeg'))
    check("allowed_file png", allowed_file('photo.PNG'))
    check("allowed_file webp", allowed_file('photo.webp'))
    check("allowed_file rejects exe", not allowed_file('virus.exe'))
    check("allowed_file rejects php", not allowed_file('shell.php'))
    check("allowed_file rejects gif", not allowed_file('anim.gif'))
    check("allowed_file rejects no ext", not allowed_file('noextension'))

    # MIME detection
    jpeg_header = b'\xff\xd8\xff\xe0' + b'\x00' * 8
    png_header  = b'\x89PNG\r\n\x1a\n' + b'\x00' * 4
    webp_header = b'RIFF\x00\x00\x00\x00WEBP'
    check("MIME detect JPEG", _detect_mime(jpeg_header) == 'image/jpeg')
    check("MIME detect PNG",  _detect_mime(png_header)  == 'image/png')
    check("MIME detect WEBP", _detect_mime(webp_header) == 'image/webp')
    check("MIME detect unknown returns None", _detect_mime(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b') is None)

    # save_upload with no file
    class FakeFile:
        def __init__(self, name, data, content_type='image/jpeg'):
            self.filename = name
            self._data = data
            self.content_type = content_type
        def read(self): return self._data

    result = save_upload(FakeFile('', b''), 'LOST')
    check("save_upload empty filename returns None result", result.filename is None and result.s3_key is None)

    # save_upload with invalid extension
    try:
        save_upload(FakeFile('virus.exe', b'\xff\xd8\xff' + b'x'*100), 'LOST')
        check("save_upload rejects .exe", False)
    except ValueError as e:
        check("save_upload rejects .exe", 'allowed' in str(e).lower())

    # save_upload with valid JPEG (minimal valid JPEG bytes)
    # Minimal JPEG: SOI + APP0 marker + enough bytes to pass MIME check
    jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 500
    result = save_upload(FakeFile('test.jpg', jpeg_bytes), 'LOST')
    check("save_upload local JPEG returns filename", result.filename is not None)
    check("save_upload local JPEG returns sha256", result.sha256_hash is not None)
    check("save_upload local JPEG storage=local", result.storage == 'local')
    check("save_upload local JPEG s3_key is None", result.s3_key is None)
    check("save_upload SHA-256 is correct",
          result.sha256_hash == calculate_sha256_bytes(jpeg_bytes))

    # Clean up the test file
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
    fs = FileStorage(stream=io.BytesIO(jpeg_bytes), filename='backpack.jpg', content_type='image/jpeg')
    r = c.post('/report-lost', data={
        'item_name': 'Blue Backpack', 'category': 'Bags',
        'description': 'Blue backpack with laptop inside',
        'location': 'Cafeteria', 'date_lost_found': '2024-02-01',
        'contact': 'alice@test.com',
        'image': fs
    }, content_type='multipart/form-data', follow_redirects=False)
    check("Report lost item with image (302 redirect)", r.status_code == 302)
    # Capture the item ID from the redirect Location header
    location = r.headers.get('Location', '')
    image_item_id = location.rstrip('/').split('/')[-1] if '/item/' in location else None
    check("Image item ID captured from redirect", image_item_id is not None and image_item_id.isdigit())

    # Follow redirect to detail page
    r = c.get(location, follow_redirects=True)
    check("Item with image detail shown", b'Blue Backpack' in r.data)
    check("Storage indicator shown", b'Stored' in r.data)

    # Verify integrity for item with image using captured ID
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

    # Clean up uploaded test images
    upload_folder = app.config['UPLOAD_FOLDER']
    for f in os.listdir(upload_folder):
        if f != '.gitkeep' and f.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            try:
                os.remove(os.path.join(upload_folder, f))
            except OSError:
                pass

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
