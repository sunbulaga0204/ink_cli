"""
engine/voice.py
Layer 4: The Disfluency & Voice Injector
Injects human-typical linguistic markers:
  - Hedges (e.g., "For what it's worth,")
  - Parenthetical asides
  - Sentence openers
  - Non-sequitur bridges between paragraphs
Engine: Heuristic. Template-based. No model needed.
"""

import json
import os
import re
import random
from typing import List, Tuple, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

def _load_templates() -> dict:
    with open(os.path.join(_DATA_DIR, "voice_templates.json"), encoding="utf-8") as f:
        return json.load(f)

_TEMPLATES = _load_templates()

# ─────────────────────────────────────────────────────────────────────────────
# Voice Action Types
# ─────────────────────────────────────────────────────────────────────────────

VOICE_ACTIONS = {
    "hedge":         "Prepend a hedge to the sentence.",
    "parenthetical": "Insert a parenthetical aside into the sentence.",
    "opener":        "Replace the sentence opener with a human-style one.",
    "bridge":        "Insert a non-sequitur bridge before this sentence.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Hedge injection
# ─────────────────────────────────────────────────────────────────────────────

def apply_hedge(sentence: str, rng: random.Random) -> str:
    """Prepend a hedge phrase to the sentence."""
    hedge = rng.choice(_TEMPLATES["hedges"])
    # Lowercase the first char of the original sentence
    s = sentence[0].lower() + sentence[1:] if sentence else sentence
    return f"{hedge} {s}"


def preview_hedge(rng: random.Random) -> str:
    return rng.choice(_TEMPLATES["hedges"])

# ─────────────────────────────────────────────────────────────────────────────
# Parenthetical injection
# ─────────────────────────────────────────────────────────────────────────────

def apply_parenthetical(sentence: str, rng: random.Random) -> str:
    """
    Insert a parenthetical aside after the first clause of the sentence.
    Tries to find a comma or natural pause. Falls back to mid-sentence.
    """
    aside = rng.choice(_TEMPLATES["parenthetical_inserts"])

    # Try to find a comma after the first 5 words
    words = sentence.split()
    if len(words) < 6:
        # Just append at end before the period
        base = sentence.rstrip(".!?")
        ending = sentence[len(base):]
        return f"{base} {aside}{ending}"

    # Find the first comma after word 4
    comma_match = re.search(r',', ' '.join(words[4:]))
    if comma_match:
        pre_comma = ' '.join(words[:4]) + ' ' + ' '.join(words[4:])[:comma_match.start() + len(' '.join(words[:4])) + 1]
        # Simpler: just insert before the first comma
        comma_pos = sentence.find(',')
        if comma_pos > 10:
            return sentence[:comma_pos] + f" {aside}" + sentence[comma_pos:]

    # Fallback: insert after the 5th word
    mid = len(' '.join(words[:5]))
    return sentence[:mid] + f" {aside}" + sentence[mid:]


def preview_parenthetical(rng: random.Random) -> str:
    return rng.choice(_TEMPLATES["parenthetical_inserts"])

# ─────────────────────────────────────────────────────────────────────────────
# Opener replacement
# ─────────────────────────────────────────────────────────────────────────────

_GENERIC_OPENERS = [
    "This", "The", "It is", "There is", "These", "Such", "One",
    "Studies", "Research", "Data", "Evidence"
]

def apply_opener(sentence: str, rng: random.Random) -> str:
    """Replace a generic sentence opener with a human-style one."""
    opener = rng.choice(_TEMPLATES["sentence_openers"])
    # Strip generic openers if found
    for generic in _GENERIC_OPENERS:
        if sentence.startswith(generic):
            remainder = sentence[len(generic):].lstrip(" ,")
            # Lowercase the remainder's first char
            remainder = remainder[0].lower() + remainder[1:] if remainder else remainder
            return f"{opener} {remainder}"
    # Fallback: just prepend the opener
    s = sentence[0].lower() + sentence[1:] if sentence else sentence
    return f"{opener} {s}"


def preview_opener(rng: random.Random) -> str:
    return rng.choice(_TEMPLATES["sentence_openers"])

# ─────────────────────────────────────────────────────────────────────────────
# Non-sequitur bridge
# ─────────────────────────────────────────────────────────────────────────────

def apply_bridge(sentences: List[str], index: int, rng: random.Random) -> List[str]:
    """Insert a non-sequitur bridge before sentences[index]."""
    bridge = rng.choice(_TEMPLATES["non_sequitur_bridges"])
    return sentences[:index] + [bridge] + sentences[index:]


def preview_bridge(rng: random.Random) -> str:
    return rng.choice(_TEMPLATES["non_sequitur_bridges"])

# ─────────────────────────────────────────────────────────────────────────────
# Find candidates for voice injection
# ─────────────────────────────────────────────────────────────────────────────

def find_voice_candidates(sentences: List[str], rng: random.Random, max_per_pass: int = 3) -> List[Tuple[int, str, str]]:
    """
    Returns a list of (sentence_index, action_type, preview_text) proposals.
    Only proposes changes for sentences that look "too clean" (no hedges or asides already).
    """
    already_hedged = set()
    for i, s in enumerate(sentences):
        for hedge in _TEMPLATES["hedges"]:
            if hedge.lower() in s.lower():
                already_hedged.add(i)

    candidates = []
    indices = list(range(len(sentences)))
    rng.shuffle(indices)

    for i in indices:
        if len(candidates) >= max_per_pass:
            break
        if i in already_hedged:
            continue
        s = sentences[i]
        # Skip very short sentences or ones that are already parenthetical
        if len(s.split()) < 6 or s.startswith("("):
            continue

        action = rng.choice(list(VOICE_ACTIONS.keys()))

        if action == "hedge":
            preview = apply_hedge(s, rng)
        elif action == "parenthetical":
            preview = apply_parenthetical(s, rng)
        elif action == "opener":
            preview = apply_opener(s, rng)
        elif action == "bridge":
            preview = preview_bridge(rng)
        else:
            continue

        candidates.append((i, action, preview))

    return candidates
