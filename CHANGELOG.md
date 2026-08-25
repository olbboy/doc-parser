# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed

- `region_dropped_pages()` skipped pages by *distinct word types* while `evaluate()`
  scores them by *total occurrences*. A page of repeated technical tokens — the exact
  profile of a nameplate table — could get a real sub-threshold page recall and still be
  excluded from region-drop detection, so `REGION_DROPPED` never fired and the page-fill
  repair never ran. Both now use the same `MIN_PAGE_WORDS` definition.
- The high-value inject read `(high_value_recall or 1)`, turning a real `0.0` — every
  model code and unit gone, the worst case the inject exists for — into "unmeasured" and
  skipping the repair. Replaced by `needs_hv_inject()`, which distinguishes `0.0` from `None`.
- A file the prober could not open (corrupt, encrypted, wrong extension) raised `KeyError`
  in `route()` and killed the whole batch. It now routes to the broadest engine, carries
  `PROBE_FAILED`, and `main()` isolates a per-file crash instead of aborting the run.
- Page-marker segments are now validated against the PDF's real page count
  (`aligned_pages()`). Docling emits a break only between pages that produced items, so a
  page yielding none shifted every later segment onto the wrong physical page — scoring
  and repairing against a neighbour.
- `split_blocks()` glued a donor table to the prose after it across a blank line; the
  merged block's mixed vocabulary then mapped to the wrong page.
- `recover()` reported a page as repaired even when the bounds guard wrote nothing,
  turning a silent drop into a clean-looking `repaired_pages`.
- `run_gates()` swallowed every gate exception and returned `{}`, indistinguishable from
  "nothing to score". Failures now surface as `GATE_EVAL_FAILED` plus a `gate_error` field.
- `--tier` was accepted, threaded through and never applied, leaving T3 (MinerU
  `hybrid-engine`) unreachable by any documented means. It now selects the tier's engine,
  rejects unknown tiers, and disables Docling pre-batching so it cannot override the choice.
- `run_docling_batch()` split on a plain-text sentinel without checking the result count;
  a document containing that string silently shifted output onto the wrong source file.
- `_run()` raised `IndexError` instead of `RuntimeError` when a failed subprocess emitted
  only whitespace; the `pages` frontmatter field dropped a legitimate `0`.
- `pyproject.toml`: the `anydoc` extra named a package that is published as
  `firecrawl-anydoc`, and the `mineru` extra omitted `six`/`requests` — the undeclared
  dependency whose absence surfaces as a misleading `HybridDependencyError`.
- `scan_unit_variants.py` now reads `DOCPARSE_CORPUS_ROOT`, which every README documented
  but no script had ever read.

### Added

- `PROBE_FAILED` and `GATE_EVAL_FAILED` quality flags — **audit-only**, like
  `MOJIBAKE_SUSPECT` and `TABLE_STRUCTURE_BROKEN`; not in the index block-list until
  there is more than one calibration positive each.
- `PROBE_FAILED_UNVERIFIED` — the first new **blocking** flag: the probe could not open
  the file *and* `readable_ratio` could not be measured, so nothing says the output is
  text. `PROBE_FAILED` alone deliberately does not block: measured on three files that
  all carry it, two are garbage (`%PDF-1.4 broken garbage`, `not a pdf`) and the third is
  a good PDF saved under an `.xlsx` name that parses in full at `readable_ratio` 0.329.
  Known cost: a short or non-Latin document also yields no ratio, so a failed probe on
  one blocks it. Calibrated on three files — widen before bulk reliance.
- Release workflow asserts the pushed tag matches `pyproject.toml` and `VERSION` before
  building, and CI runs `ruff` against the repo's own config.
- Unit tests covering every fix above, each verified by mutation (reverting the fix turns
  the test red). `region_dropped_pages()`, `aligned_pages()` and `split_blocks()` had no
  coverage at all before.

### Documentation

- Flag tables in `README.md`, `README_vi.md` and `docs/SKILL.md` now list every flag the
  code actually emits, including `NEEDS_OCR` and `LAYOUT_RISK_MEDIUM`.
