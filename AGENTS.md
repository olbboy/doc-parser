# doc-parser — Agent Entry Point

This is a **document-parsing skill router**: probe → route → gate → repair.

> If you are an AI agent, read [README_AI.md](README_AI.md) and execute it immediately.
> If you are a human, see [README.md](README.md).

## Routing (30-second version)

```text
User wants to parse a document
  → $DP scripts/probe_document.py <file>     # pick tier
  → $DP scripts/parse_document.py <file> -o out/  # parse
  → read quality_flags in output frontmatter     # decide whether to index
```

## Hard rules

- `EMPTY_SUCCESS` or `TEXT_RECALL_LOW` → **do not index**, retry with higher tier
- Never call `mineru` CLI in a loop — use the resident HTTP service
- Never change a threshold without measuring first (`docs/measurement-driven-upgrade-playbook.md`)

## Key files

| File | Purpose |
|---|---|
| `docs/SKILL.md` | Routing table, flag semantics, threshold evidence |
| `docs/document-parsing-field-notes.md` | What was measured (Vietnamese) |
| `docs/measurement-driven-upgrade-playbook.md` | How to change safely (Vietnamese) |
| `README_AI.md` | Full AI bootstrap — read this first |
