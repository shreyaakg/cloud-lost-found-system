import os
import logging
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, current_app)
from flask_login import login_required, current_user
from extensions import db
from models.item import Item, Match
from services.upload import save_upload
from services.integrity import calculate_sha256, calculate_sha256_bytes
from services.matching import find_matches_for_item, save_match

logger = logging.getLogger(__name__)

items_bp = Blueprint('items', __name__)

CATEGORIES = [
    'Electronics', 'Clothing', 'Accessories', 'Documents',
    'Keys', 'Bags', 'Jewellery', 'Books', 'Sports', 'Other'
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item_form_data():
    return {
        'item_name':       request.form.get('item_name', '').strip(),
        'category':        request.form.get('category', '').strip(),
        'description':     request.form.get('description', '').strip(),
        'location':        request.form.get('location', '').strip(),
        'date_lost_found': request.form.get('date_lost_found', '').strip(),
        'contact':         request.form.get('contact', '').strip(),
    }


def _validate_item(data):
    errors = []
    if not data['item_name']:       errors.append('Item name is required.')
    if not data['category']:        errors.append('Category is required.')
    if not data['description']:     errors.append('Description is required.')
    if not data['location']:        errors.append('Location is required.')
    if not data['date_lost_found']: errors.append('Date is required.')
    if not data['contact']:         errors.append('Contact is required.')
    return errors


def _handle_upload(file, item_type):
    """
    Validate and store an uploaded file.
    Returns (image_filename, s3_key, sha256_hash, errors_list).
    """
    image_filename = s3_key = sha256_hash = None
    errors = []

    if file and file.filename:
        try:
            result = save_upload(file, item_type)
            image_filename = result.filename
            s3_key         = result.s3_key
            sha256_hash    = result.sha256_hash
        except ValueError as e:
            errors.append(str(e))
        except RuntimeError as e:
            errors.append(str(e))

    return image_filename, s3_key, sha256_hash, errors


def _delete_stored_file(item):
    """Delete the file from whichever storage backend holds it."""
    if item.s3_object_key:
        from services.s3_service import is_s3_configured, delete_file
        if is_s3_configured():
            ok, err = delete_file(item.s3_object_key)
            if not ok:
                logger.warning('Could not delete S3 object %s: %s', item.s3_object_key, err)
    elif item.image_filename:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], item.image_filename)
        if os.path.exists(path):
            os.remove(path)


def _auto_match(item):
    """Run matching after an item is saved. Errors are logged, never propagated."""
    try:
        matches = find_matches_for_item(item)
        for other, score, reasons in matches:
            if item.item_type == 'LOST':
                save_match(item.id, other.id, score, reasons)
            else:
                save_match(other.id, item.id, score, reasons)
            if item.status == 'ACTIVE':
                item.status = 'MATCHED'
            if other.status == 'ACTIVE':
                other.status = 'MATCHED'
        if matches:
            db.session.commit()
    except Exception as exc:
        logger.error('Auto-match failed for item %s: %s', item.id, exc)
        db.session.rollback()


def _get_image_url(item):
    """Return the correct image URL for an item regardless of storage backend."""
    if item.s3_object_key:
        from services.s3_service import is_s3_configured, generate_presigned_url
        if is_s3_configured():
            url, err = generate_presigned_url(item.s3_object_key)
            if url:
                return url
            logger.warning('Could not generate presigned URL for %s: %s',
                           item.s3_object_key, err)
        return None
    elif item.image_filename:
        return url_for('static', filename='uploads/' + item.image_filename)
    return None


def _build_image_url_map(items):
    """
    Build {item.id: image_url} for a list of items in one pass.
    S3 presigned URLs are generated per-item so each card gets its own URL.
    Items with no image map to None.
    """
    return {item.id: _get_image_url(item) for item in items}


# ---------------------------------------------------------------------------
# Report routes
# ---------------------------------------------------------------------------

def _create_item(item_type):
    """Shared logic for report-lost and report-found POST handling."""
    data = _item_form_data()
    errors = _validate_item(data)

    image_filename, s3_key, sha256_hash, upload_errors = _handle_upload(
        request.files.get('image'), item_type
    )
    errors.extend(upload_errors)

    if errors:
        for e in errors:
            flash(e, 'danger')
        return render_template('items/report.html', item_type=item_type,
                               categories=CATEGORIES, **data), None

    try:
        item = Item(
            user_id=current_user.id,
            item_type=item_type,
            item_name=data['item_name'],
            category=data['category'],
            description=data['description'],
            location=data['location'],
            date_lost_found=datetime.strptime(data['date_lost_found'], '%Y-%m-%d').date(),
            contact=data['contact'],
            image_filename=image_filename,
            s3_object_key=s3_key,
            sha256_hash=sha256_hash,
            status='ACTIVE',
        )
        db.session.add(item)
        db.session.commit()
    except Exception as exc:
        logger.error('DB error saving %s item: %s', item_type, exc)
        db.session.rollback()
        flash('A database error occurred while saving your report. Please try again.', 'danger')
        return render_template('items/report.html', item_type=item_type,
                               categories=CATEGORIES, **data), None

    _auto_match(item)
    return None, item


