from models.item import Item, Match
from extensions import db


WEIGHTS = {
    'item_name': 0.35,
    'category': 0.25,
    'location': 0.25,
    'description': 0.15,
}


def _token_overlap(a: str, b: str) -> float:
    """Simple word-overlap similarity between two strings."""
    if not a or not b:
        return 0.0
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = tokens_a & tokens_b
    return len(overlap) / max(len(tokens_a), len(tokens_b))


def compute_match_score(lost: Item, found: Item):
    """
    Compare a lost item against a found item.
    Returns (score 0-100, list of matching reason strings).
    """
    reasons = []

    name_sim = _token_overlap(lost.item_name, found.item_name)
    cat_sim = 1.0 if lost.category.lower() == found.category.lower() else 0.0
    loc_sim = _token_overlap(lost.location, found.location)
    desc_sim = _token_overlap(lost.description, found.description)

    score = (
        name_sim * WEIGHTS['item_name'] +
        cat_sim * WEIGHTS['category'] +
        loc_sim * WEIGHTS['location'] +
        desc_sim * WEIGHTS['description']
    ) * 100

    if name_sim > 0:
        reasons.append(f"Item name similarity: {name_sim * 100:.0f}%")
    if cat_sim:
        reasons.append(f"Same category: {lost.category}")
    if loc_sim > 0:
        reasons.append(f"Location similarity: {loc_sim * 100:.0f}%")
    if desc_sim > 0:
        reasons.append(f"Description similarity: {desc_sim * 100:.0f}%")

    return round(score, 1), reasons


def find_matches_for_item(item: Item, threshold=50.0):
    """
    Find all potential matches for a given item.
    Returns list of (other_item, score, reasons).
    """
    if item.item_type == 'LOST':
        candidates = Item.query.filter_by(item_type='FOUND', status='ACTIVE').all()
        pairs = [(item, c) for c in candidates if c.id != item.id]
    else:
        candidates = Item.query.filter_by(item_type='LOST', status='ACTIVE').all()
        pairs = [(c, item) for c in candidates if c.id != item.id]

    results = []
    for lost, found in pairs:
        score, reasons = compute_match_score(lost, found)
        if score >= threshold:
            other = found if item.item_type == 'LOST' else lost
            results.append((other, score, reasons))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def save_match(lost_item_id, found_item_id, score, reasons):
    """Persist a match record, avoiding duplicates."""
    existing = Match.query.filter_by(
        lost_item_id=lost_item_id,
        found_item_id=found_item_id
    ).first()
    if existing:
        existing.match_score = score
        existing.matching_reason = '; '.join(reasons)
        db.session.commit()
        return existing

    match = Match(
        lost_item_id=lost_item_id,
        found_item_id=found_item_id,
        match_score=score,
        matching_reason='; '.join(reasons)
    )
    db.session.add(match)
    db.session.commit()
    return match
