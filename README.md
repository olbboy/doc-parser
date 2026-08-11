# doc-parser

**Route documents to the cheapest parsing engine that can actually handle them.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![CI](https://github.com/olbboy/doc-parser/actions/workflows/test.yml/badge.svg)](https://github.com/olbboy/doc-parser/actions/workflows/test.yml)
[![Release](https://img.shields.io/github/v/release/olbboy/doc-parser?color=green)](https://github.com/olbboy/doc-parser/releases)

---

`doc-parser` converts **PDF / DOCX / XLSX / PPTX** to clean Markdown for RAG ingestion and knowledge-base pipelines. Instead of sending every file through the same parser, it **probes each document first** (CPU-only, < 100 ms, no models), routes it to the cheapest engine that can handle it, measures what the engine dropped, and repairs it.

Every routing threshold comes from measurements on a real corpus of technical documents — not from guessing.

---

## Why routing matters

No single engine wins everywhere. Tested on the same set of documents:

| | anydoc | MarkItDown | Docling | MinerU |
|---|---|---|---|---|
| Speed on Office files | **0.5 – 20 ms** | 23 – 1 076 ms | 94 – 923 ms | 27 – 802 ms (HTTP) |
| Dense ruled table | merges headers | 24 empty separators | **correct columns** | **correct + real colspan** |
| Borderless spec table (label ↔ value) | 0 / 3 | 1 / 3 | **3 / 3** | **3 / 3** |
| Hidden sheets in a workbook | leaks 18 / 18 | leaks 18 / 18 | **filtered** | **filtered** |
| Scanned PDF | clear error | **`ok=True`, 0 chars** | OCR | OCR |
| Vietnamese OCR (diacritics) | — | 0 % | **96 – 97 %** (Vision / Tesseract) | **99.8 %** (VLM) |

The most dangerous failure is MarkItDown silently returning success with empty output on a scanned PDF: the document enters your index as a blank page and nobody notices.

---

## How it works

```
probe    (CPU, <100 ms, no models)
  ↓
route  → T0 anydoc · T0b MarkItDown · T1 MinerU/office · T2 Docling · T3 MinerU/hybrid
  ↓
gate   → text_recall · high_value_recall · page_absent
         (compared against the PDF's own text layer)
  ↓
repair → page-fill from a text-layer engine (region drop)
         token-inject from the text layer (sparse high-value loss)
  ↓
flag   → scored on the final output, after every repair stage
```

Each output file carries YAML frontmatter recording which engine ran, why it was chosen, what was repaired, and which quality flags fired — so a bad parse is visible rather than silent.

### Routing tiers

| Tier | Engine | Used for | Measured cost |
|---|---|---|---|
| **T0** | anydoc | Office (simple), text-layer PDFs | 0.5 – 150 ms/file |
| **T0b** | MarkItDown | `.msg`, `.ipynb`, `.zip`, URLs, audio | — |
| **T1** | MinerU `office` | XLSX with hidden sheets / merged cells, DOCX merged cells, all PPTX | 0.03 – 0.8 s/file |
| **T2** | Docling | Dense-grid PDFs, borderless spec tables, **all scanned PDFs** | 2.1 pages/s |
| **T3** | MinerU `hybrid` | When real `colspan`/`rowspan` or formulas must be preserved | 0.17 pages/s — batch mode |

---

## Quick start

### 1. Prerequisites

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) (fast package installer)
- ~3.4 GB disk space for engine venvs; ~2 GB for models (downloaded once)

### 2. Install engines

```bash
git clone https://github.com/olbboy/doc-parser.git
cd doc-parser
bash scripts/setup-engines.sh
```

On **Apple Silicon** the MinerU MLX backend is installed automatically.  
On **Linux**, Tesseract is wired in place of macOS Vision for OCR.

### 3. Parse documents

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python

# Probe a file — see which tier it would take, with reasons
$DP scripts/probe_document.py report.pdf

# Convert files
$DP scripts/parse_document.py *.pdf *.xlsx -o parsed/

# Dry run — preview the routing plan for a batch
$DP scripts/parse_document.py docs/*.pdf -o out/ --dry-run

# Force a specific engine (useful for debugging or comparing)
$DP scripts/parse_document.py file.pdf -o out/ --engine docling
```

---

## Usage examples

### Probing a document

```
$ $DP scripts/probe_document.py datasheet.pdf

file      : datasheet.pdf
type      : pdf
chars/page: 847
paths/page: 46
has_images: True
needs_ocr : False
tier      : T2
reason    : sparse text + images → borderless spec table layout
```

### Parsing with frontmatter output

Each `.md` file starts with YAML describing the parse:

```yaml
---
parser: docling
parser_tier: T2
parser_reason: sparse text + images → borderless spec table layout
attempts: 1
quality_flags:
  - HIGH_VALUE_RECOVERED
text_recall: 0.952
high_value_recall: 1.000
repaired_pages: [3]
---
```

### Batch conversion

```bash
# Convert an entire folder, skip already-parsed files
$DP scripts/parse_document.py /docs/**/*.pdf -o /parsed/

# Point at a wider corpus for threshold exploration
DOCPARSE_CORPUS_ROOT=/your/corpus $DP scripts/run_regression.py
```

---

## Quality flags

Flags appear in the `quality_flags` frontmatter field. The gate runs on the **final output** (after all repair stages), not on raw engine output.

| Flag | Meaning | Action |
|---|---|---|
| `PARSE_FAILED` | Every engine failed | **Do not index** — add to retry queue |
| `EMPTY_SUCCESS` | Engine reported success but produced 0 chars | **Do not index** — the most dangerous failure mode |
| `HIDDEN_SHEET_LEAK_RISK` | Workbook contains hidden sheets | Review before indexing; hidden sheets in tender workbooks often contain internal pricing |
| `PANDAS_NOISE` | Output contains `NaN` / `Unnamed:` tokens | Switch engine (MarkItDown produced 16 724 `NaN` tokens on one pricing file) |
| `DENSE_TABLE_GRID` | Dense ruled grid detected | Auto-escalated to T2 |
| `BORDERLESS_SPEC_TABLE` | Borderless spec table detected | Auto-escalated to T2 |
| `NO_HEADING_STYLES` | DOCX uses no Heading styles | Fix the template — no parser can recover structure that was never there |
| `LAYOUT_RISK_UNADDRESSED` | Difficult document forced onto a cheaper engine | Reschedule with a higher tier |
| `TEXT_RECALL_LOW` | > 5 % word loss **and** model codes / units lost **or** a content-dead page | **Do not index** |
| `TEXT_RECALL_WATCH` | 2 – 5 % word loss, or > 5 % but high-value tokens intact | Log and index normally |
| `HIGH_VALUE_MISSING` | > 10 % of model codes / units / standards lost after repair | Manual review before indexing |
| `HIGH_VALUE_RECOVERED` | Lost model codes / units recovered from the text layer | See `high_value_recovered` in frontmatter |
| `REGION_DROPPED` | Engine discarded a content region — **auto-repaired** | See `repaired_pages` |
| `REGION_DROPPED_UNREPAIRED` | Region drop detected but repair found nothing to insert | Switch engine |

### Index policy

```
Block:   PARSE_FAILED · EMPTY_SUCCESS · TEXT_RECALL_LOW · HIGH_VALUE_MISSING
         (+ HIDDEN_SHEET_LEAK_RISK for tender workbooks)
Allow:   everything else — WATCH · REGION_DROPPED · HIGH_VALUE_RECOVERED
         are audit trails, not veto flags
```

`high_value_recall = None` does **not** block indexing. A document with fewer than 5 distinct model-code / unit types does not have enough evidence to judge, and absence of evidence is not evidence of loss.

---

## Operational rules

Two constraints the measurements forced — ignoring either significantly degrades throughput or correctness:

1. **Never shell out to the `mineru` CLI in a loop.** Each call re-imports the Python interpreter and torch: measured at 6.4 s/file versus 0.03 s via the HTTP service. The tool starts a resident `mineru-api` process and reuses it.

2. **Batch Docling files into one process.** A fresh Docling process spends ~10 s in `torch.compile` before its first page. Two files batched: 33 s. Two files in separate processes: 88 s.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DOCPARSE_HOME` | `~/.local/share/doc-parse` | Root for all engine venvs and model caches |
| `DOCPARSE_MINERU_URL` | `http://127.0.0.1:8123` | URL of the resident `mineru-api` HTTP service |
| `DOCPARSE_CORPUS_ROOT` | *(none)* | Path to a wider corpus for threshold exploration; the default regression suite always runs regardless |

---

## Testing

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python

# Unit tests — no PDF fixtures needed; covers all gate arithmetic
$DP scripts/test_quality_gates.py

# Regression suite — requires three PDF fixtures (see testdata/README.md)
$DP scripts/run_regression.py
```

The unit tests run in CI on every push and pull request. The regression fixtures are not included in this repository (they are partner documents); `testdata/README.md` describes what each fixture must exercise so you can substitute your own.

---

## Documentation

| File | What it covers |
|---|---|
| [`docs/SKILL.md`](docs/SKILL.md) | Working reference: routing table, flag semantics, index policy, and the reasoning behind each threshold |
| [`docs/document-parsing-field-notes.md`](docs/document-parsing-field-notes.md) | What was measured — engine behaviour, install traps, Vietnamese OCR benchmark, licensing, and the seven conclusions the measurements reversed *(Vietnamese)* |
| [`docs/measurement-driven-upgrade-playbook.md`](docs/measurement-driven-upgrade-playbook.md) | How to change it safely — measure before deciding, metric design, fixture strategy, versioning rules *(Vietnamese)* |
| [`testdata/README.md`](testdata/README.md) | Regression fixture specification — what each of the three fixtures must exercise |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute |

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

---

## License

MIT — see [LICENSE](LICENSE).
