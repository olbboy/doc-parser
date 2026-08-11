# doc-parser — Claude Code Instructions

> This file is loaded automatically by Claude Code. It defines behaviour for this repository.

## Quick orientation

`doc-parser` is a document-parsing skill router: probe → route (5 tiers) → gate → repair.
The primary skill reference is `docs/SKILL.md`. All routing thresholds are measurement-derived.

## When the user asks to parse a document

1. Run `probe_document.py` first to see which tier the file takes.
2. Run `parse_document.py` with the chosen tier (or let the router decide).
3. Read the `quality_flags` in the YAML frontmatter of the output.
4. If `EMPTY_SUCCESS` or `TEXT_RECALL_LOW` → do not index; escalate tier or retry.

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python
$DP scripts/probe_document.py <file>
$DP scripts/parse_document.py <file> -o out/
```

## Hard rules

- **Never call `mineru` CLI in a loop** — use the HTTP service (0.03 s vs 6.4 s/file).
- **Never split Docling across separate processes** — batch into one call.
- **Never change a threshold without measuring** — see `docs/measurement-driven-upgrade-playbook.md`.
- **Do not index** files flagged `EMPTY_SUCCESS`, `PARSE_FAILED`, `TEXT_RECALL_LOW`, or `HIGH_VALUE_MISSING`.

## Testing

```bash
$DP scripts/test_quality_gates.py    # unit tests, no PDFs needed
$DP scripts/run_regression.py        # regression harness (requires fixture PDFs)
```

## Where things live

```
scripts/parse_document.py      → main pipeline
scripts/probe_document.py      → CPU-only classifier
scripts/quality_gates.py       → gate logic + all threshold constants
scripts/repair_dropped_regions.py  → page-fill + token-inject repair
docs/SKILL.md                  → routing table + flag semantics (authoritative)
docs/document-parsing-field-notes.md   → what was measured
docs/measurement-driven-upgrade-playbook.md → how to change safely
testdata/README.md             → fixture specification
```
