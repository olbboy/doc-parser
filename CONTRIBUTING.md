# Contributing to doc-parser

Thank you for your interest in contributing! This document explains how to get set up,
what kinds of contributions are most useful, and how the review process works.

---

## Table of contents

- [Code of conduct](#code-of-conduct)
- [What we are looking for](#what-we-are-looking-for)
- [Development setup](#development-setup)
- [Running the tests](#running-the-tests)
- [Project layout](#project-layout)
- [Adding a new engine](#adding-a-new-engine)
- [Changing a threshold or metric](#changing-a-threshold-or-metric)
- [Submitting a pull request](#submitting-a-pull-request)
- [Reporting bugs](#reporting-bugs)
- [Requesting features](#requesting-features)

---

## Code of conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating you agree to abide by its terms.

---

## What we are looking for

The project accepts:

- **Bug fixes** — especially silent failures (empty success, wrong engine choice, broken repair)
- **New engine adapters** — following the pattern in `scripts/engine_runners/`
- **Additional regression fixtures** — if you have a document class the current three fixtures do not cover
- **Documentation improvements** — clarifications, translations, typo fixes
- **CI improvements** — faster feedback, broader platform coverage
- **Threshold refinements backed by measurements** — see [Changing a threshold or metric](#changing-a-threshold-or-metric)

The project does **not** accept:

- Threshold changes without corpus measurements
- New routing rules based on intuition alone
- Dependencies that require a network connection at parse time

---

## Development setup

### Prerequisites

- Python 3.12 or later
- [`uv`](https://github.com/astral-sh/uv) — used by `setup-engines.sh`

### Install

```bash
git clone https://github.com/olbboy/doc-parser.git
cd doc-parser

# Build the three engine venvs and pre-stage models (~3.4 GB venvs, ~2 GB models)
bash scripts/setup-engines.sh
```

The venvs are installed to `~/.local/share/doc-parse/` (overridable via `DOCPARSE_HOME`).
They are deliberately kept outside the repository so they are never accidentally committed.

### Verify installation

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python
$DP scripts/test_quality_gates.py    # should pass with no PDFs
```

---

## Running the tests

### Unit tests (no PDFs required)

```bash
$DP scripts/test_quality_gates.py
```

Covers all gate arithmetic, threshold boundary behaviour, and `None`-polarity rules.
These run in CI on every push.

### Regression suite (three PDF fixtures required)

```bash
$DP scripts/run_regression.py
```

The three fixtures (`compat-list.pdf`, `datasheet.pdf`, `hv48100-p16-18.pdf`) are not
included in this repository — they are partner documents. See [`testdata/README.md`](testdata/README.md)
for exact properties a substitute must have. Drop your substitutes in `testdata/regression/`
and tune the bands in `testdata/expected/*.json`.

---

## Project layout

```
scripts/
  parse_document.py      # main entry-point: probe → route → gate → repair
  probe_document.py      # CPU-only document classifier
  quality_gates.py       # text_recall / high_value_recall / page_absent gates
  repair_dropped_regions.py  # page-fill and token-inject repair passes
  run_regression.py      # regression harness
  test_quality_gates.py  # unit tests for the gate arithmetic
  scan_unit_variants.py  # corpus-scanning tool for normalization rules
  setup-engines.sh       # builds the three engine venvs
  engine_runners/
    run_anydoc.py
    run_docling.py
    run_markitdown.py
    run_mineru.py
docs/
  SKILL.md                            # routing reference with all thresholds
  document-parsing-field-notes.md     # what was measured (Vietnamese)
  measurement-driven-upgrade-playbook.md  # how to change it safely (Vietnamese)
testdata/
  README.md              # fixture specification
  expected/              # JSON bands for the regression assertions
  regression/            # drop your three fixture PDFs here (not tracked)
```

---

## Adding a new engine

1. Add a runner script in `scripts/engine_runners/run_<name>.py` following the pattern of `run_anydoc.py`. The runner receives `[input_path, output_dir]` on `sys.argv` and writes a `.md` file.

2. Add a venv build step to `scripts/setup-engines.sh`.

3. Add a tier constant and routing condition in `scripts/probe_document.py`.

4. Add a fallback entry in the chain builder in `scripts/parse_document.py`.

5. Measure: run the engine over the full corpus and record the results in `docs/document-parsing-field-notes.md`. Do not add the routing condition without numbers.

---

## Changing a threshold or metric

`doc-parser` follows a measurement-first discipline documented in
[`docs/measurement-driven-upgrade-playbook.md`](docs/measurement-driven-upgrade-playbook.md).
The short version:

1. **Propose** — write down what you want to change and which documents you expect to behave differently.
2. **Measure** — dry-run on a corpus; do not edit code yet.
3. **Verify** — the guard file (`compat-list`) must not change behaviour. Both target and guard must pass.
4. **Implement** — include a unit test at the new threshold boundary in the same commit.
5. **Document** — update `docs/SKILL.md` and `CHANGELOG.md` in the same commit.

PRs that change a threshold without a corpus measurement will not be merged.

---

## Submitting a pull request

1. Fork the repository and create a branch from `main`.
2. Make your changes and run the unit tests.
3. If you changed routing logic: run (or describe) the corpus measurement.
4. Open a pull request. The template will guide you through the checklist.
5. A maintainer will review within a reasonable time. Feedback will be specific and actionable.

Please keep pull requests focused. One logical change per PR makes review faster.

---

## Reporting bugs

Use the [Bug Report issue template](.github/ISSUE_TEMPLATE/bug_report.yml).

The most useful bug reports include:
- The document type and rough description (no confidential content needed)
- Which engine was chosen and which flag fired (check the YAML frontmatter)
- The exact command you ran
- Your OS and Python version

---

## Requesting features

Use the [Feature Request issue template](.github/ISSUE_TEMPLATE/feature_request.yml).

Feature requests that include a description of the failure mode they fix and a proposed measurement method are much more likely to be acted on.
