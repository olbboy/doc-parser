#!/usr/bin/env python3
"""Post-parse gates: did the engine actually keep what the document contained?

Length checks cannot answer that — Docling emits *more* characters than anydoc on
the HV48100 manual (76.8k vs 59.8k, from markdown table padding) while silently
dropping a 14-row nameplate table it classified as a picture. These gates compare
against the PDF's own text layer instead, at three granularities:

  text_layer_recall      whole document, one number for the frontmatter
  page_recalls           per page, to localise which page lost content
  high_value_recall      model codes / units / DIP codes only — the tokens a
                         technical RAG query actually asks for

`compat-list.pdf` is why none of these may be a hard threshold on their own:
Docling scores 0.93 there while being the *best* engine for that file, because it
re-serialises a dense grid rather than dropping anything.
"""
import re, unicodedata
from collections import Counter

PAGE_MARK = "<!-- docparse:page -->"

# Thresholds live here so the three places that ask "are the model codes intact?"
# cannot drift apart, as they did when the region detector kept its own 0.99.
HIGH_VALUE_INTACT = 0.98     # at or above: every model code and unit survived
HIGH_VALUE_MISSING = 0.90    # below: raise the flag
MIN_HV_TYPES = 5             # distinct tokens needed before judging at all
PAGE_RECALL_MIN = 0.90       # below: the page is a region-drop candidate
PAGE_DEAD_RECALL = 0.50      # a page must be this badly hit before it can be "dead"
PAGE_ABSENT_DEAD = 0.10      # ...and this much of its wording must be gone, not folded
MIN_PAGE_TYPES = 12          # distinct words a page needs before its ratio is stable
MIN_PAGE_WORDS = 30          # total occurrences below this: near-empty page, nothing to lose
TEXT_RECALL_LOW = 0.95
TEXT_RECALL_WATCH = 0.98

# A PDF whose ToUnicode CMap is broken emits glyph indices instead of Unicode:
# `(XURSHDQ JHQHUDO` is `European general` shifted by 29. The recall gates above
# cannot see this. They compare the output against the PDF's own text layer, and
# when that layer is itself the corrupt side both halves agree — `PI STATION261 ·
# Hướng dẫn sử dụng` scored text_recall 0.986 over 13,324 tokens of garbage and
# carried no flag. This asks the question recall never asks: is the text a language?
READABLE_RATIO_MIN = 0.02     # below: the words are not function words of any language
MIN_READABLE_TOKENS = 200     # fewer Latin words than this and the ratio is noise

# No gate has ever looked at table shape. `PANDAS_NOISE` only sniffs for NaN and
# Unnamed:, and only for two of the four engines, so an engine that invents tables
# out of bar charts passes clean: `Storytelling with Data - P1` scored text_recall
# 0.996 with no flag while 27 of its 72 "tables" are more than half empty, because
# anydoc shredded chart axes and legends into pipe grids.
#
# Column raggedness is the obvious metric and a dead one: across 186 corpus tables
# the median off-modal ratio is 0.000 and only 2 exceed 0.25, since engines emit
# column-consistent grids even when the content inside is nonsense. What separates a
# real table from a shredded chart is how much of the grid is *empty*. Same sources,
# two engines: anydoc leaves a median 0.15 of cells blank against Docling's 0.00, and
# is the blanker engine on 10 documents out of 10. The emptiness is an artifact of
# the engine, not of the document, which is what makes it a usable signal.
TABLE_EMPTY_CELL_MAX = 0.50   # per table: share of blank cells before it counts as shredded
TABLE_OFF_MODAL_MAX = 0.25    # per table: rows disagreeing on column count — rare but real
TABLE_DEFECT_SHARE = 0.25     # per document: share of defective tables before flagging
MIN_TABLE_BODY_ROWS = 2       # fewer rows and "modal width" is not a majority of anything

