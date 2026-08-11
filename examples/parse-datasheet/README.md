# Example: Parsing a Technical Datasheet

This walkthrough shows a complete parse run on a borderless-spec-table PDF — the failure
mode documented in `docs/document-parsing-field-notes.md` §3.2.

## Step 1 — Probe

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python

$DP scripts/probe_document.py datasheet.pdf
```

```
file      : datasheet.pdf
type      : pdf
chars/page: 847
paths/page: 46
has_images: True
needs_ocr : False
tier      : T2
reason    : sparse text + images → borderless spec table layout
```

The router picks **T2 (Docling)** because the file has few characters per page alongside
images — the signal for a borderless spec table where label/value pairs are aligned
visually, not with borders.

## Step 2 — Parse

```bash
$DP scripts/parse_document.py datasheet.pdf -o out/
```

```
[1/1] datasheet.pdf → T2 docling
  text_recall       : 0.930
  high_value_recall : 0.842   ← below 0.90 threshold
  quality_flags     : ['HIGH_VALUE_MISSING']
  repair            : token-inject → HIGH_VALUE_RECOVERED
  high_value_recall : 1.000   ← after repair
  final flags       : ['HIGH_VALUE_RECOVERED']
✓ out/datasheet.md
```

## Step 3 — Read the output frontmatter

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
repaired_tokens: ["IEC62619", "UN38.3", "IEC62133-2"]
---
```

## Step 4 — Index decision

`HIGH_VALUE_RECOVERED` is an audit trail, not a veto. The file is safe to index.

Files that must **not** be indexed: `PARSE_FAILED`, `EMPTY_SUCCESS`, `TEXT_RECALL_LOW`,
`HIGH_VALUE_MISSING` (after repair failed). For this file, all three blocking flags are
absent — proceed.

---

## What this example exercises

| Check | Result |
|---|---|
| Router picks T2 for borderless spec table | ✓ |
| Docling drops sparse high-value tokens | ✓ (known failure mode) |
| Token-inject repair recovers them | ✓ |
| Final `high_value_recall` ≥ 0.98 | ✓ (1.000) |
| File is safe to index | ✓ |

This is the same scenario as `testdata/regression/datasheet.pdf` in the regression
harness. The expected outcome is captured in `testdata/expected/datasheet.json`.