@items_bp.route('/report-lost', methods=['GET', 'POST'])
@login_required
def report_lost():
    if request.method == 'POST':
        response, item = _create_item('LOST')
        if response is not None:
            return response
        flash('Lost item reported successfully.', 'success')
        return redirect(url_for('items.item_detail', item_id=item.id))
    return render_template('items/report.html', item_type='LOST', categories=CATEGORIES)


@items_bp.route('/report-found', methods=['GET', 'POST'])
@login_required
def report_found():
    if request.method == 'POST':
        response, item = _create_item('FOUND')
        if response is not None:
            return response
        flash('Found item reported successfully.', 'success')
        return redirect(url_for('items.item_detail', item_id=item.id))
    return render_template('items/report.html', item_type='FOUND', categories=CATEGORIES)


# ---------------------------------------------------------------------------
# Listing routes
# ---------------------------------------------------------------------------

@items_bp.route('/lost-items')
def lost_items():
    q        = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    location = request.args.get('location', '').strip()
    status   = request.args.get('status', '').strip()

    try:
        query = Item.query.filter_by(item_type='LOST')
        if q:        query = query.filter(Item.item_name.ilike(f'%{q}%'))
        if category: query = query.filter_by(category=category)
        if location: query = query.filter(Item.location.ilike(f'%{location}%'))
        if status:   query = query.filter_by(status=status)
        items = query.order_by(Item.created_at.desc()).all()
    except Exception as exc:
        logger.error('DB error loading lost items: %s', exc)
        db.session.rollback()
        flash('Could not load lost items. Please try again.', 'danger')
        items = []

    return render_template('items/list.html', items=items, item_type='LOST',
                           categories=CATEGORIES, q=q, category=category,
                           location=location, status=status,
                           image_urls=_build_image_url_map(items))


@items_bp.route('/found-items')
def found_items():
    q        = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    location = request.args.get('location', '').strip()
    status   = request.args.get('status', '').strip()

    try:
        query = Item.query.filter_by(item_type='FOUND')
        if q:        query = query.filter(Item.item_name.ilike(f'%{q}%'))
        if category: query = query.filter_by(category=category)
        if location: query = query.filter(Item.location.ilike(f'%{location}%'))
        if status:   query = query.filter_by(status=status)
        items = query.order_by(Item.created_at.desc()).all()
    except Exception as exc:
        logger.error('DB error loading found items: %s', exc)
        db.session.rollback()
        flash('Could not load found items. Please try again.', 'danger')
        items = []

    return render_template('items/list.html', items=items, item_type='FOUND',
                           categories=CATEGORIES, q=q, category=category,
                           location=location, status=status,
                           image_urls=_build_image_url_map(items))


# ---------------------------------------------------------------------------
# Item detail
# ---------------------------------------------------------------------------

@items_bp.route('/item/<int:item_id>')
def item_detail(item_id):
    try:
        item = db.get_or_404(Item, item_id)
    except Exception as exc:
        logger.error('DB error loading item %s: %s', item_id, exc)
        db.session.rollback()
        abort(500)

    image_url = _get_image_url(item)

    try:
        if item.item_type == 'LOST':
            matches = Match.query.filter_by(lost_item_id=item.id).order_by(
                Match.match_score.desc()).all()
        else:
            matches = Match.query.filter_by(found_item_id=item.id).order_by(
                Match.match_score.desc()).all()
    except Exception as exc:
        logger.error('DB error loading matches for item %s: %s', item_id, exc)
        db.session.rollback()
        matches = []

    return render_template('items/detail.html', item=item, matches=matches, image_url=image_url)


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

