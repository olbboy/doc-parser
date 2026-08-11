# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 2.x | ✅ Current |
| 1.x | ❌ No longer maintained |

---

## Scope

`doc-parser` is a local document-conversion tool. It does not run a server, make
outbound network requests at parse time (beyond MinerU's local HTTP service on
`127.0.0.1`), or store documents anywhere other than the output directory you specify.

Security concerns most likely to be relevant:

- **File-path traversal** in output naming when parsing attacker-controlled filenames
- **Hidden-sheet leakage** from XLSX files (documented as `HIDDEN_SHEET_LEAK_RISK` flag)
- **Dependency vulnerabilities** in the four parsing engines (anydoc, MarkItDown, Docling, MinerU)
- **Model supply-chain issues** — the tool downloads models from HuggingFace on first run

---

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Use GitHub's [Private Vulnerability Reporting](https://github.com/olbboy/doc-parser/security/advisories/new)
to report the issue confidentially. You will receive a response within **7 days**.

If the vulnerability is confirmed:

1. We will work with you to understand the impact and develop a fix.
2. A patch release will be published as soon as practicable.
3. You will be credited in the release notes unless you prefer to remain anonymous.

---

## Dependency security

The four parsing engines are third-party packages. If you discover a vulnerability
in anydoc, MarkItDown, Docling, or MinerU, please report it directly to those
projects. If the vulnerability affects how `doc-parser` calls those engines (e.g.,
argument injection), report it here.
