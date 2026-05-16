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
    Ensures that paragraph breaks (double newlines) are treated as delimiters
    so that sentences aren't accidentally merged across paragraphs.
    """
    # Split at punctuation followed by whitespace OR at double newlines
    # Using a capture group ensures we keep the delimiters
    pattern = r'((?:(?<=[.!?])\s+)|(?:\n\n+))'
    parts = re.split(pattern, text)
    
    # parts will be [sent1, delim1, sent2, delim2, ..., sentN]
    res = []
    for i in range(0, len(parts) - 1, 2):
        if parts[i] or parts[i+1]:
            res.append((parts[i], parts[i+1]))
    
    if len(parts) % 2 == 1:
        if parts[-1]:
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

def analyze(text: str) -> Dict:
    """
    Runs Layer 1 analysis on the text.
    """
    sentences = split_sentences(text)
    
    total_words = 0
    high_prob_count = 0
    high_prob_found = []
    gpt_connectors_found = []
    
    # Check for overused "GPT" connectors
    for conn in _HIGH_PROB.get("connectors", {}).keys():
        if conn.lower() in text.lower():
            gpt_connectors_found.append(conn)

    sentence_stats = []
    for i, (sent, delim) in enumerate(sentences):
        words = sent.split()
        if not words:
            continue
        
        total_words += len(words)
        hp_in_sent = 0
        hp_words_in_sent = []
        
        for w in words:
            clean_w = re.sub(r'[^\w]', '', w).lower()
            if clean_w in _HIGH_PROB_FLAT:
                hp_in_sent += 1
                hp_words_in_sent.append(w)
        
        high_prob_count += hp_in_sent
        high_prob_found.extend(hp_words_in_sent)
        
        # Calculate AI-likelihood score for this sentence
        # (Based on high probability word density and word count)
        score = (hp_in_sent / len(words)) if words else 0
        sentence_stats.append((i, score, sent))

    # Sort hotspots by score (descending)
    hotspots = sorted(sentence_stats, key=lambda x: x[1], reverse=True)
    
    burst = burstiness_score(sentences)
    
    # Heuristic verdict
    verdict = "HUMAN"
    if burst < 0.3 or (high_prob_count / max(total_words, 1)) > 0.2:
        verdict = "LIKELY AI"
    elif burst < 0.5:
        verdict = "MIXED"

    return {
        "verdict": verdict,
        "burstiness": burst,
        "high_prob_count": high_prob_count,
        "high_prob_words": list(set(high_prob_found)),
        "gpt_connectors": gpt_connectors_found,
        "hotspots": hotspots
    }