# Engines disagree on check-mark glyphs (MinerU normalises √ to ✓); fold them so a
# table full of ticks does not read as a recall failure.
_GLYPH = {"✓": "√", "✔": "√", "☑": "√", "✅": "√", "–": "-", "—": "-", "’": "'"}

HIGH_VALUE = [
    re.compile(r"\b[A-Z][A-Z0-9]{1,}-\d+[A-Z0-9]*\b"),          # BMU-8, AF1-3
    re.compile(r"\b[A-Z]{2,4}\d{3,6}\b"),                        # HV48100, EX2000
    re.compile(r"\b\d+[.,]?\d*\s?(?:kWh|Wh|kW|W|VDC|VAC|V|Ah|A|Hz|mm|kg|inch|°C)\b"),
    re.compile(r"\b[01]{6}\b"),                                  # DIP codes
    # Certification standards: the number may be attached or spaced, and may carry
    # a dotted or hyphenated part ("IEC62477", "IEC 62619", "EN 61000-6", "UN38.3").
    # The model-code pattern above only catches the attached, undotted form.
    # Attached forms like IEC62477 therefore match both patterns and land in the bag
    # twice. Symmetric across reference and output, so recall stays consistent; only
    # the relative weight of those tokens is doubled.
    re.compile(r"\b(?:IEC|EN|UL|ISO|GB|UN|BS|VDE)\s?\d{2,6}(?:[.\-–]\d+)*\b"),
]


def normalize(text):
    text = unicodedata.normalize("NFC", text)
    for a, b in _GLYPH.items():
        text = text.replace(a, b)
    # Engines space units out differently: Docling writes "0 ° C" where the text
    # layer has "0°C". Without this the token pattern below misses the value and the
    # metric reports a loss that never happened — measured on `datasheet.pdf`, where
    # it manufactured four missing temperature limits. Newlines are left alone
    # because callers split this output into lines.
    # The space is removed rather than collapsed, so "0°C" and "0 ° C" become the
    # same token on both sides of the comparison; collapsing to one space would
    # still leave "0°C" and "0 °C" as two different strings.
    #
    # Only spacing is normalised here. Across all 510 text-layer PDFs in the Pytes
    # corpus there is no "kW h" or "A h" spelling at all; the 14 apparent "m m" hits
    # are diff-export artifacts that put one character per line, which is precisely
    # the over-match such a rule would institutionalise. The decimal comma the
    # Vietnamese documents use ("2,14kWh") is real but needs no rule either, because
    # every engine writes it identically — text layer, Docling and anydoc all report
    # 32 comma forms on `baogia-v16.pdf`. Re-measure with scripts/scan_unit_variants.py
    # before adding a rule; existence in the corpus is not the bar, engine
    # disagreement is.
    text = re.sub(r"°[ \t]*C", "°C", text)
    text = re.sub(r"(\d)[ \t]+(?=°C|kWh|Wh|kW|VDC|VAC|Ah|Hz|mm|kg|inch|[VAW]\b)", r"\1", text)
    return text


def words(text, minlen=2):
    return Counter(w for w in re.findall(r"\w+", normalize(text), re.UNICODE) if len(w) >= minlen)


# Latin letters only. Deliberately excludes Greek and Cyrillic, which a wider
# `À-ỹ` range would swallow: a Russian document would then score near zero and be
# mistaken for mojibake. × (U+00D7) and ÷ (U+00F7) are cut out of the range because
# they sit among the letters and would glue "a×b" into one token.
_LATIN_WORD = re.compile(r"[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F\u1E00-\u1EFF]{2,}")
_STOPWORDS_EN = frozenset("the and of to in for is are with this be on or as by from at "
                          "that it can not will has have shall must if when each".split())
_STOPWORDS_VI = frozenset("và của các là trong cho với này được không khi một những để "
                          "có thể theo từ đến hoặc phải nếu sau trước".split())


