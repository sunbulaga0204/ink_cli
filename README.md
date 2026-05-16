# ink — Stealth Text Fuzzer
**Codename**: `break_the_wallv1`

> **Warning**: Use this tool responsibly. The primary objective is educational research into adversarial linguistics. The author denies responsibility for any misuse of this tool.

`ink` is a modular, CLI-first tool designed for adversarial linguistic perturbation of AI-generated text. It uses a multi-layered heuristic approach to inject "human-like" variance into flat, robotic text blocks.

Designed to be pipe-friendly and lightweight, like `pandoc`.

---

## Installation

`ink` is designed to be zero-dependency at its core, but offers an advanced NLTK-powered analysis mode.

### 1. Basic (Zero-Dependency)
```bash
git clone <repo-url>
cd break_the_wallv1
pip install .
```

### 2. Advanced (with NLTK support)
Required for the `--deep` analysis mode.
```bash
pip install .[deep]
```

### System Requirements
- **Python**: 3.8+
- **Pandoc**: (Optional but recommended) Required for handling complex document formats.
  - macOS: `brew install pandoc`
  - Linux: `sudo apt install pandoc`

---

## Usage

### 1. Interactive Mode (Default)
Presents each proposed change one at a time. This is the highest quality mode because you (the human) validate every change.

```bash
# Process a file
ink -i manuscript.md --passes burst,syn,voice

# From stdin (pipe-friendly)
cat draft.md | ink --passes syn,voice > output.md

# With a word limit (split into 2000-word chunks)
ink -i huge_draft.md --limit 2000
```

**Controls:**
- `A` — Apply change
- `S` — Skip (saved to session state)
- `R` — Retry (pull a different variation from the RNG)
- `Q` — Quit and save progress

### 2. Advanced Analysis (`--deep`)
Uses NLTK to perform statistical deep-dives into your text.

```bash
ink -i draft.md --deep
```

**Detects:**
- **Lexical Diversity**: Type-Token Ratio (TTR) using lemma-based analysis.
- **N-Gram Perplexity**: Highlights sentences using high-probability "AI Trigrams."
- **Grammatical Context**: Pinpoints exact locations for hedge injection via POS tagging.

### 3. Batch Mode (`--batch`)
Generate multiple variants automatically using different random seeds.

```bash
ink -i draft.md --batch --count 5
```

---

## Privacy & Stealth

`ink` is built for security researchers and sensitive data.

- **Offline-First**: All core heuristics run locally. No data is sent to an API.
- **Ephemeral Mode**: Run without leaving any session logs or JSON state files on your disk.
  ```bash
  ink -i secret.md --ephemeral
  ```
- **Purge Utility**: Completely remove all downloaded NLTK data models (~40MB) from your machine.
  ```bash
  ink --purge
  ```
- **State Wiping**: Reset the session state for a specific file.
  ```bash
  ink -i draft.md --clear-state
  ```

---

## The Engine Layers

| Pass | Flag | Layer | Description |
|:-----|:-----|:---:|:------------|
| **Burstiness** | `burst` | 2 | Injects sentence length variance. Merges flat sentences, splits monotonous ones. |
| **Synonym Swap** | `syn` | 3 | Replaces "High-Prob" AI words with low-prob synonyms. |
| **Voice Inject** | `voice` | 4 | Injects disfluencies, hedges, and personal openers into robotic sections. |

---

## Architecture

```
break_the_wallv1/
├── ink.py              # Main CLI & Interactive Loop
├── engine/
│   ├── analyzer.py     # Heuristic Heatmap (Standard)
│   ├── deep_analyze.py # NLTK-powered Statistical Engine (Advanced)
│   ├── burst.py        # Burstiness & Variance Engine
│   ├── syn_fuzz.py     # Synonym & POS-safe Swaps
│   └── voice.py        # Contextual Hedge & Voice Injection
└── data/               # Curated adversarial linguistic data
```

---

## Design Philosophy

- **No Models, No GPU**: 100% heuristic. Fast, light, and private.
- **Stochastic Entropy**: Every run is unique due to the seed-based RNG.
- **Semantic Anchor**: We use curated synonyms, not a blind thesaurus, to prevent "meaning drift."
- **Human-in-the-Loop**: The tool works *with* you, not instead of you.
