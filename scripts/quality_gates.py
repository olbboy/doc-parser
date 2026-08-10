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
TEXT_RECALL_LOW = 0.95
TEXT_RECALL_WATCH = 0.98

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
        if sum(pw.values()) < 30:          # near-empty page: nothing to lose
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
    pages = page_texts(pdf_path)
    per = gates.get("page_recalls") or []
    # Same definition of "intact" the flags use, rather than a second threshold.
    # The old 0.99 was a leftover from counting occurrences, where near-complete
    # meant "almost every repeat survived"; under presence it made a document that
    # lost 1 token in 80 look like a dropped region and cost a pointless donor run.
    # None does not corroborate: too few tokens to judge is not evidence of loss.
    hv_lost = high_value_intact(gates) is False
    dropped = []
    for i, r in enumerate(per):
        if r is None or r >= min_recall or len(words(pages[i])) < 30:
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
