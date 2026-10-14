"""
Matching service — compares lost and found item reports.

Algorithm:
  1. Compute weighted similarity across name, category, location, description.
  2. Detect explicit color/attribute contradictions in description+name tokens.
     A contradiction (e.g. "black" vs "red") applies a penalty that can
     override a high name+category score.
  3. Return score (0-100), matching reasons, and conflicting details so users
     can make an informed decision.
  4. Never auto-mark an item recovered — that requires explicit user action.
"""

import re
from typing import List, Tuple
from models.item import Item, Match
from extensions import db

# ---------------------------------------------------------------------------
# Weights — must sum to 1.0
# ---------------------------------------------------------------------------
WEIGHTS = {
    'item_name':   0.35,
    'category':    0.25,
    'location':    0.25,
    'description': 0.15,
}

# Common color words used for contradiction detection.
# Two items whose combined text contains members of different color groups
# are penalised.
_COLOR_GROUPS = [
    {'black', 'dark'},
    {'white', 'cream', 'ivory'},
    {'red', 'crimson', 'maroon', 'scarlet'},
    {'blue', 'navy', 'cobalt', 'azure'},
    {'green', 'olive', 'teal', 'lime'},
    {'yellow', 'gold', 'amber'},
    {'orange'},
    {'pink', 'rose', 'magenta'},
    {'purple', 'violet', 'lavender'},
    {'brown', 'tan', 'beige', 'khaki'},
    {'grey', 'gray', 'silver'},
]

# Penalty applied when a clear color contradiction is detected.
# 40 points is enough to drop a name+category match (60 pts) below threshold.
_CONTRADICTION_PENALTY = 40.0


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation."""
    return re.sub(r'[^\w\s]', ' ', text.lower()).strip()


def _tokens(text: str) -> set:
    return set(_normalise(text).split())


def _token_overlap(a: str, b: str) -> float:
    """Jaccard-style word-overlap similarity between two strings."""
    if not a or not b:
        return 0.0
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _detect_color_contradiction(text_a: str, text_b: str) -> List[str]:
    """
    Return a list of contradiction strings if the two texts contain color
    words from different color groups.  Empty list means no contradiction.

    Example: text_a='black purse', text_b='red purse' ->
             ['Color conflict: black vs red']
    """
    ta, tb = _tokens(text_a), _tokens(text_b)
    conflicts = []
    for group in _COLOR_GROUPS:
        colors_a = ta & group
        colors_b = tb & group
        # Both texts mention the SAME color group — no conflict
        if colors_a and colors_b:
            continue
        # One text has a color from this group, the other has a color from a
        # different group — check all other groups for the other text
        if colors_a:
            for other_group in _COLOR_GROUPS:
                if other_group is group:
                    continue
                colors_b_other = tb & other_group
                if colors_b_other:
                    conflicts.append(
                        f"Color conflict: {', '.join(sorted(colors_a))} "
                        f"vs {', '.join(sorted(colors_b_other))}"
                    )
    return conflicts


def compute_match_score(lost: Item, found: Item) -> Tuple[float, List[str], List[str]]:
    """
    Compare a lost item against a found item.

    Returns:
        score        — float 0-100 (after contradiction penalty)
        reasons      — list of positive matching reason strings
        conflicts    — list of contradiction strings (empty when none found)
    """
    reasons: List[str] = []
    conflicts: List[str] = []

    name_sim = _token_overlap(lost.item_name, found.item_name)
    cat_sim  = 1.0 if lost.category.lower() == found.category.lower() else 0.0
    loc_sim  = _token_overlap(lost.location, found.location)
    desc_sim = _token_overlap(lost.description, found.description)

    raw_score = (
        name_sim * WEIGHTS['item_name'] +
        cat_sim  * WEIGHTS['category'] +
        loc_sim  * WEIGHTS['location'] +
        desc_sim * WEIGHTS['description']
    ) * 100

    # Detect color contradictions across all text fields combined
    combined_lost  = f"{lost.item_name} {lost.description}"
    combined_found = f"{found.item_name} {found.description}"
    conflicts = _detect_color_contradiction(combined_lost, combined_found)

    # Apply penalty: each distinct contradiction reduces the score
    penalty = _CONTRADICTION_PENALTY * len(conflicts)
    score = max(0.0, raw_score - penalty)

    # Build human-readable reasons
    if name_sim > 0:
        reasons.append(f"Item name similarity: {name_sim * 100:.0f}%")
    if cat_sim:
        reasons.append(f"Same category: {lost.category}")
    if loc_sim > 0:
        reasons.append(f"Location similarity: {loc_sim * 100:.0f}%")
    if desc_sim > 0:
        reasons.append(f"Description similarity: {desc_sim * 100:.0f}%")

    return round(score, 1), reasons, conflicts


def find_matches_for_item(item: Item, threshold: float = 50.0):
    """
    Find all potential matches for a given item above the threshold.
    Returns list of (other_item, score, reasons_and_conflicts_combined).
    """
    if item.item_type == 'LOST':
        candidates = Item.query.filter_by(item_type='FOUND', status='ACTIVE').all()
        pairs = [(item, c) for c in candidates if c.id != item.id]
    else:
        candidates = Item.query.filter_by(item_type='LOST', status='ACTIVE').all()
        pairs = [(c, item) for c in candidates if c.id != item.id]

    results = []
    for lost, found in pairs:
        score, reasons, conflicts = compute_match_score(lost, found)
        if score >= threshold:
            other = found if item.item_type == 'LOST' else lost
            # Merge reasons and conflicts into a single list for storage
            all_reasons = reasons + [f"CONFLICT: {c}" for c in conflicts]
            results.append((other, score, all_reasons))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def save_match(lost_item_id: int, found_item_id: int,
               score: float, reasons: List[str]) -> Match:
    """Persist a match record, avoiding duplicates."""
    existing = Match.query.filter_by(
        lost_item_id=lost_item_id,
        found_item_id=found_item_id
    ).first()
    reason_text = '; '.join(reasons)
    if existing:
        existing.match_score = score
        existing.matching_reason = reason_text
        db.session.commit()
        return existing

    match = Match(
        lost_item_id=lost_item_id,
        found_item_id=found_item_id,
        match_score=score,
        matching_reason=reason_text,
    )
    db.session.add(match)
    db.session.commit()
    return match
