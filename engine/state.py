"""
engine/state.py
State Manager for ink.
Tracks which tokens/sentences have already been fuzzed to prevent
the tool from cycling on the same word indefinitely.
State is stored in a hash-scoped .ink_state_<hash>.json file.
"""

import json
import hashlib
import os
from typing import Dict, List, Set

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "state")


def _ensure_state_dir():
    os.makedirs(_STATE_DIR, exist_ok=True)


def _state_path(source_path: str) -> str:
    """Compute a hash-scoped state file path based on the source filename."""
    _ensure_state_dir()
    h = hashlib.md5(source_path.encode()).hexdigest()[:8]
    basename = os.path.splitext(os.path.basename(source_path))[0]
    return os.path.join(_STATE_DIR, f".ink_state_{basename}_{h}.json")

# ─────────────────────────────────────────────────────────────────────────────
# State schema
# ─────────────────────────────────────────────────────────────────────────────

def _empty_state() -> Dict:
    return {
        "source": "",
        "passes_applied": [],
        "swapped_tokens": {},    # { "original_word": "replacement" }
        "fuzzed_sentences": [],  # indices of sentences that have been touched
        "change_count": 0,
        "skipped_tokens": [],    # tokens the user chose to skip
    }

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_state(source_path: str) -> Dict:
    """Load existing state for a source file, or return a fresh state."""
    path = _state_path(source_path)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    state = _empty_state()
    state["source"] = source_path
    return state


def save_state(source_path: str, state: Dict):
    """Persist the current state to disk."""
    path = _state_path(source_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def record_swap(state: Dict, original: str, replacement: str):
    """Record a successful token swap."""
    state["swapped_tokens"][original.lower()] = replacement
    state["change_count"] += 1


def record_skip(state: Dict, token: str):
    """Record a token the user chose to skip (won't be proposed again)."""
    if token.lower() not in state["skipped_tokens"]:
        state["skipped_tokens"].append(token.lower())


def record_sentence_fuzzed(state: Dict, index: int):
    """Mark a sentence index as having been touched."""
    if index not in state["fuzzed_sentences"]:
        state["fuzzed_sentences"].append(index)
        state["change_count"] += 1


def record_pass(state: Dict, pass_name: str):
    """Log which passes have been applied."""
    if pass_name not in state["passes_applied"]:
        state["passes_applied"].append(pass_name)


def is_token_skipped(state: Dict, token: str) -> bool:
    return token.lower() in state["skipped_tokens"]


def is_token_already_swapped(state: Dict, token: str) -> bool:
    return token.lower() in state["swapped_tokens"]


def clear_state(source_path: str):
    """Delete the state file for a source document (fresh start)."""
    path = _state_path(source_path)
    if os.path.exists(path):
        os.remove(path)


def print_state_summary(state: Dict):
    """Print a human-readable summary of the current session state."""
    print(f"\n{'─'*40}")
    print(f"  Session State Summary")
    print(f"{'─'*40}")
    print(f"  Source     : {state['source']}")
    print(f"  Changes    : {state['change_count']}")
    print(f"  Passes     : {', '.join(state['passes_applied']) or 'none'}")
    print(f"  Swaps made : {len(state['swapped_tokens'])}")
    print(f"  Tokens skipped: {len(state['skipped_tokens'])}")
    print(f"{'─'*40}\n")
