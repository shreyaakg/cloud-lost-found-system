from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models.item import Item, Match

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    total_lost = Item.query.filter_by(item_type='LOST').count()
    total_found = Item.query.filter_by(item_type='FOUND').count()
    active = Item.query.filter_by(status='ACTIVE').count()
    matched = Item.query.filter_by(status='MATCHED').count()
    recovered = Item.query.filter_by(status='RECOVERED').count()
    return render_template('dashboard.html',
                           total_lost=total_lost,
                           total_found=total_found,
                           active=active,
                           matched=matched,
                           recovered=recovered)
