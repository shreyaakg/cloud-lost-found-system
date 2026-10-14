import logging
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models.item import Item, Match

logger = logging.getLogger(__name__)
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        total_lost  = Item.query.filter_by(item_type='LOST').count()
        total_found = Item.query.filter_by(item_type='FOUND').count()
        active      = Item.query.filter_by(status='ACTIVE').count()
        matched     = Item.query.filter_by(status='MATCHED').count()
        recovered   = Item.query.filter_by(status='RECOVERED').count()
    except Exception as exc:
        logger.error('DB error loading dashboard: %s', exc)
        db.session.rollback()
        flash('Could not load dashboard statistics. Please refresh.', 'warning')
        total_lost = total_found = active = matched = recovered = 0

    return render_template('dashboard.html',
                           total_lost=total_lost,
                           total_found=total_found,
                           active=active,
                           matched=matched,
                           recovered=recovered)
