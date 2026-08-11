# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.0.1] — 2026-08-11

### Added

- **`README_AI.md`** — dedicated AI agent bootstrap file (step-by-step setup, routing
  instructions, critical rules, document map, example report format). Inspired by the
  `README_AI.md` pattern in purpose-built skill routers like reverse-skill.
- **`AGENTS.md`** — platform-neutral AI entry point: 30-second routing summary and hard
  rules for any compatible AI client (Claude Code, Cursor, Cline, Codex, …).
- **`CLAUDE.md`** — Claude Code-specific instruction file, auto-loaded by Claude Code;
  provides quick orientation, hard rules, test commands, and file map.
- **`README_vi.md`** — native Vietnamese README mirroring the English README. The field
  notes and playbook are already in Vietnamese; the README now is too.
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


## [2.0.0] — 2026-08-11

### Changed

- **Breaking:** `high_value_recall` now counts *presence* (is this type of token anywhere in the output?)
  instead of *frequency* (how many occurrences survived?). Same document, same engine — the score
  changes. Version bumped to major because any threshold written against v1.x needs re-verification.
  Background: the old counting method produced 3/3 false alarms on 12 documents; the new method
  catches both true losses (0.842 and 0.032) and silences all false alarms.
- `TEXT_RECALL_LOW` can no longer be downgraded to `TEXT_RECALL_WATCH` solely because `high_value_recall`
  is intact. A content-dead page (`page_recall < 0.50` **and** `page_absent ≥ 0.10`) vetoes the
  downgrade — validated on `V5 UL9540A.pdf` where 5 pages (322 words) disappeared while model
  codes remained intact.

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

[Unreleased]: https://github.com/olbboy/doc-parser/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/olbboy/doc-parser/compare/v2.0.0...v1.0.1
[2.0.0]: https://github.com/olbboy/doc-parser/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/olbboy/doc-parser/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/olbboy/doc-parser/releases/tag/v1.0.0

