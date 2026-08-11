# doc-parser — Agent Bootstrap

> ⚡ **For AI agents only.** Human readers: see [README.md](README.md).

You are an AI agent (Claude Code, Codex, Cursor, Cline, or another compatible client).
This file is your bootstrap. **Read it in full, then execute section 0 immediately.**

---

## 0. Immediate Actions (Execute Now)

```text
1. Detect SKILL_ROOT: the directory containing this file (README_AI.md).
2. Confirm Python 3.12+ is available:
   python3 --version
3. Confirm the engine venvs exist at $DOCPARSE_HOME (~/.local/share/doc-parse/ by default):
   ls ~/.local/share/doc-parse/lite/bin/python   # must exist
   If missing → run: bash scripts/setup-engines.sh
4. Set DP alias for this session:
   DP=$HOME/.local/share/doc-parse/lite/bin/python
5. Run the unit tests to confirm the installation is healthy:
   $DP scripts/test_quality_gates.py
6. Report back the status (see "Example Report" below).
7. Wait for the user's actual task.
```

---

## Routing

When the user asks to parse, convert, or extract from a document:

```
User task
  → probe the file (CPU, <100 ms, no models)
      $DP scripts/probe_document.py <file>
  → route to tier (T0–T3, see docs/SKILL.md)
  → parse
      $DP scripts/parse_document.py <file> -o <outdir>
  → read the quality_flags in the output frontmatter
  → repair or escalate if needed
```

**Never start parsing without probing first.** The probe tells you which engine to use and why.

---

## Critical rules

| Rule | Why |
|---|---|
| Never shell out to `mineru` CLI in a loop | 6.4 s/file vs 0.03 s via HTTP — import cost, not parse cost |
| Never batch Docling as separate processes | Fresh process = ~10 s torch.compile before first page |
| Never index a file flagged `EMPTY_SUCCESS` | Engine reported success but produced 0 chars — most dangerous failure mode |
| Never index a file flagged `PARSE_FAILED` or `TEXT_RECALL_LOW` | Do not index; add to retry queue |
| Do not change routing thresholds without measuring | See `docs/measurement-driven-upgrade-playbook.md` |

---

## Document map (what to read for which task)

| Task | Read |
|---|---|
| Understand routing decisions | `docs/SKILL.md` — routing table, flag semantics, threshold evidence |
| Parse a new document type | `docs/SKILL.md` → routing table → `scripts/probe_document.py` |
| Interpret quality flags | `docs/SKILL.md` → "Quality flags" section |
| Add a new engine | `CONTRIBUTING.md` → "Adding a new engine" |
| Change a threshold | `docs/measurement-driven-upgrade-playbook.md` — read before touching any constant |
| Understand why a threshold is what it is | `docs/document-parsing-field-notes.md` |
| Run regression tests | `testdata/README.md` → `scripts/run_regression.py` |

---

## Environment variables

| Variable | Default | Override |
|---|---|---|
| `DOCPARSE_HOME` | `~/.local/share/doc-parse` | Point to custom venv root |
| `DOCPARSE_MINERU_URL` | `http://127.0.0.1:8123` | Different MinerU API port |
| `DOCPARSE_CORPUS_ROOT` | *(none)* | Path to a wider corpus for threshold work |

---

## Example Report

After completing section 0, output this before asking for the user's task:

```markdown
✅ doc-parser ready

Installation path : <SKILL_ROOT>
Python            : 3.12.x
Engine venvs      : lite ✓  docling ✓  mineru ✓  (or: missing → run setup-engines.sh)
Unit tests        : PASSED (N tests)
MinerU API        : running at http://127.0.0.1:8123  (or: not running — will start on first T1/T3 parse)

Ready. Provide a file path or a batch glob to parse.
```