@items_bp.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        data = _item_form_data()
        errors = _validate_item(data)

        file = request.files.get('image')
        if file and file.filename:
            new_filename, new_s3_key, new_hash, upload_errors = _handle_upload(
                file, item.item_type)
            errors.extend(upload_errors)
            if not upload_errors:
                _delete_stored_file(item)
                item.image_filename = new_filename
                item.s3_object_key  = new_s3_key
                item.sha256_hash    = new_hash

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('items/edit.html', item=item, categories=CATEGORIES,
                                   image_url=_get_image_url(item))

        try:
            item.item_name       = data['item_name']
            item.category        = data['category']
            item.description     = data['description']
            item.location        = data['location']
            item.date_lost_found = datetime.strptime(data['date_lost_found'], '%Y-%m-%d').date()
            item.contact         = data['contact']
            db.session.commit()
        except Exception as exc:
            logger.error('DB error updating item %s: %s', item_id, exc)
            db.session.rollback()
            flash('A database error occurred while updating. Please try again.', 'danger')
            return render_template('items/edit.html', item=item, categories=CATEGORIES,
                                   image_url=_get_image_url(item))

        flash('Item updated successfully.', 'success')
        return redirect(url_for('items.item_detail', item_id=item.id))

    return render_template('items/edit.html', item=item, categories=CATEGORIES,
                           image_url=_get_image_url(item))


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@items_bp.route('/item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)

    _delete_stored_file(item)

    try:
        Match.query.filter(
            (Match.lost_item_id == item.id) | (Match.found_item_id == item.id)
        ).delete(synchronize_session=False)
        db.session.delete(item)
        db.session.commit()
    except Exception as exc:
        logger.error('DB error deleting item %s: %s', item_id, exc)
        db.session.rollback()
        flash('A database error occurred while deleting. Please try again.', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    flash('Item deleted.', 'success')
    return redirect(url_for('main.dashboard'))


# ---------------------------------------------------------------------------
# Mark recovered
# ---------------------------------------------------------------------------

@items_bp.route('/item/<int:item_id>/recover', methods=['POST'])
@login_required
def mark_recovered(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)

    try:
        item.status = 'RECOVERED'
        db.session.commit()
    except Exception as exc:
        logger.error('DB error marking item %s recovered: %s', item_id, exc)
        db.session.rollback()
        flash('A database error occurred. Please try again.', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    flash('Item marked as recovered.', 'success')
    return redirect(url_for('items.item_detail', item_id=item.id))


# ---------------------------------------------------------------------------
# My reports / Matches
# ---------------------------------------------------------------------------

@items_bp.route('/my-reports')
@login_required
def my_reports():
    try:
        items = Item.query.filter_by(user_id=current_user.id).order_by(
            Item.created_at.desc()).all()
    except Exception as exc:
        logger.error('DB error loading my-reports: %s', exc)
        db.session.rollback()
        flash('Could not load your reports. Please try again.', 'danger')
        items = []
    return render_template('items/my_reports.html', items=items)


@items_bp.route('/matches')
@login_required
def matches():
    try:
        all_matches = Match.query.order_by(Match.match_score.desc()).all()
    except Exception as exc:
        logger.error('DB error loading matches: %s', exc)
        db.session.rollback()
        flash('Could not load matches. Please try again.', 'danger')
        all_matches = []
    return render_template('items/matches.html', matches=all_matches)


# ---------------------------------------------------------------------------
# SHA-256 Integrity Verification
# ---------------------------------------------------------------------------

@items_bp.route('/verify/<int:item_id>')
@login_required
def verify_integrity(item_id):
    item = db.get_or_404(Item, item_id)
    stored_hash  = item.sha256_hash
    current_hash = None
    result       = None
    storage_info = None

    if item.s3_object_key:
        from services.s3_service import is_s3_configured, download_file
        storage_info = f'S3 object: {item.s3_object_key}'
        if is_s3_configured():
            data, err = download_file(item.s3_object_key)
            if data is not None:
                current_hash = calculate_sha256_bytes(data)
                result = 'VERIFIED' if current_hash == stored_hash else 'FAILED'
            else:
                result = 'S3_ERROR'
                flash(f'Could not retrieve file from S3: {err}', 'danger')
        else:
            result = 'S3_NOT_CONFIGURED'

    elif item.image_filename:
        storage_info = f'Local file: {item.image_filename}'
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], item.image_filename)
        current_hash = calculate_sha256(path)
        if current_hash and stored_hash:
            result = 'VERIFIED' if current_hash == stored_hash else 'FAILED'
        else:
            result = 'NO_FILE'
    else:
        result = 'NO_IMAGE'

    return render_template('items/verify.html', item=item,
                           result=result,
                           stored_hash=stored_hash,
                           current_hash=current_hash,
                           storage_info=storage_info)
