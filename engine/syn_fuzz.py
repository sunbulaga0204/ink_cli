"""
engine/syn_fuzz.py
Layer 3: The Lexical Fuzzer (Synonym Swapper)
Uses the high-probability word list to find AI-typical words and replaces them
with lower-probability synonyms. POS mapping ensures Noun→Noun, Adj→Adj.
Engine: Heuristic. Dictionary-based. No model needed.
"""

import json
import os
import re
import random
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

def _load_words() -> Dict:
    with open(os.path.join(_DATA_DIR, "high_prob_words.json"), encoding="utf-8") as f:
        return json.load(f)

_WORDS = _load_words()

# ─────────────────────────────────────────────────────────────────────────────
# Build a flat "word → [synonyms, category]" lookup
# ─────────────────────────────────────────────────────────────────────────────

# Structure: { "significant": {"synonyms": [...], "pos": "adjectives"} }
_LOOKUP: Dict[str, Dict] = {}

for pos_category, word_map in _WORDS.items():
    if not isinstance(word_map, dict):
        continue
    for word, synonyms in word_map.items():
        # Filter out empty strings (e.g., stripped GPT-isms)
        clean_syns = [s for s in synonyms if s.strip()]
        if clean_syns:
            _LOOKUP[word.lower()] = {"synonyms": clean_syns, "pos": pos_category}

# ─────────────────────────────────────────────────────────────────────────────
# Case preservation helper
# ─────────────────────────────────────────────────────────────────────────────

def _preserve_case(original: str, replacement: str) -> str:
    """Match the case pattern of the original word to the replacement."""
    if original.isupper():
        return replacement.upper()
    if original.istitle():
        return replacement.capitalize()
    return replacement.lower()

# ─────────────────────────────────────────────────────────────────────────────
# Find candidates in a sentence
# ─────────────────────────────────────────────────────────────────────────────

def find_candidates(sentence: str) -> List[Tuple[str, str, List[str]]]:
    """
    Scan a sentence for high-probability words.
    Returns list of (original_word, pos_category, synonyms).
    """
    # Tokenize preserving punctuation
    tokens = re.findall(r'\b[a-zA-Z]+\b', sentence)
    candidates = []
    seen = set()
    for token in tokens:
        lower = token.lower()
        if lower in _LOOKUP and lower not in seen:
            seen.add(lower)
            candidates.append((token, _LOOKUP[lower]["pos"], _LOOKUP[lower]["synonyms"]))
    return candidates

# ─────────────────────────────────────────────────────────────────────────────
# GPT Connector replacement
# ─────────────────────────────────────────────────────────────────────────────

def find_connector_candidates(text: str) -> List[Tuple[str, List[str]]]:
    """
    Detects GPT-style transitional phrases in the text.
    Returns list of (original_phrase, [replacement_options]).
    """
    connectors = _WORDS.get("connectors", {})
    found = []
    for phrase, replacements in connectors.items():
        if not phrase:
            continue
        clean = [r for r in replacements if r.strip()]
        if clean and re.search(re.escape(phrase), text, re.IGNORECASE):
            found.append((phrase, clean))
    return found

# ─────────────────────────────────────────────────────────────────────────────
# Apply a single swap in a sentence
# ─────────────────────────────────────────────────────────────────────────────

def apply_swap(sentence: str, original: str, replacement: str) -> str:
    """
    Replace the first occurrence of `original` in `sentence` with `replacement`.
    Preserves the case pattern of the original.
    """
    cased_replacement = _preserve_case(original, replacement)

    def replacer(match):
        return cased_replacement

    pattern = r'\b' + re.escape(original) + r'\b'
    return re.sub(pattern, replacer, sentence, count=1, flags=re.IGNORECASE)


def apply_connector_swap(text: str, original: str, replacement: str) -> str:
    """Replace a multi-word connector phrase in the full text."""
    pattern = re.escape(original)
    return re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)

# ─────────────────────────────────────────────────────────────────────────────
# Interactive proposal: pick a random synonym to propose
# ─────────────────────────────────────────────────────────────────────────────

def propose_swap(sentence: str, rng: random.Random) -> Optional[Tuple[str, str, str]]:
    """
    Pick one high-probability word from the sentence and propose a swap.
    Returns (original, proposed_replacement, pos_category) or None.
    """
    candidates = find_candidates(sentence)
    if not candidates:
        return None
    # Pick randomly for stochasticity
    original, pos, synonyms = rng.choice(candidates)
    # Pick a synonym that isn't the same as the original
    options = [s for s in synonyms if s.lower() != original.lower()]
    if not options:
        return None
    replacement = rng.choice(options)
    return original, replacement, pos
