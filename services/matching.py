"""
Matching service — compares lost and found item reports.

Algorithm
---------
1. Compute weighted token-overlap similarity across name, category,
   location and description.
2. Detect explicit colour contradictions (e.g. "black" vs "red") and
   apply a configurable penalty that can override a high name+category score.
3. Return score (0–100), human-readable positive reasons, and conflict
   strings so users can make an informed decision.
4. Never auto-mark an item recovered — that requires explicit user action.

Thresholds (configurable via THRESHOLDS dict)
---------------------------------------------
  75–100  Strong candidate
  50–74   Potential match
  30–49   Possible match
  < 30    Not displayed by default

These are candidate-confidence scores, not statistical probabilities.
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

# ---------------------------------------------------------------------------
# Display thresholds — change these to adjust category boundaries
# ---------------------------------------------------------------------------
THRESHOLDS = {
    'strong':   75.0,   # >= 75  → Strong candidate
    'potential': 50.0,  # >= 50  → Potential match
    'possible':  30.0,  # >= 30  → Possible match
    'hidden':     0.0,  # <  30  → Not shown by default
}

# Penalty per detected colour contradiction.
# 40 pts drops a name+category-only match (60 pts) below the potential threshold.
_CONTRADICTION_PENALTY = 40.0

# Colour groups — words within the same group do NOT conflict with each other.
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


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def match_category(score: float) -> str:
    """
    Return the display category label for a given score.
    Used by templates to section matches and colour score badges.
    """
    if score >= THRESHOLDS['strong']:
        return 'strong'
    if score >= THRESHOLDS['potential']:
        return 'potential'
    if score >= THRESHOLDS['possible']:
        return 'possible'
    return 'hidden'


def match_category_label(score: float) -> str:
    """Human-readable label for the match category."""
    labels = {
        'strong':   'Strong Candidate',
        'potential': 'Potential Match',
        'possible':  'Possible Match',
        'hidden':    'Low Confidence',
    }
    return labels[match_category(score)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
    Return a list of conflict strings when the two texts contain colour words
    from *different* colour groups.  Empty list means no contradiction.

    Example:
        _detect_color_contradiction('black purse', 'red purse')
        → ['Color conflict: black vs red']
    """
    ta, tb = _tokens(text_a), _tokens(text_b)
    conflicts = []
    for group in _COLOR_GROUPS:
        colors_a = ta & group
        if not colors_a:
            continue
        # colors_a is present — check whether text_b has a colour from a
        # *different* group (same group = no conflict)
        same_group_in_b = tb & group
        if same_group_in_b:
            continue  # same colour family, no conflict
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


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------

def compute_match_score(lost: Item, found: Item) -> Tuple[float, List[str], List[str]]:
    """
    Compare a lost item against a found item.

    Returns
    -------
    score     : float 0–100 (after contradiction penalty)
    reasons   : list of positive matching reason strings
    conflicts : list of contradiction strings (empty when none found)

    Rules
    -----
    - Identical names alone do NOT guarantee a strong match; location and
      description must also agree for a high score.
    - Missing fields (empty string) contribute 0 to their component — they
      are neither counted as agreement nor disagreement.
    - Each detected colour contradiction subtracts _CONTRADICTION_PENALTY pts.
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

    # Colour contradiction detection across name + description combined
    combined_lost  = f"{lost.item_name} {lost.description}"
    combined_found = f"{found.item_name} {found.description}"
    conflicts = _detect_color_contradiction(combined_lost, combined_found)

    penalty = _CONTRADICTION_PENALTY * len(conflicts)
    score = max(0.0, raw_score - penalty)

    # Build human-readable positive reasons
    if name_sim >= 1.0:
        reasons.append(f"Exact name match: \"{lost.item_name}\"")
    elif name_sim > 0:
        reasons.append(f"Name similarity: {name_sim * 100:.0f}%")
    if cat_sim:
        reasons.append(f"Same category: {lost.category}")
    if loc_sim >= 1.0:
        reasons.append(f"Same location: \"{lost.location}\"")
    elif loc_sim > 0:
        reasons.append(f"Location similarity: {loc_sim * 100:.0f}%")
    if desc_sim >= 1.0:
        reasons.append("Description matches exactly")
    elif desc_sim > 0:
        reasons.append(f"Description similarity: {desc_sim * 100:.0f}%")

    return round(score, 1), reasons, conflicts


# ---------------------------------------------------------------------------
# Candidate search
# ---------------------------------------------------------------------------

def find_matches_for_item(item: Item, threshold: float = None):
    """
    Find all potential matches for a given item at or above the threshold.

    Searches ACTIVE and MATCHED candidates (not RECOVERED).
    Returns list of (other_item, score, reasons_and_conflicts_combined).

    threshold defaults to THRESHOLDS['possible'] (30) so possible matches
    are stored; the UI filters by category.
    """
    if threshold is None:
        threshold = THRESHOLDS['possible']

    searchable = ('ACTIVE', 'MATCHED')
    if item.item_type == 'LOST':
        candidates = Item.query.filter(
            Item.item_type == 'FOUND',
            Item.status.in_(searchable)
        ).all()
        pairs = [(item, c) for c in candidates if c.id != item.id]
    else:
        candidates = Item.query.filter(
            Item.item_type == 'LOST',
            Item.status.in_(searchable)
        ).all()
        pairs = [(c, item) for c in candidates if c.id != item.id]

    results = []
    for lost, found in pairs:
        score, reasons, conflicts = compute_match_score(lost, found)
        if score >= threshold:
            other = found if item.item_type == 'LOST' else lost
            all_reasons = reasons + [f"CONFLICT: {c}" for c in conflicts]
            results.append((other, score, all_reasons))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_match(lost_item_id: int, found_item_id: int,
               score: float, reasons: List[str]) -> Match:
    """Persist a match record, updating score/reasons if it already exists."""
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