- `docs/SKILL.md` quick-start used a `.claude/skills/doc-parse/scripts` path that does not
  exist in this repo; its "known limitations" section still called mojibake unaddressed
  and cited a filter rule that was never in the code.
- `DOCPARSE_CORPUS_ROOT` is documented as belonging to `scan_unit_variants.py`, not the parser.
- `README.md` and `README_vi.md` state that **T3 is never routed automatically** — the probe
  measures nothing that implies a real `colspan` or a formula, and T3 is 12× slower than T2.
- `docs/SKILL.md` records a third known limitation: `normalize()` folds unit spacing but not
  spacing inside certification standards, so `IEC 62619` against `IEC62619` scores
  `high_value_recall` 0.000 with nothing actually lost. Measurement shows the folding rule
  would be a no-op except on disagreement and would not dilute the token bag; what is still
  missing is evidence that any engine disagrees. Measure with `scan_unit_variants.py` first.
- `run_regression.py` points at `testdata/README.md` when a fixture is missing.

---

## [2.0.1] — 2026-08-11

### Fixed

- CI: add `pyyaml` to the test workflow install step — the "Validate YAML templates"
  job imported `yaml` but the package was not installed, causing `ModuleNotFoundError`
  on both Python 3.12 and 3.13 runners.
- Add `release.yml` GitHub Actions workflow: automatically creates a GitHub Release with
  notes extracted from `CHANGELOG.md` and uploads `sdist` + `wheel` when a `vX.Y.Z`
  tag is pushed.
- `VERSION` file synced to match `pyproject.toml` (was `1.0.1`, now `2.0.1`).
- `CHANGELOG.md` section order corrected to newest-first; comparison links were
  backwards and have been fixed.

---

## [2.0.0] — 2026-08-11

### Changed

- **Breaking:** `high_value_recall` now counts *presence* (is this type of token anywhere in the
  output?) instead of *frequency* (how many occurrences survived?). Same document, same engine —
  the score changes. Version bumped to major because any threshold written against v1.x needs
  re-verification. Background: the old counting method produced 3/3 false alarms on 12 documents;
  the new method catches both true losses (0.842 and 0.032) and silences all false alarms.
- `TEXT_RECALL_LOW` can no longer be downgraded to `TEXT_RECALL_WATCH` solely because
  `high_value_recall` is intact. A content-dead page (`page_recall < 0.50` **and**
  `page_absent ≥ 0.10`) vetoes the downgrade — validated on `V5 UL9540A.pdf` where 5 pages
  (322 words) disappeared while model codes remained intact.

### Added

- `page_absent` metric: fraction of a page's vocabulary that is absent from the *entire* document,
  not just the expected page position. Immune to header repetition.
- `content_dead_pages` list in frontmatter: pages where both `page_recall < 0.50` and
  `page_absent ≥ 0.10`. Distinct from `low_recall_pages` (which uses the less stringent
  `page_recall < 0.90` threshold).
- `HIGH_VALUE_RECOVERED` flag: raised when token-inject successfully restored lost model
  codes / units / standards from the text layer.
- Token-inject repair pass: appends individual text-layer lines that contain lost high-value
  tokens directly to the Markdown body, without touching existing tables. Documented in
  `docs/SKILL.md` under "Two repair passes, two loss types".
- `scan_unit_variants.py`: corpus-scanning tool to audit which unit spellings actually appear
  before adding normalization rules.

### Fixed

- Fallback chain for scanned PDFs now correctly excludes MinerU `pipeline` backend (which has
  no Vietnamese OCR support). Previously `parse_one` assigned `backend="pipeline"` to all
  tiers other than T3, silently destroying diacritics on Vietnamese scans that Docling failed.
- Output filename collision: when `file.pdf` and `file.xlsx` were parsed into the same output
  directory, the second run silently overwrote the first. Stem collision now writes
  `<stem>-<ext>.md` for the conflicting file.
- MinerU API scratch directories now created in a temp path, not CWD. Previously spawning the
  API from the repository root wrote ~43 MB of task directories into `output/`.

---

## [1.1.0] — 2026-08-10

