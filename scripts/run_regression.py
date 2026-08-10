#!/usr/bin/env python3
"""Run the three regression fixtures and assert the behaviour they pin.

Each fixture locks a different failure mode, and two of them only mean something
side by side: `compat-list` and `hv48100` are both dense ruled grids, but Docling
parses one perfectly and throws the other away. A change that makes either one pass
alone is not a fix.

Assertions are on behaviour bands, never on exact floats — `datasheet` legitimately
moved from 0.571 to 0.536 when the high-value pattern learned to see `UN38.3`, same
behaviour, different denominator.

Usage: run_regression.py [--keep] [name ...]
"""
import argparse, json, pathlib, re, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).parent
TESTDATA = HERE.parent / "testdata"
PARSE = HERE / "parse_document.py"


def frontmatter(md_path):
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    head, _, body = text[4:].partition("\n---\n")
    fm = {}
    for line in head.splitlines():
        key, _, raw = line.partition(":")
        try:
            fm[key.strip()] = json.loads(raw.strip())
        except Exception:
            fm[key.strip()] = raw.strip()
    return fm, body


def check(name, spec, fm, body):
    """Return a list of failure strings; empty means the case passed."""
    bad = []
    flags = fm.get("quality_flags") or []
    parser = str(fm.get("parser"))

    if spec.get("parser_contains") and spec["parser_contains"] not in parser:
        bad.append(f"parser={parser!r} không chứa {spec['parser_contains']!r}")
    for f in spec.get("must_flags", []):
        if f not in flags:
            bad.append(f"thiếu cờ {f}")
    for f in spec.get("must_not_flags", []):
        if f in flags:
            bad.append(f"có cờ không mong muốn {f}")

    for key, bound, cmp in (("text_recall", "text_recall_min", "min"),
                            ("text_recall", "text_recall_max", "max"),
                            ("high_value_recall", "high_value_recall_min", "min"),
                            ("high_value_recall", "high_value_recall_max", "max")):
        if bound not in spec:
            continue
        got = fm.get(key)
        if got is None:
            bad.append(f"{key} không có trong frontmatter")
        elif cmp == "min" and got < spec[bound]:
            bad.append(f"{key}={got} < {spec[bound]}")
        elif cmp == "max" and got > spec[bound]:
            bad.append(f"{key}={got} > {spec[bound]}")

    # Page markers are an internal gate anchor; leaking them would pollute every
    # RAG chunk with implementation detail.
    if "<!-- docparse:page -->" in body:
        bad.append("mốc trang lọt vào body")
    for s in spec.get("must_contain", []):
        if s not in body:
            bad.append(f"output thiếu {s!r}")
    for s, n in (spec.get("min_occurrences") or {}).items():
        got = body.count(s)
        if got < n:
            bad.append(f"{s!r} xuất hiện {got} lần, cần ≥ {n}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="chỉ chạy fixture có tên này")
    ap.add_argument("--keep", action="store_true", help="giữ lại thư mục output")
    a = ap.parse_args()

    specs = sorted((TESTDATA / "expected").glob("*.json"))
    if a.names:
        specs = [s for s in specs if s.stem in a.names]
    if not specs:
        print("không tìm thấy fixture nào", file=sys.stderr)
        return 2

    outdir = pathlib.Path(tempfile.mkdtemp(prefix="doc-parse-regression-"))
    failures = 0
    for spec_path in specs:
        name = spec_path.stem
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        pdf = TESTDATA / "regression" / f"{name}.pdf"
        if not pdf.exists():
            print(f"✗ {name}: thiếu fixture {pdf}")
            failures += 1
            continue

        run = subprocess.run([sys.executable, str(PARSE), str(pdf), "-o", str(outdir),
                              *spec.get("args", [])], capture_output=True, text=True)
        md = outdir / f"{name}.md"
        if run.returncode != 0 or not md.exists():
            print(f"✗ {name}: parse thất bại\n   {run.stderr.strip()[-300:]}")
            failures += 1
            continue

        fm, body = frontmatter(md)
        bad = check(name, spec, fm, body)
        recalls = f"text={fm.get('text_recall')} hv={fm.get('high_value_recall')}"
        if bad:
            failures += 1
            print(f"✗ {name}  [{recalls}]")
            for b in bad:
                print(f"    · {b}")
            print(f"    spec: {spec.get('why', '')}")
        else:
            print(f"✓ {name}  parser={fm.get('parser')}  {recalls}  "
                  f"flags={','.join(fm.get('quality_flags') or []) or '-'}")

    if a.keep:
        print(f"\noutput giữ tại {outdir}")
    print(f"\n{len(specs) - failures}/{len(specs)} đạt")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
