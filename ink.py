#!/usr/bin/env python3
"""
ink — The Stealth Text Fuzzer
A modular CLI tool for bypassing AI text detectors via adversarial
linguistic perturbation. Designed like pandoc: pipe-friendly, composable.

Usage:
  ink -i draft.md --passes burst,syn,voice
  cat draft.md | ink --passes syn --seed 42 > out.md

Passes:
  burst   — Sentence length variance injection (Layer 2)
  syn     — Synonym swap (Layer 3)
  voice   — Disfluency & hedge injection (Layer 4)

Flags:
  -i, --input     Input file (default: stdin)
  -o, --output    Output file (default: stdout)
  -p, --passes    Comma-separated passes to run (default: burst,syn,voice)
  -t, --target    Detection target: 'hardened' (Turnitin) or 'simple' (default: hardened)
  -s, --seed      Random seed for reproducibility
  -b, --batch     Batch mode: generate N versions (see --count)
  --count         Number of batch variants (default: 3)
  --analyze       Print analysis report and exit (no changes made)
  --clear-state   Clear session state for this file and exit
  --interactive   (Default) Run the interactive change loop
  --limit         Split output into chunks of N words

Batch Mode (Option B — documented):
  ink -i draft.md --batch --count 5
  Generates draft_v1_entropy_low.md ... draft_v5_entropy_high.md
  Each uses a different seed. User manually checks which version passes.
"""

import sys
import os
import argparse
import random
import re

import shutil

def check_dependencies():
    """Verify that external dependencies like Pandoc are installed."""
    if not shutil.which("pandoc"):
        print(c("  Warning: 'pandoc' not found in PATH.", YELLOW))
        print(c("  Pandoc is required for handling certain document formats and final clean-ups.", DIM))
        print(c("  Install it via: brew install pandoc (macOS) or apt install pandoc (Linux)\n", DIM))

# ─────────────────────────────────────────────────────────────────────────────
# Engine imports
# ─────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(__file__))

from engine import analyzer, burst, syn_fuzz, voice, state

# ─────────────────────────────────────────────────────────────────────────────
# ANSI colors (gracefully degraded if not supported)
# ─────────────────────────────────────────────────────────────────────────────

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def c(text, color): return f"{color}{text}{RESET}"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def read_input(path: str) -> str:
    if path == "-" or path is None:
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_output(path: str, text: str):
    if path == "-" or path is None:
        sys.stdout.write(text)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(c(f"  ✓ Saved to: {path}", GREEN))


def split_by_word_limit(text: str, limit: int) -> list:
    """
    Splits text into chunks of roughly 'limit' words.
    Attempts to split at paragraph boundaries to keep structure intact.
    """
    if not limit or limit <= 0:
        return [text]
    
    # Split by paragraphs (double newlines)
    paragraphs = re.split(r'(\n\n+)', text)
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for part in paragraphs:
        if part.strip() == "":
            current_chunk.append(part)
            continue
            
        words_in_part = len(part.split())
        
        if current_word_count + words_in_part > limit and current_word_count > 0:
            chunks.append("".join(current_chunk).strip())
            current_chunk = [part]
            current_word_count = words_in_part
        else:
            current_chunk.append(part)
            current_word_count += words_in_part
            
    if current_chunk:
        chunks.append("".join(current_chunk).strip())
        
    return chunks


def prompt_user(prompt: str) -> str:
    """Read a single character from the user without requiring Enter."""
    try:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(ch)  # echo the char
        return ch.lower()
    except Exception:
        # Fallback for environments without tty support
        return input(prompt).strip().lower()


def print_banner():
    print(c("""
  ╔══════════════════════════════════════╗
  ║    ink — Stealth Text Fuzzer v1.0    ║
  ║    break_the_wallv1 / codename ink   ║
  ╚══════════════════════════════════════╝
""", CYAN))


