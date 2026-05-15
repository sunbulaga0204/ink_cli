# ink — Stealth Text Fuzzer
**Codename**: `break_the_wallv1`

> use this responsibly, the primary objective of creating this tool is for educational and adversarial test toward AI detection, I deny responsibility for bad use of this tool.

A modular, CLI-first tool for adversarial linguistic perturbation of AI-generated text.
Designed to be pipe-friendly, like `pandoc`. No internet. No models. No GPU.

---

## Install

```bash
git clone <repo>
cd break_the_wallv1
# No dependencies. Requires Python >= 3.8 only.
python3 ink.py --help
```

---

## Usage

### Interactive Mode (Option A — default)
Presents each proposed change one at a time. You decide.

```bash
# From a file
python3 ink.py -i draft.md --passes burst,syn,voice

# From stdin (pipe-friendly)
cat draft.md | python3 ink.py --passes syn,voice > output.md

# With a fixed seed (reproducible run)
python3 ink.py -i draft.md --seed 42
```

**Interactive Controls:**
- `A` — Apply the proposed change
- `S` — Skip (this word/sentence won't be proposed again in this session)
- `R` — Retry (propose a different synonym or conjunction)
- `Q` — Quit and save progress

---

### Analyze Only (Pre-flight)
Print an AI risk report without making any changes.

```bash
python3 ink.py -i draft.md --analyze
```

**Output includes:**
- `Verdict` — HIGH / MEDIUM / LOW / CLEAN
- `Burstiness` — How uniform your sentence lengths are (low = AI-like)
- `High-Prob Words` — AI-typical words detected
- `GPT Connectors` — Overused transitional phrases detected
- `Hotspots` — Top 3 most AI-like sentences

---

### Batch Mode (Option B)
Generate N variants automatically. Each uses a different seed.

```bash
python3 ink.py -i draft.md --batch --count 5
```

**Output:**
```
draft_v1_entropy_minimal.md
draft_v2_entropy_low.md
draft_v3_entropy_med.md
draft_v4_entropy_high.md
draft_v5_entropy_max.md
```

Upload each to your detector manually. Use the one that passes.

---

## Passes

| Pass | Flag | Description |
|:-----|:-----|:------------|
| Burstiness | `burst` | Merges short uniform sentences; splits long ones. Breaks rhythmic flatness. |
| Synonym Swap | `syn` | Replaces high-probability AI words with lower-probability synonyms. POS-safe. |
| Voice Inject | `voice` | Adds hedges, parentheticals, non-sequiturs, and human-style openers. |

**Canonical Pass Order**: `burst` → `syn` → `voice` (always enforced).

---

## Targets

| Flag | Description |
|:-----|:------------|
| `--target hardened` | For Turnitin/GPTZero. Disables Unicode glitch passes. |
| `--target simple` | For lightweight detectors. Allows all passes. |

---

## State Management

`ink` tracks session state in a hash-scoped file:
```
state/.ink_state_<filename>_<hash>.json
```

- Prevents the same word from being proposed twice.
- Tracks which passes have been applied.
- Survives crashes — resume mid-session.

**Clear state for a fresh start:**
```bash
python3 ink.py -i draft.md --clear-state
```

---

## Architecture

```
break_the_wallv1/
├── ink.py              # Main CLI entry point
├── engine/
│   ├── analyzer.py     # Layer 1: Heuristic heatmap (burstiness + high-prob words)
│   ├── burst.py        # Layer 2: Sentence length variance injector
│   ├── syn_fuzz.py     # Layer 3: Synonym fuzzer (POS-safe)
│   ├── voice.py        # Layer 4: Disfluency & hedge injector
│   └── state.py        # State manager
├── data/
│   ├── high_prob_words.json   # AI-typical word → synonym mappings
│   └── voice_templates.json  # Hedges, parentheticals, bridges
└── state/              # Auto-generated session state files
```

---

## Design Decisions

- **No LLMs, No Models**: 100% heuristic. Under 5MB total. Runs offline.
- **Stochastic**: Every run uses a random seed. No two outputs are identical.
- **POS-Safe Swaps**: Only `Adjective→Adjective`, `Noun→Noun`. Text stays readable.
- **Semantic Anchor**: Synonyms are drawn from curated lists, not a thesaurus, to prevent "meaning drift."
- **Human-in-the-Loop**: The interactive mode ensures a human validates every change before it lands in the final document.

---

## Known Limitations

1. **Proxy Score Problem**: `ink` has no local scoring engine. You must check the output manually against a real detector (GPTZero, Turnitin, etc.).
2. **Batch Mode is Dumb**: Batch mode applies changes blindly without context. Interactive mode is always higher quality.
3. **No PDF/DOCX support (yet)**: Works on `.txt` and `.md` only. Use `pandoc` to convert first.
4. **Voice Injection is Template-Based**: The hedges and openers come from a fixed list. A motivated adversary who knows the list could spot them.