def readable_ratio(text):
    """Share of Latin words that are common function words. None when unjudgeable.

    Measured over 35 T0 documents of the Pytes corpus: the one file with a broken
    ToUnicode CMap scores 0.001, the lowest *legitimate* document 0.078, ordinary
    documents 0.17 – 0.25 — a 78x gap, so the threshold sits far from both sides.

    Bilingual CJK documents were the worry and are not a problem: the three
    CJK-heavy files score 0.20 – 0.23, because they carry English alongside the
    Chinese and the Chinese characters are not counted as words at all.

    `max` of the two hit-rates rather than their sum, so a purely Vietnamese
    document is not punished for lacking English function words.

    None when there are too few Latin words to judge — a pure CJK or Arabic
    document lands there, and callers must not read None as "readable".
    """
    toks = [t.lower() for t in _LATIN_WORD.findall(text)]
    if len(toks) < MIN_READABLE_TOKENS:
        return None
    c = Counter(toks)
    return round(max(sum(c[w] for w in _STOPWORDS_EN),
                     sum(c[w] for w in _STOPWORDS_VI)) / len(toks), 3)


_FENCE = re.compile(r"^\s*(```|~~~)")
_TABLE_SEP = re.compile(r"^[\s|:\-]+$")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")          # a cell may contain an escaped pipe


def parse_md_tables(md):
    """Body rows of every markdown table in `md`, each row as a list of cells.

    Separator rows are dropped — they carry no content, and their width is not
    independent evidence of anything. Fenced code is skipped whole: a shell session
    that prints a pipe-delimited line is not a table.

    Exactly one leading and one trailing pipe is removed, not every one of them.
    `||Survey Results||||100%|` opens with an empty cell, and stripping greedily
    would hide the very raggedness this is here to count.
    """
    tables, cur, fenced = [], [], False

    def flush():
        # A fence line ends the table above it exactly as a line of prose does.
        # Leaving it out merged two unrelated tables across a code block and read
        # the width change between them as raggedness — a false positive.
        if len(cur) >= MIN_TABLE_BODY_ROWS:
            tables.append(list(cur))
        cur.clear()

    for line in md.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            flush()
            continue
        if fenced:
            continue
        s = line.strip()
        if len(s) > 1 and s.startswith("|") and s.endswith("|"):
            if not _TABLE_SEP.match(s):
                cur.append([c.strip() for c in _CELL_SPLIT.split(s[1:-1])])
            continue
        flush()
    flush()
    return tables


def table_defect_share(md):
    """Share of the document's tables that are structurally defective. None if no tables.

    A table is defective when it is mostly blank (`TABLE_EMPTY_CELL_MAX`) or when its
    rows disagree on how many columns they have (`TABLE_OFF_MODAL_MAX`). The first
    catches an engine shredding a chart, a bulleted list or an address block into a
    grid; the second catches a genuinely malformed table, which is rare — 2 of 186.

    Calibrated on 10 documents parsed twice, once per engine. The share itself is a
    blunt instrument: it never exceeds 0.143 for anydoc or 0.053 for Docling on real
    technical documents, so on this corpus the flag fires on exactly one file — a book
    of bar charts anydoc shredded into 72 fake tables, at 0.389. Narrow coverage is the
    intended trade: zero false positives across 20 parses.

    The underlying blankness separates far more sharply than the flag does — median
    blank cells per table run 0.15 for anydoc against 0.00 for Docling, and anydoc is
    the blanker engine on 10 of 10 documents. That gap answers "was a better engine
    available", which is a routing question, not "is this output broken". Keeping the
    two apart is deliberate; a flag on the first would fire on most T0 output.

    Table counts do not settle it either way: Docling finds more tables on the two
    manuals (19 vs 16, 15 vs 11) but fewer on several certificates (1 vs 11, 4 vs 7).
    """
    tables = parse_md_tables(md)
    if not tables:
        return None
    defective = 0
    for rows in tables:
        widths = [len(r) for r in rows]
        modal = max(set(widths), key=widths.count)
        off_modal = sum(1 for w in widths if w != modal) / len(widths)
        cells = [c for r in rows for c in r]
        blank = sum(1 for c in cells if not c) / len(cells) if cells else 0
        if blank > TABLE_EMPTY_CELL_MAX or off_modal > TABLE_OFF_MODAL_MAX:
            defective += 1
    return round(defective / len(tables), 3)


