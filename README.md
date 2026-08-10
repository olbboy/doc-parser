# doc-parse

A Claude Code skill that converts PDF / DOCX / XLSX / PPTX to Markdown by probing each
document first and routing it to the cheapest engine that can actually handle it —
[anydoc](https://github.com/firecrawl/anydoc), [MarkItDown](https://github.com/microsoft/markitdown),
[Docling](https://github.com/docling-project/docling), [MinerU](https://github.com/opendatalab/MinerU) —
then measuring what the engine lost and repairing it.

Every threshold in here came from measurement on a real corpus, and several of them
exist because a reasonable-sounding assumption failed that measurement.

## Why route at all

No engine wins everywhere. Measured on the same documents:

| | anydoc | MarkItDown | Docling | MinerU |
|---|---|---|---|---|
| Speed on Office files | **0.5–20 ms** | 0.02–1.1 s | 0.1–0.9 s | 0.03–0.8 s (HTTP) |
| Dense ruled table | breaks | breaks | **correct** | **correct + real colspan** |
| Borderless spec table (label↔value) | 0/3 | 1/3 | **3/3** | **3/3** |
| Hidden sheets in a workbook | leaks 18/18 | leaks 18/18 | **filters** | **filters** |
| Scanned PDF | clear error | **`ok=True`, 0 chars** | OCR | OCR |
| Vietnamese OCR (diacritics kept) | — | 0% | **97%** (Vision / Tesseract) | **99.8%** (VLM) / 50% (pipeline) |

The failure that matters most is MarkItDown reporting success with empty output on a
scanned PDF: in a bulk pipeline that document enters your index blank and nobody finds out.

## What it does

```
probe (CPU, <100 ms, no models)
  ↓
route → T0 anydoc · T0b MarkItDown · T1 MinerU (Office over HTTP) · T2 Docling · T3 MinerU hybrid
  ↓
gate  → text_recall · high_value_recall · page_absent, all against the PDF's own text layer
  ↓
repair→ page-fill from a text-layer engine · token inject for lost model codes
  ↓
flag  → scored on the final output, after every repair
```

Each output carries YAML frontmatter recording which engine ran, why, what was repaired,
and which quality flags fired — so a bad parse is visible instead of silent.

## Install

```bash
bash scripts/setup-engines.sh          # builds 3 venvs (~3.4 GB) and pre-stages models
```

Needs `uv` and Python 3.12. On Apple Silicon it installs MinerU's MLX backend; on Linux
it wires Tesseract instead of macOS Vision for OCR.

## Use

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python

$DP scripts/probe_document.py file.pdf                 # see which tier it would take
$DP scripts/parse_document.py *.pdf *.xlsx -o parsed/  # convert
$DP scripts/parse_document.py docs/*.pdf -o out/ --dry-run
$DP scripts/test_quality_gates.py                      # unit tests, no PDFs needed
$DP scripts/run_regression.py                          # needs your own fixtures, see below
```

## Two operational rules the measurements forced

1. **Never shell out to the `mineru` CLI in a loop.** It re-imports torch every call:
   6.4 s per file versus 0.03 s through the HTTP service. The skill starts and reuses a
   resident `mineru-api`.
2. **Batch Docling files into one process.** A fresh Docling process spends ~10 s in
   `torch.compile` before its first page. Two files batched took 33 s against 88 s apart.

## Test fixtures are not included

`run_regression.py` expects three PDFs in `testdata/regression/`, each locking a
different failure mode. They are not in this repository because they are partner
documents. `testdata/README.md` describes what each fixture must exercise and what the
expected JSON asserts, so you can substitute your own:

| Fixture | Must exercise |
|---|---|
| `compat-list.pdf` | dense ruled grid the layout engine re-serialises **without losing anything** — the false-positive guard |
| `datasheet.pdf` | borderless spec table that drops a few certification standards — sparse high-value loss |
| `hv48100-p16-18.pdf` | a page the layout engine classifies as a picture and discards — region drop |

`scripts/test_quality_gates.py` needs no PDFs at all and covers the gate arithmetic.

## Notes

`SKILL.md` is the working document and is written in Vietnamese; it carries the full
routing table, the flag semantics, and the reasoning behind each threshold.

## License

MIT
