#!/usr/bin/env python3
"""Count how a PDF corpus actually spells its units and standards.

Tooling, not a gate: nothing in `run_regression.py` or `setup-engines.sh` calls it.
Run it by hand before touching `quality_gates.normalize`, so a rule is added only
for a spelling the corpus really uses.

Existence is not the bar, though — a variant only needs normalising when *engines
disagree* about it. The Vietnamese decimal comma ("2,14 kWh") is common here and
still needs no rule, because text layer, Docling and anydoc all write it the same
way; the degree sign did need one, because Docling writes "0 ° C" where the text
layer writes "0°C".

Last run: 11/08/2026 — 530 PDFs from `knowledge/business` and `~/Downloads/Pytes
Product`. Sampling is seeded so a repeat run picks the same files.

Usage: scan_unit_variants.py <dir> [dir...] [--all] [--json out.json]
"""
import argparse, collections, json, pathlib, random, re, sys

import pypdfium2 as pdfium

SEED = 7
SAMPLE = 120                 # files to scan unless --all
PAGES_PER_FILE = 12
MIN_FILES = 2                # a variant earns a look at this many files...
MIN_HITS = 5                 # ...or this many occurrences

PATTERNS = {
    "deg_spaced":     r"\d\s+°\s*C",
    "deg_sign_space": r"°\s+C",
    "deg_tight":      r"\d°C",
    "num_space_unit": r"\d\s+(?:kWh|kW|Wh|Ah|Hz|mm|kg|inch)\b",
    "num_space_VAW":  r"\d\s+[VAW]\b",
    "kW_h":           r"kW\s+h\b",
    "A_h":            r"\bA\s+h\b",
    "m_m":            r"\bm\s+m\b",
    "decimal_comma":  r"\d,\d+\s*(?:kWh|kW|Wh|Ah|Hz|mm|kg|V|A|W|°C)\b",
    "decimal_dot":    r"\d\.\d+\s*(?:kWh|kW|Wh|Ah|Hz|mm|kg|V|A|W|°C)\b",
    "std_spaced":     r"\b(?:IEC|EN|UL|ISO|GB|UN|BS|VDE)\s\d{2,6}",
    "std_tight":      r"\b(?:IEC|EN|UL|ISO|GB|UN|BS|VDE)\d{2,6}",
}


def scan(roots, take_all=False):
    files = sorted({f for r in roots for f in r.rglob("*.pdf")})
    total = len(files)
    if not take_all and total > SAMPLE:
        random.seed(SEED)
        files = random.sample(files, SAMPLE)

    rx = {k: re.compile(v, re.I if k == "kW_h" else 0) for k, v in PATTERNS.items()}
    hits = collections.Counter()
    seen_in = collections.defaultdict(set)
    samples = collections.defaultdict(list)
    scanned = 0

    for f in files:
        try:
            doc = pdfium.PdfDocument(f)
            text = "\n".join(doc[i].get_textpage().get_text_range()
                             for i in range(min(len(doc), PAGES_PER_FILE)))
        except Exception:
            continue
        if len(text) < 200:                    # scanned page, nothing to count
            continue
        scanned += 1
        for name, r in rx.items():
            found = r.findall(text)
            if not found:
                continue
            hits[name] += len(found)
            seen_in[name].add(f.name)
            if len(samples[name]) < 2:
                m = r.search(text)
                samples[name].append(text[max(0, m.start() - 25):m.end() + 15].replace("\n", "⏎"))
    return dict(total_files=total, scanned=scanned, hits=dict(hits),
                files={k: sorted(v) for k, v in seen_in.items()},
                samples=dict(samples))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--all", action="store_true", help="quét mọi file, bỏ lấy mẫu")
    ap.add_argument("--json", help="ghi kết quả đầy đủ ra file")
    a = ap.parse_args()

    res = scan([pathlib.Path(r) for r in a.roots], a.all)
    print(f"quét {res['scanned']} PDF có text layer "
          f"(trong {res['total_files']} file, {'toàn bộ' if a.all else f'mẫu {SAMPLE}, seed {SEED}'})\n")
    print(f"{'biến thể':18s} {'lần':>6s} {'file':>5s}  ví dụ")
    for name in PATTERNS:
        n = res["hits"].get(name, 0)
        nf = len(res["files"].get(name, []))
        mark = "◀ đủ ngưỡng" if (nf >= MIN_FILES or n >= MIN_HITS) else ""
        ex = (res["samples"].get(name) or [""])[0][:58]
        print(f"{name:18s} {n:6d} {nf:5d}  {ex} {mark}")
    print("\nĐủ ngưỡng ≠ cần rule. Trước khi sửa normalize(), so cùng một file qua "
          "text layer / Docling / anydoc: chỉ sửa khi chúng ghi khác nhau.")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nJSON: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