def recall(ref, hyp):
    total = sum(ref.values())
    if not total:
        return None
    return round(sum(min(c, hyp.get(w, 0)) for w, c in ref.items()) / total, 3)


def page_texts(pdf_path):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf_path)
    return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]


def high_value_tokens(text):
    """Every model code, unit value, DIP code and standard number in `text`."""
    text = normalize(text)
    c = Counter()
    for rx in HIGH_VALUE:
        c.update(m.group(0) for m in rx.finditer(text))
    return c


def high_value_recall(ref_text, hyp_text):
    """Share of distinct high-value tokens that survived at least once.

    Presence, not multiplicity. Counting occurrences punishes an engine for
    deduplicating a repeated page header: `V5 UL9540A.pdf` carries "9540A" in the
    header of all 47 pages, Docling folds it to 13, and the multiplicity form
    scored that 0.843 — a loss flag on a document that lost nothing. Measured over
    12 documents, every one of the three flags multiplicity raised was false, while
    presence kept both known real losses far below the threshold (datasheet 0.842,
    hv48100 0.032).

    The question this metric answers is the one a technical query asks — "is
    IEC62619 in here at all?" — not "does the header repeat the right number of
    times". None when there are too few distinct tokens to judge.
    """
    ref = high_value_tokens(ref_text)
    if len(ref) < MIN_HV_TYPES:
        return None
    got = high_value_tokens(hyp_text)
    return round(sum(1 for tok in ref if got.get(tok, 0)) / len(ref), 3)


def evaluate(pdf_path, md, md_pages=None):
    """Return the gate readings for one parsed PDF.

    md_pages, when the engine could emit page breaks, enables per-page recall;
    otherwise every page is scored against the whole output, which still localises
    a dropped page (its words are absent everywhere) without false-flagging
    reflowed ones.
    """
    pages = page_texts(pdf_path)
    # Docling only emits a page break between pages that produced items, so a
    # blank or fully-filtered page shifts every later segment onto the wrong
    # page. When the marker count disagrees with the PDF, per-page scoring would
    # compare page i against page i+1's output — fall back to whole-document.
    if md_pages is not None and len(md_pages) != len(pages):
        md_pages = None
    ref_all = "\n".join(pages)
    ref_w = words(ref_all)
    if sum(ref_w.values()) < 200:
        return {}
    hyp_all = words(md)
    out = {"text_recall": recall(ref_w, hyp_all)}

    hv = high_value_recall(ref_all, md)
    if hv is not None:
        out["high_value_recall"] = hv

    per, absent = [], []
    for i, ptext in enumerate(pages):
        pw = words(ptext)
        if sum(pw.values()) < MIN_PAGE_WORDS:   # near-empty page: nothing to lose
            per.append(None)
        else:
            target = words(md_pages[i]) if md_pages and i < len(md_pages) else hyp_all
            per.append(recall(pw, target))
        absent.append(page_absent(pw, hyp_all))
    out["page_recalls"] = per
    out["page_absent"] = absent
    return out


def page_absent(page_words, output_words):
    """Share of a page's vocabulary that appears nowhere in the whole output.

    Deliberately compared against the entire document, not the matching page: a
    repeated header is "present" because it also sits on other pages, so a page that
    is nothing but header scores ~0 and stops looking like a loss.

    This replaces an earlier idea of judging pages by how many distinct words they
    hold. Measurement killed it — the two are anti-correlated here. The TÜV report
    header on `04-iec-60731` is vocabulary-rich (74 distinct words: address, phone,
    fax, project number) and loses nothing (3% absent), while a one-line header page
    on `V5 UL9540A` is poor (27 words) and really does lose 15%. Richness measures
    how wordy a page is, not whether the engine kept it.
    """
    if len(page_words) < MIN_PAGE_TYPES:
        return None                        # too few words for a ratio to mean anything
    kept = sum(1 for t in page_words if output_words.get(t, 0))
    return round(1 - kept / len(page_words), 3)