### Added

- Quality gate layer: `text_recall`, `high_value_recall`, and `page_recalls` — all measured
  against the PDF's own text layer rather than against expected output lengths.
- Two-stage repair pipeline: page-fill (region drop) and sparse token-inject (high-value drop).
- Regression harness (`run_regression.py`) with three fixture slots covering the three
  canonical failure modes: false-positive guard, sparse high-value drop, region drop.
- `YAML` frontmatter on every output file: `parser`, `parser_tier`, `parser_reason`,
  `attempts`, `quality_flags`, and metric values.
- `HIDDEN_SHEET_LEAK_RISK` flag: raised when a workbook contains hidden sheets.
  Measured: anydoc and MarkItDown both leak all 18 hidden sheets in a 32-sheet test workbook.

### Changed

- Router escalates PDFs with `chars/page < 50` directly to T2 (Docling with OCR), bypassing
  MarkItDown entirely — MarkItDown returns `ok=True` with 0 characters on scanned PDFs.
- DOCX routing counts both `gridSpan` *and* `vMerge` for merged-cell detection; counting only
  `gridSpan` missed 5 of 13 tables with vertical merges.

---

## [1.0.1] — 2026-08-11

### Added

- **`README_AI.md`** — dedicated AI agent bootstrap file (step-by-step setup, routing
  instructions, critical rules, document map, example report format).
- **`AGENTS.md`** — platform-neutral AI entry point: 30-second routing summary and hard
  rules for any compatible AI client (Claude Code, Cursor, Cline, Codex, …).
- **`CLAUDE.md`** — Claude Code-specific instruction file, auto-loaded by Claude Code;
  provides quick orientation, hard rules, test commands, and file map.
- **`README_vi.md`** — native Vietnamese README mirroring the English README.
- **`VERSION`** — standalone plaintext version file; machine-readable single source of
  truth alongside `pyproject.toml` and git tags.
- **`.gitattributes`** — enforces LF on `.sh/.py/.json/.md/.yml/.toml` and CRLF on
  `.ps1/.bat`; prevents mixed-EOL commits that dirty `git status` on fresh clones.
- **`examples/parse-datasheet/README.md`** — end-to-end walkthrough: probe, parse, read
  frontmatter, make index decision. Exercises the borderless-spec-table failure mode.
- **`docs/assets/doc-parser.png`** — project logo icon for the README header.
- **Centered README layout** — logo, tagline, badge row, and navigation link bar all
  centered with HTML `<p align="center">`. Follows modern open source README standards.
- **`🌐 Tiếng Việt` nav link** in the English README pointing to `README_vi.md`.
- **`back to top` links** at every major section of the README.
- **AI agent callout** at the top of the About section pointing to `README_AI.md`.

### Changed

- `README.md` fully rewritten with centered layout, logo, nav links, i18n link, AI
  bootstrap pointer, and `back to top` links throughout.
- `.gitignore` expanded: venvs, IDE files, OS artefacts (`.DS_Store`, `Thumbs.db`),
  coverage artefacts, MinerU `output/` scratch directory.

---

## [1.0.0] — 2026-08-10

### Added

- Initial release: probe → route (5 tiers) → engine adapter (anydoc, MarkItDown, Docling, MinerU).
- `probe_document.py`: CPU-only document classifier; no models loaded.
- `parse_document.py`: full pipeline with per-failure chain rebuild.
- `setup-engines.sh`: builds three isolated venvs and pre-stages models.
- `scripts/engine_runners/`: thin adapter scripts for each engine.
- Routing thresholds derived from measurements on a corpus of technical documents
  (datasheets, compatibility lists, user manuals, pricing workbooks).
- Two operational rules documented and enforced: resident MinerU HTTP service,
  batched Docling processes.

---

[Unreleased]: https://github.com/olbboy/doc-parser/compare/v2.0.1...HEAD
[2.0.1]: https://github.com/olbboy/doc-parser/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/olbboy/doc-parser/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/olbboy/doc-parser/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/olbboy/doc-parser/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/olbboy/doc-parser/releases/tag/v1.0.0
