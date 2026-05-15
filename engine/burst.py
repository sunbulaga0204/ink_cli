"""
engine/burst.py
Layer 2: The Burstiness Injector
Finds clusters of uniform-length sentences and forces variance by:
  - Merging two short, adjacent sentences with a conjunction.
  - Splitting one long sentence into two punchy ones.
Engine: Pure heuristic. No models needed.
"""

import re
import random
from typing import List, Tuple, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Merge Conjunctions — used when joining two short sentences
# ─────────────────────────────────────────────────────────────────────────────

_MERGE_CONJUNCTIONS = [
    "; consequently,",
    "; as a result,",
    "— and, in fact,",
    ", which means",
    "; this is why",
    ", and yet",
    "; in turn,",
    "— that is,",
]

# ─────────────────────────────────────────────────────────────────────────────
# Splitters — used when cutting a long sentence in two
# Splits at these conjunctions if found in the sentence.
# ─────────────────────────────────────────────────────────────────────────────

_SPLIT_MARKERS = [
    r'\band\b',
    r'\bwhich\b',
    r'\bwhere\b',
    r'\bbecause\b',
    r'\balthough\b',
    r'\bwhile\b',
    r'\bwhereas\b',
    r'\bso that\b',
]

# ─────────────────────────────────────────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────────────────────────────────────────

def _word_count(sentence: str) -> int:
    return len(sentence.split())


def _find_split_point(sentence: str) -> Optional[Tuple[str, str]]:
    """
    Find a natural split point in a long sentence.
    Returns (part1, part2) if found, else None.
    """
    for marker in _SPLIT_MARKERS:
        matches = list(re.finditer(marker, sentence, flags=re.IGNORECASE))
        if not matches:
            continue
        # Pick a match that splits the sentence roughly in the middle third
        for m in matches:
            pos = m.start()
            total = len(sentence)
            if total * 0.25 < pos < total * 0.75:
                part1 = sentence[:pos].rstrip(" ,")
                part2 = sentence[pos:].strip()
                # Capitalize the start of part2
                part2 = part2[0].upper() + part2[1:] if part2 else part2
                if _word_count(part1) >= 4 and _word_count(part2) >= 4:
                    return part1 + ".", part2
    return None


def _merge_pair(s1: str, s2: str, rng: random.Random) -> str:
    """
    Merge two sentences into one using a random conjunction.
    Strips the period from s1.
    """
    conj = rng.choice(_MERGE_CONJUNCTIONS)
    s1_clean = s1.rstrip(".!?")
    s2_clean = s2[0].lower() + s2[1:] if s2 else s2
    return f"{s1_clean}{conj} {s2_clean}"

# ─────────────────────────────────────────────────────────────────────────────
# Main pass
# ─────────────────────────────────────────────────────────────────────────────

def find_burst_candidates(sentences: List[str], window: int = 4) -> List[Tuple[str, int, str]]:
    """
    Scans for clusters of uniform sentence lengths.
    Returns a list of (action, index, description) proposals.
    action: "merge" or "split"
    index: sentence index where the action applies
    description: human-readable change description
    """
    proposals = []
    lengths = [_word_count(s) for s in sentences]
    mean_len = sum(lengths) / max(len(lengths), 1)

    i = 0
    while i < len(sentences) - 1:
        # ── Merge opportunity: two adjacent short/medium sentences ──
        l1 = lengths[i]
        l2 = lengths[i + 1]
        both_close_to_mean = abs(l1 - mean_len) < 5 and abs(l2 - mean_len) < 5
        both_short = l1 < 20 and l2 < 20

        if both_short and both_close_to_mean and i + 1 < len(sentences):
            proposals.append((
                "merge",
                i,
                f"Sentences {i+1} & {i+2} are uniform ({l1}w / {l2}w). "
                f"Propose merging with conjunction."
            ))
            i += 2
            continue

        # ── Split opportunity: one very long sentence ──
        if l1 > 35:
            split_result = _find_split_point(sentences[i])
            if split_result:
                proposals.append((
                    "split",
                    i,
                    f"Sentence {i+1} is long ({l1}w). Propose splitting at natural conjunction."
                ))
        i += 1

    return proposals


def apply_merge(sentences: List[str], index: int, rng: random.Random) -> List[str]:
    """Apply merge of sentences[index] and sentences[index+1]."""
    merged = _merge_pair(sentences[index], sentences[index + 1], rng)
    return sentences[:index] + [merged] + sentences[index + 2:]


def apply_split(sentences: List[str], index: int) -> List[str]:
    """Apply split of sentences[index] at its natural conjunction."""
    result = _find_split_point(sentences[index])
    if result is None:
        return sentences  # no change possible
    part1, part2 = result
    return sentences[:index] + [part1, part2] + sentences[index + 1:]


def preview_merge(sentences: List[str], index: int, rng: random.Random) -> str:
    """Return a preview of what the merged sentence would look like."""
    return _merge_pair(sentences[index], sentences[index + 1], rng)


def preview_split(sentences: List[str], index: int) -> Optional[Tuple[str, str]]:
    """Return a preview of the split result."""
    return _find_split_point(sentences[index])
