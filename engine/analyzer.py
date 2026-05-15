"""
engine/analyzer.py
Layer 1: The Analyzer — Generates a "Heatmap" of the input text.
Identifies which sentences are statistically "flat" (AI-like) vs. "bursty" (human-like).
Engine: Pure heuristic. No models needed. Uses sentence length variance and
a lookup against the high-probability word list.
"""

import json
import re
import os
import math
from typing import List, Tuple, Dict

# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

def _load_high_prob() -> Dict:
    path = os.path.join(_DATA_DIR, "high_prob_words.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

_HIGH_PROB = _load_high_prob()

# Flatten all high-probability words into a single set for O(1) lookup
_HIGH_PROB_FLAT: set = set()
for category in _HIGH_PROB.values():
    if isinstance(category, dict):
        _HIGH_PROB_FLAT.update(k.lower() for k in category.keys())

# ─────────────────────────────────────────────────────────────────────────────
# Sentence splitting
# ─────────────────────────────────────────────────────────────────────────────

def split_sentences(text: str) -> List[Tuple[str, str]]:
    """
    Split text into a list of (text, delimiter) tuples.
    This allows perfect reconstruction of the original document structure.
    """
    # Split while capturing the delimiters (whitespace/newlines after punctuation)
    pattern = r'((?<=[.!?])\s+)'
    parts = re.split(pattern, text)
    
    # parts will be [sent1, delim1, sent2, delim2, ..., sentN]
    res = []
    for i in range(0, len(parts) - 1, 2):
        res.append((parts[i], parts[i+1]))
    if len(parts) % 2 == 1:
        res.append((parts[-1], ""))
    return res

# ─────────────────────────────────────────────────────────────────────────────
# Burstiness Score
# ─────────────────────────────────────────────────────────────────────────────

def burstiness_score(sentences: List[Tuple[str, str]]) -> float:
    """
    Returns a burstiness variance score.
    """
    if len(sentences) < 2:
        return 1.0
    lengths = [len(s[0].split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    std_dev = math.sqrt(variance)
    # Normalize: human text has std_dev typically >4 words
    score = min(std_dev / 8.0, 1.0)
    return round(score, 4)

# ─────────────────────────────────────────────────────────────────────────────
# High-Probability Word Count
# ─────────────────────────────────────────────────────────────────────────────

def count_high_prob_words(text: str) -> Tuple[int, List[str]]:
    """
    Returns (count, list_of_found_words).
    Counts how many "AI-typical" high-probability words appear in the text.
    """
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    found = [w for w in words if w in _HIGH_PROB_FLAT]
    return len(found), list(set(found))

# ─────────────────────────────────────────────────────────────────────────────
# Connector / GPT-ism detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_gpt_connectors(text: str) -> List[str]:
    """
    Detects overused GPT-style transitional phrases.
    Returns list of matches found.
    """
    connectors = list(_HIGH_PROB.get("connectors", {}).keys())
    found = []
    for c in connectors:
        if c and c.lower() in text.lower():
            found.append(c)
    return found

# ─────────────────────────────────────────────────────────────────────────────
# Sentence-level AI likelihood (heuristic hotspot finder)
# ─────────────────────────────────────────────────────────────────────────────

def sentence_hotspots(sentences: List[Tuple[str, str]], top_n: int = 5) -> List[Tuple[int, float, str]]:
    """
    Returns top_n sentences most likely to be "AI-generated"
    """
    lengths = [len(s[0].split()) for s in sentences]
    mean_len = sum(lengths) / max(len(lengths), 1)

    scored = []
    for i, (sent, _) in enumerate(sentences):
        word_count = lengths[i]
        hp_count, _ = count_high_prob_words(sent)
        hp_density = hp_count / max(word_count, 1)

        # Length conformity penalty (more uniform = more AI-like)
        conformity = 1.0 - min(abs(word_count - mean_len) / max(mean_len, 1), 1.0)

        # Combined heuristic score
        score = (hp_density * 0.6) + (conformity * 0.4)
        scored.append((i, round(score, 4), sent))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]

# ─────────────────────────────────────────────────────────────────────────────
# Public API: Full Analysis Report
# ─────────────────────────────────────────────────────────────────────────────

def analyze(text: str) -> Dict:
    """
    Full analysis of input text.
    """
    sentences = split_sentences(text)
    burst = burstiness_score(sentences)
    hp_count, hp_words = count_high_prob_words(text)
    connectors = detect_gpt_connectors(text)
    hotspots = sentence_hotspots(sentences)

    # Rough verdict
    ai_signals = 0
    if burst < 0.35:
        ai_signals += 1
    if hp_count > 5:
        ai_signals += 1
    if len(connectors) >= 2:
        ai_signals += 1

    if ai_signals == 0:
        verdict = "CLEAN — Minimal AI signals detected."
    elif ai_signals == 1:
        verdict = "LOW RISK — A few AI patterns present."
    elif ai_signals == 2:
        verdict = "MEDIUM RISK — Detectors may flag this."
    else:
        verdict = "HIGH RISK — Strong AI signals. Run all passes."

    return {
        "burstiness": burst,
        "high_prob_count": hp_count,
        "high_prob_words": hp_words,
        "gpt_connectors": connectors,
        "hotspots": hotspots,
        "sentences": sentences,
        "verdict": verdict,
    }
