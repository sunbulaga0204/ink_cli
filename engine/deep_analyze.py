"""
engine/deep_analyze.py
Layer 1 (Advanced) — NLTK-powered deep analysis engine.
Activated only when the user runs `ink --deep`.

Requires: nltk >= 3.8
Data packages: punkt, wordnet, averaged_perceptron_tagger

This module is fully isolated from the core engine.
The standard analyzer.py remains untouched and functional without nltk.

Features:
  - N-Gram Perplexity Scoring (Layer 3)
  - Lemma-based Type-Token Ratio / Lexical Diversity (Layer 4)
  - Modal Verb / Hedge Detection via POS Tagging (Layer 5)
"""

from __future__ import annotations

import re
import math
from typing import Dict, List, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap: lazy NLTK loader
# Called once before any deep analysis. Handles download gracefully.
# ─────────────────────────────────────────────────────────────────────────────

_NLTK_READY = False

_REQUIRED_PACKAGES = [
    ("tokenizers/punkt_tab", "punkt_tab"),
    ("corpora/wordnet",      "wordnet"),
    ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
]


def bootstrap_nltk() -> bool:
    """
    Ensures all required NLTK data packages are present.
    Downloads missing ones with user consent.
    Returns True if ready, False if nltk is not installed at all.
    """
    global _NLTK_READY
    if _NLTK_READY:
        return True

    try:
        import nltk
    except ImportError:
        return False

    missing = []
    for path, pkg_id in _REQUIRED_PACKAGES:
        try:
            nltk.data.find(path)
        except LookupError:
            missing.append(pkg_id)

    if missing:
        print(f"\n  [deep] Missing NLTK data packages: {', '.join(missing)}")
        print("  [deep] These are ~40MB in total and stored in ~/nltk_data")
        answer = input("  [deep] Download now? [Y/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            for pkg in missing:
                nltk.download(pkg, quiet=True)
            print("  [deep] Download complete.\n")
        else:
            print("  [deep] Skipped. Run without --deep or install manually.")
            return False

    _NLTK_READY = True
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Layer 4: Lemma-based Type-Token Ratio (Lexical Diversity)
# ─────────────────────────────────────────────────────────────────────────────

def lexical_diversity(text: str) -> Dict:
    """
    Computes the Type-Token Ratio (TTR) using lemmatized words.
    A score close to 1.0 = very diverse vocabulary (human-like).
    A score close to 0.0 = repetitive vocabulary (AI-like).

    Also reports the top 10 most overused lemmas as "repetition flags."
    """
    import nltk
    from nltk.stem import WordNetLemmatizer

    lemmatizer = WordNetLemmatizer()

    # Tokenize and clean
    tokens = nltk.word_tokenize(text.lower())
    content_words = [t for t in tokens if t.isalpha() and len(t) > 2]

    if not content_words:
        return {"ttr": 0.0, "overused_lemmas": [], "total_tokens": 0, "unique_lemmas": 0}

    # Lemmatize each word
    lemmas = [lemmatizer.lemmatize(w) for w in content_words]

    total = len(lemmas)
    unique = len(set(lemmas))
    ttr = round(unique / total, 4) if total > 0 else 0.0

    # Find overused lemmas (appear more than average)
    from collections import Counter
    freq = Counter(lemmas)
    mean_freq = total / max(unique, 1)
    overused = [
        (lemma, count)
        for lemma, count in freq.most_common(20)
        if count > mean_freq * 2
    ]

    return {
        "ttr": ttr,
        "total_tokens": total,
        "unique_lemmas": unique,
        "overused_lemmas": overused[:10],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: N-Gram Perplexity Scoring
# ─────────────────────────────────────────────────────────────────────────────

# Common "AI Triplets" — phrases that are statistically predictable in LLM output.
# This list is curated from real GPT/Claude outputs in academic contexts.
_AI_TRIGRAMS = {
    ("it", "is", "important"),
    ("it", "is", "worth"),
    ("it", "is", "essential"),
    ("in", "order", "to"),
    ("it", "is", "worth", "noting"),
    ("the", "results", "show"),
    ("the", "results", "suggest"),
    ("the", "findings", "suggest"),
    ("this", "is", "because"),
    ("as", "mentioned", "above"),
    ("as", "noted", "above"),
    ("as", "discussed", "above"),
    ("it", "can", "be"),
    ("this", "can", "be"),
    ("there", "is", "a"),
    ("there", "are", "a"),
    ("plays", "a", "crucial"),
    ("plays", "a", "key"),
    ("plays", "a", "vital"),
    ("plays", "a", "significant"),
    ("has", "a", "significant"),
    ("have", "a", "significant"),
    ("it", "should", "be"),
    ("it", "must", "be"),
    ("it", "would", "be"),
    ("this", "study", "aims"),
    ("this", "paper", "aims"),
    ("this", "research", "aims"),
    ("the", "purpose", "of"),
    ("one", "of", "the"),
    ("due", "to", "the"),
    ("based", "on", "the"),
    ("in", "addition", "to"),
    ("with", "respect", "to"),
    ("in", "terms", "of"),
    ("in", "the", "context"),
    ("in", "conclusion", ","),
    ("in", "summary", ","),
    ("in", "the", "literature"),
    ("by", "contrast", ","),
    ("on", "the", "other"),
    ("the", "other", "hand"),
    ("as", "a", "result"),
    ("as", "a", "whole"),
    ("as", "well", "as"),
    ("such", "as", "the"),
    ("that", "is", "to"),
}


def perplexity_score(text: str) -> Dict:
    """
    Scores each sentence by how many 'AI Trigrams' it contains.
    Returns a normalized predictability score (0.0 to 1.0) per sentence.
    Also returns the top 5 most 'boring' sentences for targeted fuzzing.
    """
    import nltk

    sentences_raw = nltk.sent_tokenize(text)
    sentence_scores = []

    for i, sent in enumerate(sentences_raw):
        tokens = nltk.word_tokenize(sent.lower())
        tokens = [t for t in tokens if t.isalpha() or t == ","]

        if len(tokens) < 3:
            sentence_scores.append((i, 0.0, sent))
            continue

        # Generate all trigrams in the sentence
        trigrams_in_sent = set(
            tuple(tokens[j:j+3]) for j in range(len(tokens) - 2)
        )

        hits = trigrams_in_sent & _AI_TRIGRAMS
        # Normalize by sentence length so short sentences aren't unfairly penalized
        score = round(len(hits) / max(len(trigrams_in_sent), 1), 4)
        sentence_scores.append((i, score, sent))

    # Sort by most "predictable" (highest score = most AI-like)
    sorted_scores = sorted(sentence_scores, key=lambda x: x[1], reverse=True)

    mean_score = (
        sum(s for _, s, _ in sentence_scores) / len(sentence_scores)
        if sentence_scores else 0.0
    )

    return {
        "mean_predictability": round(mean_score, 4),
        "hotspots": sorted_scores[:5],
        "all_sentences": sentence_scores,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Layer 5: Modal Verb / Hedge Detection via POS Tagging
# ─────────────────────────────────────────────────────────────────────────────

# Modal verbs that commonly appear in AI academic writing with high certainty
_OVERCONFIDENT_MODALS = {"will", "shall", "must", "is", "are", "was", "were"}
# Hedges that a human researcher would naturally use
_HEDGE_SUGGESTIONS = [
    "arguably", "seemingly", "in certain respects",
    "to some extent", "in some sense", "as it were",
    "by most accounts", "it appears that", "it would seem that",
]


def find_hedge_targets(text: str, rng=None) -> List[Dict]:
    """
    Uses POS tagging to find sentences with:
    - High certainty modals (will, must, is) with no existing hedges.
    - Recommends where to inject a hedge and which hedge to use.
    Returns a list of {sentence_idx, sentence, suggestion, inject_before} dicts.
    """
    import nltk
    import random as _random

    _rng = rng or _random.Random()

    sentences_raw = nltk.sent_tokenize(text)
    targets = []

    for i, sent in enumerate(sentences_raw):
        tokens = nltk.word_tokenize(sent)
        tagged = nltk.pos_tag(tokens)

        # Check if this sentence already has a hedge-like adverb (RB tag)
        has_hedge = any(
            tag.startswith("RB") and word.lower() in {
                "perhaps", "possibly", "arguably", "seemingly",
                "apparently", "supposedly", "presumably", "likely"
            }
            for word, tag in tagged
        )

        if has_hedge:
            continue

        # Find the first verb (VBZ, VBP, MD) to inject a hedge before
        inject_before_idx = None
        for j, (word, tag) in enumerate(tagged):
            if tag in ("VBZ", "VBP", "MD") and word.lower() in _OVERCONFIDENT_MODALS:
                inject_before_idx = j
                break

        if inject_before_idx is not None:
            hedge = _rng.choice(_HEDGE_SUGGESTIONS)
            targets.append({
                "sentence_idx": i,
                "sentence": sent,
                "inject_before_word": tokens[inject_before_idx],
                "hedge_suggestion": hedge,
                "preview": sent.replace(
                    tokens[inject_before_idx],
                    f"{hedge} {tokens[inject_before_idx]}",
                    1
                ),
            })

    return targets


# ─────────────────────────────────────────────────────────────────────────────
# Unified deep_analyze() entry point
# ─────────────────────────────────────────────────────────────────────────────

def deep_analyze(text: str, rng=None) -> Dict:
    """
    Runs all three advanced layers and returns a combined report.
    Caller must ensure bootstrap_nltk() returned True before calling this.
    """
    lex = lexical_diversity(text)
    perp = perplexity_score(text)
    hedges = find_hedge_targets(text, rng)

    # Composite AI-likelihood score (0.0 = very human, 1.0 = very AI)
    ttr_penalty = max(0.0, 0.6 - lex["ttr"])        # Low TTR = AI-like
    perp_penalty = perp["mean_predictability"]       # High predictability = AI
    composite = round(min((ttr_penalty + perp_penalty) / 2.0, 1.0), 4)

    return {
        "composite_ai_score": composite,
        "lexical_diversity": lex,
        "perplexity": perp,
        "hedge_targets": hedges,
    }
