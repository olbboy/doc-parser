#!/usr/bin/env python3
"""Parse a document to Markdown using the cheapest engine that can handle it.

Probes the file, picks a tier, runs that engine, and falls back down a chain
that is rebuilt after every failure — so a "needs OCR" error from a cheap engine
removes every engine without OCR from the remaining attempts.

Output is Markdown with YAML frontmatter recording which engine ran, why, and
which quality flags fired.

Usage:
  parse_document.py <file> [file...] -o outdir [--tier auto|T0|T1|T2|T3]
                    [--engine anydoc|markitdown|docling|mineru] [--dry-run]
"""
import argparse, json, os, pathlib, platform, subprocess, sys, tempfile, time, urllib.request

HOME = pathlib.Path(os.environ.get("DOCPARSE_HOME", pathlib.Path.home() / ".local/share/doc-parse"))
VENV = {"lite": HOME / "lite", "docling": HOME / "docling", "mineru": HOME / "mineru"}
MINERU_URL = os.environ.get("DOCPARSE_MINERU_URL", "http://127.0.0.1:8123")
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from probe_document import probe  # noqa: E402
import quality_gates  # noqa: E402
from quality_gates import high_value_intact, HIGH_VALUE_INTACT  # noqa: E402
import repair_dropped_regions  # noqa: E402

RUNNERS = HERE / "engine_runners"


def _py(venv):
    p = VENV[venv] / "bin" / "python"
    if not p.exists():
        raise RuntimeError(f"thiếu venv {venv} tại {p} — chạy scripts/setup-engines.sh")
    return str(p)


def _run(venv, script, *args, timeout=3600):
    r = subprocess.run([_py(venv), str(RUNNERS / script), *map(str, args)],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1][:300] if (r.stderr or r.stdout) else "exit != 0")
    return r.stdout


def mineru_alive(url=MINERU_URL):
    try:
        urllib.request.urlopen(url + "/docs", timeout=2)
        return True
    except Exception:
        return False