def content_dead_pages(gates):
    """Pages whose wording left the document — 0-based, in page order.

    Both signals are required, and neither works alone. Poor page recall alone fires
    on any page the engine reflowed. High absence alone fires on ordinary
    serialisation noise: `compat-list.pdf` reaches 14% absent on a page while losing
    nothing an operator would care about, because hyphenation and glyph handling
    always shed a few words.

    Together they mean something narrow and correct: the page barely made it into
    the output *and* the reason is that its wording is gone rather than merely
    deduplicated. That is what separates `V5 UL9540A.pdf` page 3 (recall 0.059,
    34% absent) from the TÜV header block on `04-iec-60731` (recall 0.30, 3% absent).
    """
    per = gates.get("page_recalls") or []
    absent = gates.get("page_absent") or []
    dead = []
    for i, r in enumerate(per):
        if r is None or r >= PAGE_DEAD_RECALL:
            continue
        a = absent[i] if i < len(absent) else None
        if a is not None and a >= PAGE_ABSENT_DEAD:
            dead.append(i)
    return dead


def high_value_intact(gates):
    """True when every model code and unit survived, None when it cannot be judged.

    A document with too few distinct such tokens yields None, which callers must
    not read as "intact" — absence of evidence is not evidence the content is whole.
    """
    hv = gates.get("high_value_recall")
    return None if hv is None else hv >= HIGH_VALUE_INTACT


def region_dropped_pages(pdf_path, md, gates, md_pages=None, min_recall=PAGE_RECALL_MIN):
    """Pages whose text the engine threw away.

    A page qualifies when its recall is poor *and* one corroborating signal agrees:
    either the engine left a picture placeholder where the text layer still holds
    real words, or the document as a whole lost model codes and units. Poor page
    recall alone is not enough — it also fires on any page the engine merely
    reflowed, which is what `compat-list.pdf` does at 0.93 while losing nothing.
    """
    per = gates.get("page_recalls") or []
    if not per:
        return []
    pages = page_texts(pdf_path)
    # Same definition of "intact" the flags use, rather than a second threshold.
    # The old 0.99 was a leftover from counting occurrences, where near-complete
    # meant "almost every repeat survived"; under presence it made a document that
    # lost 1 token in 80 look like a dropped region and cost a pointless donor run.
    # None does not corroborate: too few tokens to judge is not evidence of loss.
    hv_lost = high_value_intact(gates) is False
    dropped = []
    for i, r in enumerate(per):
        # Same near-empty definition evaluate() uses — total occurrences, not
        # distinct types. Counting types here silently excluded exactly the pages
        # a region drop hits hardest: a nameplate of repeated units and model
        # fields has many occurrences of few types, so its sub-threshold recall
        # never reached the corroboration checks below.
        if r is None or r >= min_recall or sum(words(pages[i]).values()) < MIN_PAGE_WORDS:
            continue
        placeholder = ("<!-- image -->" in (md_pages[i] if md_pages and i < len(md_pages) else md))
        if placeholder or hv_lost:
            dropped.append(i)
    return dropped


def split_pages(md):
    """Split engine output on the page marker, or return None if it has none."""
    if PAGE_MARK not in md:
        return None
    return [p.strip() for p in md.split(PAGE_MARK)]


def aligned_pages(pdf_path, md):
    """split_pages(md), but None unless the segments match the PDF's page count.

    Docling only emits a page break between pages that produced items, so a
    blank or fully-filtered page silently shifts every later segment onto the
    wrong physical page. Page-indexed consumers — per-page recall, page-fill
    repair — must fall back to their whole-document path rather than score or
    inject against a neighbouring page.
    """
    pages = split_pages(md)
    if pages is not None and len(pages) != len(page_texts(pdf_path)):
        return None
    return pages
