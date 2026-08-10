# testdata — the minimal regression set

Three PDFs, three **different failure modes**. This is not a random sample: each one
locks a behaviour that a change to the gates or the repair path can easily break, and
two of them only mean anything side by side.

**The PDFs themselves are not in this repository** — they are partner documents. What is
here is the harness and the expected behaviour, so you can supply equivalents from your
own corpus. Drop them in `testdata/regression/` under the filenames below.

| Fixture | Failure mode it locks | Correct behaviour |
|---|---|---|
| `compat-list.pdf` | **False-positive guard.** A dense ruled grid (measured 5,078 vector paths per page) that the layout engine re-serialises, so `text_recall` falls to ~0.93 while **nothing is lost** | `TEXT_RECALL_WATCH` only; **no** repair, **no** `HIGH_VALUE_MISSING` |
| `datasheet.pdf` | **Sparse high-value drop.** A borderless spec table that loses a handful of certification standards (IEC / UN) while prose stays almost intact | `HIGH_VALUE_RECOVERED` after the token inject; final `high_value_recall` ≥ 0.98 |
| `hv48100-p16-18.pdf` | **Region drop.** A nameplate table the layout engine classifies as a picture and discards entirely | `REGION_DROPPED` plus a page-fill repair; `text_recall` recovers from ~0.64 to ~0.99 |

`compat-list` and `hv48100` are both dense ruled grids with opposite outcomes — one is
parsed perfectly, the other is thrown away. That pair is exactly why the router must not
use vector-path density to decide whether to repair. Dropping either one loses the
ability to detect that regression.

## What a substitute needs

| Fixture | Minimum properties |
|---|---|
| `compat-list.pdf` | multi-page table with ruling lines, two-tier header, a column of repeated single-character cells (ticks), and content the layout engine handles well |
| `datasheet.pdf` | 1–3 pages, a spec table drawn without borders, at least 15 distinct model codes / units / standards, some of which a layout engine drops |
| `hv48100-p16-18.pdf` | a page whose table is drawn densely enough that a layout engine labels it a picture; needs `--engine docling` forced, since a clean text layer routes the file to T0 |

Tune the bands in `expected/*.json` to your substitutes. Keep them as **bands**, never
exact floats: `datasheet` legitimately moved from 0.571 to 0.536 when the high-value
pattern learned to see `UN38.3` — same behaviour, different denominator. Pinning `0.571`
would have turned a correct improvement into a red test.

## Running

```bash
$HOME/.local/share/doc-parse/lite/bin/python scripts/run_regression.py
```

`scripts/test_quality_gates.py` needs no PDFs at all and covers the gate arithmetic,
including the threshold neighbourhoods the corpus never exercised.

A wider corpus, for threshold work rather than regression, can be pointed at through
`DOCPARSE_CORPUS_ROOT`; the default gate always runs on these three.