def start_mineru(url=MINERU_URL, wait=600):
    """MinerU's CLI pays ~4-6 s of interpreter+torch import per file; the HTTP
    service pays it once. Never shell out to `mineru` in a loop."""
    if mineru_alive(url):
        return True
    port = url.rsplit(":", 1)[-1]
    log = open(tempfile.gettempdir() + "/doc-parse-mineru-api.log", "ab")
    # mineru-api writes per-task scratch dirs under its CWD; keep that out of the repo.
    workdir = pathlib.Path(tempfile.gettempdir()) / "doc-parse-mineru-work"
    workdir.mkdir(exist_ok=True)
    subprocess.Popen([str(VENV["mineru"] / "bin" / "mineru-api"),
                      "--host", "127.0.0.1", "--port", port],
                     stdout=log, stderr=log, cwd=str(workdir), start_new_session=True)
    for _ in range(wait // 3):
        time.sleep(3)
        if mineru_alive(url):
            return True
    return False


# --- engine adapters: each returns markdown text ----------------------------
def run_anydoc(path, **_):
    return _run("lite", "run_anydoc.py", path)


def run_markitdown(path, **_):
    return _run("lite", "run_markitdown.py", path)


DOCLING_SPLIT = "<<<DOCPARSE-SPLIT>>>"


def run_docling_batch(paths, ocr=None):
    """One Docling process for many files — the warm-up is paid once, not per file."""
    args = list(paths) + (["--ocr", ocr[0], "--lang", ocr[1]] if ocr else [])
    return _run("docling", "run_docling.py", *args).split("\n" + DOCLING_SPLIT + "\n")


def run_docling(path, ocr=None, **_):
    return run_docling_batch([path], ocr)[0]


def run_mineru(path, backend="pipeline", **_):
    if not start_mineru():
        raise RuntimeError("không khởi động được mineru-api")
    return _run("mineru", "run_mineru.py", path, backend, MINERU_URL)


ENGINES = {"anydoc": run_anydoc, "markitdown": run_markitdown,
           "docling": run_docling, "mineru": run_mineru}


def fallback_chain(engine_spec, needs_ocr):
    """Order engines to try. Rebuilt after each failure by the caller, so that a
    late 'OCR is required' verdict drops every OCR-less engine from what's left."""
    ocr = None
    name = engine_spec
    if engine_spec.startswith("docling:ocr:"):
        _, _, eng, lang = engine_spec.split(":")
        name, ocr = "docling", (eng, lang)
    if needs_ocr:
        # Only engines that can read pixels — and for the MinerU step specifically
        # the VLM backend, never `pipeline`: its OCR models carry no Vietnamese and
        # measured 50% diacritic retention on scanned Vietnamese pages.
        return [("docling", ocr or default_ocr()), ("mineru:vlm-engine", None)]
    order = [(name, ocr)]
    for e in ("mineru", "docling", "anydoc", "markitdown"):
        if e != name:
            order.append((e, None))
    return order


def default_ocr():
    return ("ocrmac", "vi-VT") if platform.system() == "Darwin" else ("tesseract", "vie")


def run_gates(info, md):
    """Recall readings for a PDF that carries a text layer; {} for anything else."""
    if info["kind"] != "pdf" or not md:
        return {}
    try:
        return quality_gates.evaluate(info["file"], md, quality_gates.split_pages(md))
    except Exception:
        return {}


def repair_if_dropped(info, md, used, gates):
    """Refill pages the primary engine threw away, using a text-layer engine.

    Fires only when poor page recall is corroborated — a picture placeholder on a
    page whose text layer still holds real words, or model codes and units missing
    from the document — so a page that is genuinely a diagram, or one the engine
    merely reflowed, is left alone.

    Returns (markdown, repaired_pages, detected_pages). Detection and repair are
    reported separately because a page can be correctly detected as dropped and
    still not be repairable — the donor may fail, or hold nothing the primary lacks
    — and that case has to surface rather than pass as clean.
    """
    if info["kind"] != "pdf" or not md or used not in ("docling", "mineru"):
        return md, [], []
    pages = quality_gates.split_pages(md)
    dropped = quality_gates.region_dropped_pages(info["file"], md, gates, pages)
    if not dropped:
        return md, [], []
    try:
        donor = run_anydoc(info["file"])
    except Exception:
        return md, [], dropped
    md, repaired = repair_dropped_regions.recover(info["file"], dropped, donor, md, pages)
    return md, repaired, dropped


def decide_recall_flags(gates):
    """Recall flags for one finished document, judged on the final reading.

    `HIGH_VALUE_MISSING` is a *residual*: it fires on what is still missing after
    every repair, so on a document the token inject fully recovered it stays quiet
    and only `HIGH_VALUE_RECOVERED` remains. It earns its place on the case where
    the inject recovers nothing — the donor line was already present in a different
    wording, or the file has no text layer to draw from.
    """
    flags = []
    recall = gates.get("text_recall")
    if recall is None:
        return flags
    # A single global threshold cannot separate "dropped a block" from
    # "re-serialised a dense grid", so only gross loss is a hard flag, and even that
    # is downgraded when every model code and unit survived — which is what separates
    # compat-list (0.93 recall, all ticks and DIP codes intact, Docling is the right
    # engine) from a page that genuinely went missing.
    # The downgrade is withdrawn as soon as a page's wording has left the document.
    # Intact model codes say the technical values survived; they say nothing about
    # whether a page of prose did. `V5 UL9540A.pdf` keeps 0.988 of its codes while
    # five pages — including one with 322 words — are effectively gone, and used to
    # pass as WATCH on that strength alone.
    hv = gates.get("high_value_recall")
    intact = hv is not None and hv >= HIGH_VALUE_INTACT
    if recall < quality_gates.TEXT_RECALL_LOW and not (
            intact and not quality_gates.content_dead_pages(gates)):
        flags.append("TEXT_RECALL_LOW")
    elif recall < quality_gates.TEXT_RECALL_WATCH:
        flags.append("TEXT_RECALL_WATCH")
    if hv is not None and hv < quality_gates.HIGH_VALUE_MISSING:
        flags.append("HIGH_VALUE_MISSING")
    return flags


def output_path(src, outdir):
    """Where one source file's Markdown goes, without silently eating a sibling.

    A folder holding both `report.pdf` and `report.docx` maps them to the same
    `report.md`; whichever ran last used to overwrite the other with no warning.
    On a collision the extension is folded into the name instead.
    """
    src = pathlib.Path(src)
    out = pathlib.Path(outdir) / f"{src.stem}.md"
    if out.exists():
        head = out.read_text(encoding="utf-8", errors="ignore")[:400]
        if f'source_file: "{src.name}"' not in head:
            return out.with_name(f"{src.stem}{src.suffix.replace('.', '-')}.md")
    return out


def parse_one(path, outdir, forced_tier="auto", forced_engine=None, dry_run=False,
              pre=None):
    info = probe(path)
    if forced_engine:
        info["engine"], info["reason"] = forced_engine, "engine do người dùng chỉ định"
    if dry_run:
        return info, None

    needs_ocr = "NEEDS_OCR" in info["flags"]
    attempts, md, used = [], None, None
    tried = set()
    if pre is not None:                      # already produced by a batch run
        md, used = pre["md"], pre["engine"]
        attempts.append({"engine": used, "ok": True, "seconds": pre["seconds"], "batched": True})
    while md is None:
        chain = [c for c in fallback_chain(info["engine"], needs_ocr) if c[0] not in tried]
        if not chain:
            break
        name, ocr = chain[0]
        tried.add(name)
        t0 = time.perf_counter()
        try:
            engine, _, forced_backend = name.partition(":")
            kwargs = {"ocr": ocr}
            if engine == "mineru":
                kwargs = {"backend": forced_backend or
                          ("hybrid-engine" if info["tier"] == "T3" else "pipeline")}
            md = ENGINES[engine](info["file"], **kwargs)
            attempts.append({"engine": name, "ok": True, "seconds": round(time.perf_counter() - t0, 3)})
            used = engine
            break
        except Exception as e:
            err = str(e)
            attempts.append({"engine": name, "ok": False, "error": err[:200]})
            if "OCR is required" in err or "no extractable text" in err:
                needs_ocr = True
                info["flags"].append("NEEDS_OCR")

    flags = list(dict.fromkeys(info["flags"]))
    gates = run_gates(info, md)
    md, repaired, detected = repair_if_dropped(info, md, used, gates)
    if repaired:
        info["repaired_pages"] = repaired
        used = f"{used}+anydoc-fill"
        gates = run_gates(info, md)               # re-score the repaired output

    # Sparse token loss survives page-level repair: the page is present, only the
    # certification standards and unit values inside it are gone. Pull those lines
    # straight from the text layer instead of re-running an engine.
    tokens = []
    if md and info["kind"] == "pdf" and (gates.get("high_value_recall") or 1) < quality_gates.HIGH_VALUE_MISSING:
        try:
            md, tokens = repair_dropped_regions.recover_high_value(info["file"], md)
        except Exception:
            tokens = []
        if tokens:
            info["high_value_recovered"] = tokens
            used = f"{used}+hv-inject"
            gates = run_gates(info, md)

    # Flags are decided only once every repair has run, against the final reading.
    # Raising them earlier leaves stale alarms on output that a later step fixed.
    if repaired:
        flags.append("REGION_DROPPED")
    elif detected and high_value_intact(gates) is not True:
        # Detected but not repaired. Only worth raising when something independent
        # says content really went missing: when the donor found nothing absent and
        # every model code and unit survived, the detection was the false alarm —
        # which is exactly `compat-list.pdf`, where Docling reflows a dense grid
        # across pages without losing a single tick.
        #
        # `is not True`, deliberately opposite to the `is False` the detector uses.
        # Raising a detection needs positive evidence of loss, so an unmeasurable
        # document must not corroborate one; silencing an alarm needs positive
        # evidence of wholeness, so an unmeasurable document must not silence it.
        flags.append("REGION_DROPPED_UNREPAIRED")
        info["dropped_pages"] = [p + 1 for p in detected]
    if tokens:
        flags.append("HIGH_VALUE_RECOVERED")

    if md:
        md = md.replace(quality_gates.PAGE_MARK + "\n", "").replace(quality_gates.PAGE_MARK, "")

    recall = gates.get("text_recall")
    if recall is not None:
        info["text_recall"] = recall
        info["high_value_recall"] = gates.get("high_value_recall")
        # Persist the pages the region detector could have acted on. The body has its
        # page markers stripped by the time it is written, so re-running the gate on
        # the artifact silently takes a different branch and answers a different
        # question — a trap that produced one wrong diagnosis already. Only the pages
        # below the threshold are kept: the rest are 1.0 and would bury the frontmatter
        # of a 118-page manual.
        low = {str(i + 1): r for i, r in enumerate(gates.get("page_recalls") or [])
               if r is not None and r < quality_gates.PAGE_RECALL_MIN}
        if low:
            info["low_recall_pages"] = low
        dead = quality_gates.content_dead_pages(gates)
        if dead:
            info["content_dead_pages"] = {str(i + 1): gates["page_absent"][i] for i in dead}
        flags.extend(decide_recall_flags(gates))
    if md is None:
        flags.append("PARSE_FAILED")
    elif not md.strip():
        flags.append("EMPTY_SUCCESS")
        md = ""
    if md and used in ("anydoc", "markitdown"):
        if "NaN" in md or "Unnamed:" in md:
            flags.append("PANDAS_NOISE")
        if info["tier"] in ("T2", "T3"):
            flags.append("LAYOUT_RISK_UNADDRESSED")

    out = output_path(path, outdir)
    out.parent.mkdir(parents=True, exist_ok=True)
    fm = {"source_file": pathlib.Path(path).name, "doc_kind": info["kind"],
          "pages": info.get("pages") or info.get("sheets") or info.get("slides"),
          "parser": used, "parser_tier": info["tier"], "parser_reason": info["reason"],
          "text_recall": info.get("text_recall"),
          "high_value_recall": info.get("high_value_recall"),
          "repaired_pages": info.get("repaired_pages"),
          "dropped_pages": info.get("dropped_pages"),
          "high_value_recovered": info.get("high_value_recovered"),
          "low_recall_pages": info.get("low_recall_pages"),
          "content_dead_pages": info.get("content_dead_pages"),
          "attempts": attempts, "quality_flags": flags}
    fm = {k: v for k, v in fm.items() if v is not None}
    body = "---\n" + "\n".join(
        f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fm.items()) + "\n---\n\n" + (md or "")
    out.write_text(body, encoding="utf-8")
    info.update(parser=used, quality_flags=flags, output=str(out), attempts=attempts)
    return info, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--outdir", default="parsed")
    ap.add_argument("--tier", default="auto")
    ap.add_argument("--engine", choices=list(ENGINES))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    # Group the Docling-bound files (same OCR settings) into one process.
    batched = {}
    if not a.dry_run and not a.engine and len(a.files) > 1:
        groups = {}
        for f in a.files:
            spec = probe(f)["engine"]
            if spec == "docling":
                groups.setdefault(None, []).append(f)
            elif spec.startswith("docling:ocr:"):
                _, _, eng, lang = spec.split(":")
                groups.setdefault((eng, lang), []).append(f)
        for ocr, files in groups.items():
            if len(files) < 2:
                continue
            t0 = time.perf_counter()
            try:
                outs = run_docling_batch(files, ocr)
                per = round((time.perf_counter() - t0) / len(files), 3)
                for f, md in zip(files, outs):
                    batched[f] = {"md": md, "engine": "docling", "seconds": per}
            except Exception:
                pass                          # fall through to per-file attempts

    for f in a.files:
        info, out = parse_one(f, a.outdir, a.tier, a.engine, a.dry_run, batched.get(f))
        name = pathlib.Path(f).name
        if a.dry_run:
            print(f"{name:34s} → {info['tier']:3s} {info['engine']:28s} {info['reason']}")
        else:
            secs = next((x["seconds"] for x in info["attempts"] if x.get("ok")), None)
            flags = ",".join(info["quality_flags"]) or "-"
            print(f"{name:34s} → {info['tier']:3s} {str(info['parser']):11s} {secs}s  [{flags}]")


if __name__ == "__main__":
    main()
