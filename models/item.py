from datetime import datetime, timezone
from extensions import db


class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_type = db.Column(db.String(10), nullable=False)   # LOST or FOUND
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    date_lost_found = db.Column(db.Date, nullable=False)
    contact = db.Column(db.String(150), nullable=False)
    image_filename = db.Column(db.String(200))
    s3_object_key = db.Column(db.String(300))
    sha256_hash = db.Column(db.String(64))
    status = db.Column(db.String(20), default='ACTIVE')    # ACTIVE, MATCHED, RECOVERED
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    lost_matches = db.relationship('Match', foreign_keys='Match.lost_item_id',
                                   backref='lost_item', lazy=True)
    found_matches = db.relationship('Match', foreign_keys='Match.found_item_id',
                                    backref='found_item', lazy=True)

    def __repr__(self):
        return f'<Item {self.item_name} ({self.item_type})>'


class Match(db.Model):
    __tablename__ = 'matches'

    id = db.Column(db.Integer, primary_key=True)
    lost_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    found_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    match_score = db.Column(db.Float, nullable=False)
    matching_reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDING')   # PENDING, CONFIRMED, REJECTED
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Match lost={self.lost_item_id} found={self.found_item_id} score={self.match_score}>'