def print_analysis(report: dict):
    print(c("\n  ── Analysis Report ──", BOLD))
    print(f"  Verdict        : {c(report['verdict'], YELLOW)}")
    print(f"  Burstiness     : {report['burstiness']} {'(LOW — uniform/AI)' if report['burstiness'] < 0.35 else '(OK)'}")
    print(f"  High-Prob Words: {report['high_prob_count']} detected")
    if report['high_prob_words']:
        print(f"  Words          : {c(', '.join(report['high_prob_words'][:12]), RED)}")
    if report['gpt_connectors']:
        print(f"  GPT Connectors : {c(', '.join(report['gpt_connectors']), RED)}")
    if report['hotspots']:
        print(c("\n  ── Top Hotspots (most AI-like sentences) ──", DIM))
        for idx, score, sent in report['hotspots'][:3]:
            display = (sent[:80] + "...") if len(sent) > 80 else sent
            print(f'  [{idx+1}] score={score:.2f}  "{display}"')
    print()

# ─────────────────────────────────────────────────────────────────────────────
# Interactive loop
# ─────────────────────────────────────────────────────────────────────────────

CANONICAL_PASS_ORDER = ["burst", "syn", "voice"]

def run_interactive(text: str, passes: list, rng: random.Random,
                    source_path: str, target: str) -> str:
    """
    Main interactive loop. Presents proposed changes one at a time.
    User responds with: [A]pply, [S]kip, [R]etry, [Q]uit
    """
    sess = state.load_state(source_path)
    # Split while preserving original whitespace delimiters
    sentences = analyzer.split_sentences(text)
    total_changes = 0

    # Enforce canonical pass order
    ordered_passes = [p for p in CANONICAL_PASS_ORDER if p in passes]

    for pass_name in ordered_passes:
        print(c(f"\n  ══ Pass: {pass_name.upper()} ══", BOLD))
        state.record_pass(sess, pass_name)

        if pass_name == "burst":
            # Pass only the text parts to the burst candidate finder
            candidates = burst.find_burst_candidates([s for s, d in sentences])
            if not candidates:
                print(c("  No burst candidates found in this pass.", DIM))
                continue

            for action, idx, description in candidates:
                if idx >= len(sentences):
                    continue

                print(c(f"\n  [{action.upper()}] {description}", CYAN))

                if action == "merge" and idx + 1 < len(sentences):
                    preview = burst.preview_merge([s for s, d in sentences], idx, rng)
                    print(f"  {c('Original:', DIM)} {sentences[idx][0]}")
                    print(f"            {sentences[idx+1][0]}")
                    print(f"  {c('Proposed:', GREEN)} {preview}")

                elif action == "split":
                    result = burst.preview_split([s for s, d in sentences], idx)
                    if result is None:
                        print(c("  (Could not find a clean split point — skipping)", DIM))
                        continue
                    p1, p2 = result
                    print(f"  {c('Original:', DIM)} {sentences[idx][0]}")
                    print(f"  {c('Proposed:', GREEN)} {p1}")
                    print(f"            {p2}")

                print(c("  >> [A]pply  [S]kip  [R]etry  [Q]uit : ", YELLOW), end="", flush=True)
                ch = prompt_user("")

                if ch == 'q':
                    state.save_state(source_path, sess)
                    return "".join([s + d for s, d in sentences])
                elif ch == 'a':
                    if action == "merge" and idx + 1 < len(sentences):
                        # Use the preview directly
                        # The delimiter after the second sentence (idx+1) is preserved.
                        sentences[idx] = (preview, sentences[idx+1][1])
                        sentences.pop(idx + 1)
                    elif action == "split":
                        # result is (part1, part2)
                        p1, p2 = result
                        # The original delimiter for the whole sentence is kept with p2
                        orig_delim = sentences[idx][1]
                        sentences[idx] = (p1, " ")
                        sentences.insert(idx + 1, (p2, orig_delim))
                    
                    state.record_sentence_fuzzed(sess, idx)
                    total_changes += 1
                    print(c("  ✓ Applied.", GREEN))
                elif ch == 'r':
                    # Retry with a fresh RNG pull
                    if action == "merge" and idx + 1 < len(sentences):
                        new_preview = burst.preview_merge([s for s, d in sentences], idx, rng)
                        print(f"  {c('Retry:', YELLOW)} {new_preview}")
                        print(c("  >> [A]pply  [S]kip  [Q]uit : ", YELLOW), end="", flush=True)
                        ch2 = prompt_user("")
                        if ch2 == 'a':
                            sentences[idx] = (new_preview, sentences[idx+1][1])
                            sentences.pop(idx + 1)
                            total_changes += 1
                            print(c("  ✓ Applied.", GREEN))
                    else:
                        print(c("  (Retry not available for split — skipping)", DIM))
                else:  # 's' or anything else
                    state.record_skip(sess, f"burst_{idx}")
                    print(c("  Skipped.", DIM))

        elif pass_name == "syn":
            # Reconstruct text for analysis
            full_text = "".join([s + d for s, d in sentences])
            report = analyzer.analyze(full_text)
            hotspots = report["hotspots"]
            
            # Propose connector replacements
            connector_cands = syn_fuzz.find_connector_candidates(full_text)
            for phrase, replacements in connector_cands[:3]:
                if state.is_token_skipped(sess, phrase):
                    continue
                replacement = rng.choice(replacements)
                print(c(f"\n  [CONNECTOR] GPT phrase detected:", CYAN))
                print(f"  {c('Original:', DIM)} '{phrase}'")
                print(f"  {c('Proposed:', GREEN)} '{replacement}'")
                print(c("  >> [A]pply  [S]kip  [Q]uit : ", YELLOW), end="", flush=True)
                ch = prompt_user("")
                if ch == 'q':
                    state.save_state(source_path, sess)
                    return "".join([s + d for s, d in sentences])
                elif ch == 'a':
                    sentences = [(s.replace(phrase, replacement), d) for s, d in sentences]
                    state.record_swap(sess, phrase, replacement)
                    total_changes += 1
                    print(c("  ✓ Applied.", GREEN))
                else:
                    state.record_skip(sess, phrase)
                    print(c("  Skipped.", DIM))

            # Word-level swaps on hotspot sentences
            for idx, score, _ in hotspots:
                if idx >= len(sentences):
                    continue
                sent = sentences[idx][0]
                proposal = syn_fuzz.propose_swap(sent, rng)
                if proposal is None:
                    continue
                original, replacement, pos = proposal
                if state.is_token_skipped(sess, original) or state.is_token_already_swapped(sess, original):
                    continue

                print(c(f"\n  [SYN-SWAP] Sentence {idx+1} (score={score:.2f}):", CYAN))
                print(f"  {c('Original:', DIM)} {sent}")
                highlighted = sent.replace(original, c(original, RED))
                print(f"  {c('Flagged :', DIM)} {highlighted}")
                new_sent = syn_fuzz.apply_swap(sent, original, replacement)
                highlighted_new = new_sent.replace(replacement, c(replacement, GREEN))
                print(f"  {c('Proposed:', GREEN)} {highlighted_new}")
                print(f"  {c('POS Category:', DIM)} {pos}")
                print(c("  >> [A]pply  [S]kip  [R]etry  [Q]uit : ", YELLOW), end="", flush=True)
                ch = prompt_user("")

                if ch == 'q':
                    state.save_state(source_path, sess)
                    return "".join([s + d for s, d in sentences])
                elif ch == 'a':
                    sentences[idx] = (new_sent, sentences[idx][1])
                    state.record_swap(sess, original, replacement)
                    state.record_sentence_fuzzed(sess, idx)
                    total_changes += 1
                    print(c("  ✓ Applied.", GREEN))
                elif ch == 'r':
                    proposal2 = syn_fuzz.propose_swap(sent, rng)
                    if proposal2:
                        o2, r2, p2 = proposal2
                        new_sent2 = syn_fuzz.apply_swap(sent, o2, r2)
                        print(f"  {c('Retry:', YELLOW)} {new_sent2}")
                        print(c("  >> [A]pply  [S]kip  [Q]uit : ", YELLOW), end="", flush=True)
                        ch2 = prompt_user("")
                        if ch2 == 'a':
                            sentences[idx] = (new_sent2, sentences[idx][1])
                            state.record_swap(sess, o2, r2)
                            total_changes += 1
                            print(c("  ✓ Applied.", GREEN))
                        else:
                            state.record_skip(sess, o2)
                    else:
                        print(c("  (No alternative found — skipping)", DIM))
                else:
                    state.record_skip(sess, original)
                    print(c("  Skipped.", DIM))

        elif pass_name == "voice":
            candidates = voice.find_voice_candidates([s for s, d in sentences], rng)
            if not candidates:
                print(c("  No voice injection candidates found.", DIM))
                continue

            # Sort candidates by index (descending) to handle bridge insertions safely
            candidates.sort(key=lambda x: x[0], reverse=True)

            for idx, action, preview in candidates:
                if idx >= len(sentences):
                    continue

                print(c(f"\n  [VOICE/{action.upper()}] Sentence {idx+1}:", CYAN))
                print(f"  {c('Original:', DIM)} {sentences[idx][0]}")
                print(f"  {c('Proposed:', GREEN)} {preview}")
                print(c("  >> [A]pply  [S]kip  [Q]uit : ", YELLOW), end="", flush=True)
                ch = prompt_user("")

                if ch == 'q':
                    state.save_state(source_path, sess)
                    return "".join([s + d for s, d in sentences])
                elif ch == 'a':
                    if action == "bridge":
                        # preview is the bridge sentence itself
                        sentences.insert(idx, (preview, "\n\n"))
                    else:
                        # preview is the fully transformed sentence
                        sentences[idx] = (preview, sentences[idx][1])
                    
                    state.record_sentence_fuzzed(sess, idx)
                    total_changes += 1
                    print(c("  ✓ Applied.", GREEN))
                else:
                    print(c("  Skipped.", DIM))

    state.save_state(source_path, sess)
    print(c(f"\n  ── Session complete. {total_changes} change(s) applied. ──", BOLD))
    state.print_state_summary(sess)
    # Perfect reconstruction using preserved delimiters
    return "".join([s + d for s, d in sentences])

