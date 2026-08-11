## Summary

<!-- One paragraph: what does this PR change and why? -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change — bumps major version per CHANGELOG rules
- [ ] Documentation only
- [ ] CI / tooling

## Checklist

- [ ] `scripts/test_quality_gates.py` passes locally
- [ ] If routing logic or thresholds changed: corpus measurements are included in this PR or linked
- [ ] If a new threshold was added or changed: a unit test at the boundary is included
- [ ] `CHANGELOG.md` is updated in this commit (not in a follow-up)
- [ ] `docs/SKILL.md` is updated if the routing table or flag semantics changed
- [ ] No regression fixture PDFs are committed (they are partner documents — see `testdata/README.md`)
- [ ] No `__pycache__/`, `.pyc`, or venv directories are committed

## Corpus measurement (if applicable)

<!--
Paste a before/after table, e.g.:

| File | Before text_recall | After text_recall | Flag before | Flag after |
|---|---|---|---|---|
| compat-list.pdf | 0.93 | 0.93 | WATCH | WATCH |
| datasheet.pdf   | 0.952 | 0.961 | — | — |

The guard file (compat-list) must not change behaviour.
-->