# ─────────────────────────────────────────────────────────────────────────────
# Batch mode (Option B — documented)
# ─────────────────────────────────────────────────────────────────────────────

ENTROPY_LABELS = ["entropy_minimal", "entropy_low", "entropy_med", "entropy_high", "entropy_max"]

def run_batch(text: str, passes: list, count: int, source_path: str):
    """
    Generate `count` variants of the document, each with a different seed.
    Applies all passes automatically (no user interaction).
    Output: draft_v1_entropy_low.md ... draft_vN.md
    """
    base = os.path.splitext(source_path)[0] if source_path != "-" else "draft"
    print(c(f"\n  ── Batch Mode: generating {count} variants ──", BOLD))

    for i in range(count):
        seed = random.randint(0, 99999)
        rng = random.Random(seed)
        label = ENTROPY_LABELS[min(i, len(ENTROPY_LABELS)-1)]
        out_path = f"{base}_v{i+1}_{label}.md"

        # Auto-apply all passes silently
        sentences = analyzer.split_sentences(text)

        if "burst" in passes:
            candidates = burst.find_burst_candidates([s for s, d in sentences])
            # Process in reverse to keep indices stable for splits/merges
            candidates.sort(key=lambda x: x[1], reverse=True)
            for action, idx, _ in candidates:
                if idx >= len(sentences):
                    continue
                if action == "merge" and idx + 1 < len(sentences):
                    # Preview is the merged string
                    merged = burst.preview_merge([s for s, d in sentences], idx, rng)
                    sentences[idx] = (merged, sentences[idx+1][1])
                    sentences.pop(idx + 1)
                elif action == "split":
                    res = burst.preview_split([s for s, d in sentences], idx)
                    if res:
                        p1, p2 = res
                        orig_delim = sentences[idx][1]
                        sentences[idx] = (p1, " ")
                        sentences.insert(idx + 1, (p2, orig_delim))

        if "syn" in passes:
            full_txt = "".join([s + d for s, d in sentences])
            report = analyzer.analyze(full_txt)
            for idx, _, _ in report["hotspots"]:
                if idx >= len(sentences):
                    continue
                proposal = syn_fuzz.propose_swap(sentences[idx][0], rng)
                if proposal:
                    original, replacement, _ = proposal
                    new_s = syn_fuzz.apply_swap(sentences[idx][0], original, replacement)
                    sentences[idx] = (new_s, sentences[idx][1])

        if "voice" in passes:
            vcandidates = voice.find_voice_candidates([s for s, d in sentences], rng, max_per_pass=2)
            vcandidates.sort(key=lambda x: x[0], reverse=True)
            for idx, action, preview in vcandidates:
                if idx >= len(sentences):
                    continue
                if action == "bridge":
                    sentences.insert(idx, (preview, "\n\n"))
                else:
                    sentences[idx] = (preview, sentences[idx][1])

        output = "".join([s + d for s, d in sentences])
        write_output(out_path, output)
        print(c(f"  [{i+1}/{count}] Seed={seed} → {out_path}", GREEN))

    print(c(f"\n  Done. Run each variant through your detector manually.", CYAN))

# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    check_dependencies()
    parser = argparse.ArgumentParser(
        prog="ink",
        description="ink — Stealth Text Fuzzer. Bypass AI text detectors via adversarial linguistic perturbation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--input",   default="-",  help="Input file path (default: stdin)")
    parser.add_argument("-o", "--output",  default=None, help="Output file path (default: stdout)")
    parser.add_argument("-p", "--passes",  default="burst,syn,voice", help="Comma-separated passes")
    parser.add_argument("-t", "--target",  default="hardened", choices=["hardened", "simple"], help="Detection target")
    parser.add_argument("-s", "--seed",    type=int, default=None, help="Random seed")
    parser.add_argument("-b", "--batch",   action="store_true", help="Enable batch mode")
    parser.add_argument("--count",         type=int, default=3, help="Number of batch variants")
    parser.add_argument("--analyze",       action="store_true", help="Print analysis report and exit")
    parser.add_argument("--clear-state",   action="store_true", help="Clear session state for input file")
    parser.add_argument("--limit",         type=int, default=None, help="Split output into chunks of N words")
    args = parser.parse_args()

    print_banner()

    # ── Read input ──
    source_path = args.input if args.input != "-" else "-"
    text = read_input(source_path)
    if not text.strip():
        print(c("  Error: Empty input.", RED))
        sys.exit(1)

    # ── Clear state ──
    if args.clear_state:
        state.clear_state(source_path)
        print(c(f"  Session state cleared for: {source_path}", GREEN))
        sys.exit(0)

    # ── Analysis only ──
    if args.analyze:
        report = analyzer.analyze(text)
        print_analysis(report)
        sys.exit(0)

    # ── Parse passes ──
    passes = [p.strip() for p in args.passes.split(",") if p.strip()]
    valid_passes = {"burst", "syn", "voice"}
    passes = [p for p in passes if p in valid_passes]
    
    if not passes and not args.limit:
        print(c("  Error: No valid passes specified. Use: burst, syn, voice (or just use --limit to split)", RED))
        sys.exit(1)

    # In 'hardened' mode, remove 'glitch' if someone added it
    if args.target == "hardened" and "glitch" in passes:
        passes.remove("glitch")
        print(c("  [hardened mode] 'glitch' pass disabled (Turnitin normalizes Unicode).", YELLOW))

    # ── RNG setup ──
    seed = args.seed if args.seed is not None else random.randint(0, 99999)
    rng = random.Random(seed)
    print(c(f"  Seed: {seed}  |  Target: {args.target}  |  Passes: {', '.join(passes)}", DIM))

    # ── Run analysis first as a pre-flight ──
    report = analyzer.analyze(text)
    print_analysis(report)

    # ── Batch mode ──
    if args.batch:
        run_batch(text, passes, args.count, source_path)
        return

    # ── Interactive mode ──
    output_text = run_interactive(text, passes, rng, source_path, args.target)

    # ── Write output ──
    # Always resolve to a canonical _inked.md path so that running the tool
    # multiple times on the same document (or its _inked output) accumulates
    # all changes in ONE file instead of creating _inked_inked_inked.md chains.
    if args.output:
        out_path = args.output
    elif source_path == "-":
        out_path = None
    else:
        base = os.path.splitext(source_path)[0]
        # Strip any trailing _inked suffixes so we always write to <base>_inked.md
        while base.endswith("_inked"):
            base = base[: -len("_inked")]
        out_path = base + "_inked.md"

    if args.limit and out_path:
        chunks = split_by_word_limit(output_text, args.limit)
        if len(chunks) > 1:
            base_out = os.path.splitext(out_path)[0]
            ext = os.path.splitext(out_path)[1]
            print(c(f"\n  ── Splitting into {len(chunks)} parts (limit: {args.limit} words) ──", BOLD))
            for i, chunk in enumerate(chunks):
                chunk_path = f"{base_out}_part{i+1}{ext}"
                write_output(chunk_path, chunk)
            return
    
    write_output(out_path, output_text)


if __name__ == "__main__":
    main()
