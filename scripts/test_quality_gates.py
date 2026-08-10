#!/usr/bin/env python3
"""Unit tests for the gate maths and the token inject. No PDFs, no engines.

The regression fixtures prove the pipeline end to end; these cover the pieces that
are cheap to get subtly wrong and expensive to notice — unit spacing, and the flag
that only fires on a case the corpus does not yet contain.

Run: <lite-venv>/bin/python test_quality_gates.py
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from collections import Counter
import quality_gates as qg
import repair_dropped_regions as rr
from parse_document import decide_recall_flags

FAILS = []


def check(name, got, want):
    if got != want:
        FAILS.append(f"{name}: got {got!r}, want {want!r}")


def tokens(text):
    from collections import Counter
    c = Counter()
    t = qg.normalize(text)
    for rx in qg.HIGH_VALUE:
        c.update(m.group(0) for m in rx.finditer(t))
    return set(c)


# --- unit spacing -----------------------------------------------------------
# Docling writes "0 ° C" where the text layer has "0°C". Before this was
# normalised the metric reported four missing temperature limits on datasheet.pdf
# that were never missing, which would have biased any later threshold calibration.
check("degree sign spaced out", tokens("outside 0 ° C and 45 ° C"), {"0°C", "45°C"})
check("degree sign tight", tokens("outside 0°C and 45°C"), {"0°C", "45°C"})
check("same tokens either way",
      tokens("range -20~55 ° C") == tokens("range -20~55°C"), True)
check("unit space collapses", tokens("51.2  V and 5.12 kWh"), {"51.2V", "5.12kWh"})
check("newlines survive normalise", qg.normalize("a\nb").count("\n"), 1)

# --- high-value token classes ----------------------------------------------
check("standards spaced and tight",
      tokens("IEC 62619, IEC62477, UN38.3") >= {"IEC 62619", "IEC62477", "UN38.3"}, True)
check("model code", "BMU-8" in tokens("HV48100 BMU-8"), True)
check("dip code", "000100" in tokens("DIP 000100"), True)

# --- high-value recall is presence, not multiplicity ------------------------
# A page header repeated 50 times that the engine folds to 13 loses nothing; the
# multiplicity form scored that 0.843 and raised a loss flag on `V5 UL9540A.pdf`,
# which had lost one token out of 249.
HEADER = "IEC62619 " * 50 + " 51.2V 100Ah BMU-8 000100"
FOLDED = "IEC62619 " * 13 + " 51.2V 100Ah BMU-8 000100"
check("repeated header folded is not a loss", qg.high_value_recall(HEADER, FOLDED), 1.0)
check("token gone entirely is a loss",
      qg.high_value_recall(HEADER, "51.2V 100Ah BMU-8 000100"), 0.8)
check("too few distinct tokens to judge", qg.high_value_recall("51.2V 100Ah", "51.2V"), None)
check("distinct types, not occurrences, meet the minimum",
      qg.high_value_recall("IEC62619 " * 20, "IEC62619"), None)

# --- recall -----------------------------------------------------------------
check("recall counts multiplicity",
      qg.recall(qg.words("alpha alpha beta"), qg.words("alpha beta")), 0.667)
check("recall of empty reference", qg.recall(qg.words(""), qg.words("x")), None)

# --- flag bands -------------------------------------------------------------
check("clean document", decide_recall_flags({"text_recall": 0.99, "high_value_recall": 1.0}), [])
check("watch band", decide_recall_flags({"text_recall": 0.96, "high_value_recall": 1.0}),
      ["TEXT_RECALL_WATCH"])
check("low recall downgraded when tokens intact",
      decide_recall_flags({"text_recall": 0.929, "high_value_recall": 1.0}),
      ["TEXT_RECALL_WATCH"])
check("low recall stays hard when tokens lost",
      decide_recall_flags({"text_recall": 0.93, "high_value_recall": 0.75}),
      ["TEXT_RECALL_LOW", "HIGH_VALUE_MISSING"])
# The live path for HIGH_VALUE_MISSING after Phase B: prose is fine, the inject
# recovered nothing, and the standards are still gone. No corpus file does this yet.
check("high-value missing with healthy prose",
      decide_recall_flags({"text_recall": 0.99, "high_value_recall": 0.60}),
      ["HIGH_VALUE_MISSING"])
check("cannot judge tokens, recall low -> hard flag",
      decide_recall_flags({"text_recall": 0.90, "high_value_recall": None}),
      ["TEXT_RECALL_LOW"])

# --- behaviour around the 0.90 threshold ------------------------------------
# No document in the 12-file calibration corpus lands between 0.85 and 0.95, so the
# threshold's own neighbourhood is pinned here instead of left untested. These fix
# behaviour at the boundary; they are not a claim that 0.90 is the optimum.
BAND = " ".join(f"BMU-{i}" for i in range(1, 21))          # 20 distinct tokens


def band(missing):
    """Output that drops the first `missing` of the 20 tokens."""
    return " ".join(f"BMU-{i}" for i in range(1 + missing, 21))


check("19/20 present -> 0.95", qg.high_value_recall(BAND, band(1)), 0.95)
check("18/20 present -> 0.90", qg.high_value_recall(BAND, band(2)), 0.9)
check("17/20 present -> 0.85", qg.high_value_recall(BAND, band(3)), 0.85)
check("0.95 does not flag", decide_recall_flags({"text_recall": 0.99, "high_value_recall": 0.95}), [])
check("exactly 0.90 does not flag",
      decide_recall_flags({"text_recall": 0.99, "high_value_recall": 0.90}), [])
check("0.85 flags", decide_recall_flags({"text_recall": 0.99, "high_value_recall": 0.85}),
      ["HIGH_VALUE_MISSING"])

# 0.98 governs three decisions, so pin its neighbourhood the same way 0.90's is.
check("intact tokens downgrade a low prose recall",
      decide_recall_flags({"text_recall": 0.93, "high_value_recall": 0.98}),
      ["TEXT_RECALL_WATCH"])
check("just-lost tokens keep the hard flag",
      decide_recall_flags({"text_recall": 0.93, "high_value_recall": 0.979}),
      ["TEXT_RECALL_LOW"])
check("unmeasurable tokens keep the hard flag",
      decide_recall_flags({"text_recall": 0.93, "high_value_recall": None}),
      ["TEXT_RECALL_LOW"])

# --- a dead page withdraws the downgrade ------------------------------------
# Intact model codes said the technical values survived, and that was taken as
# permission to soften a low prose recall. `V5 UL9540A.pdf` showed the hole: 0.988
# of its codes intact while five pages, one of them 322 words, had left the
# document — and it passed as WATCH on the strength of the codes alone.
PAGE = Counter({f"w{i}": 1 for i in range(20)})
check("page fully present", qg.page_absent(PAGE, Counter({f"w{i}": 1 for i in range(20)})), 0.0)
check("page 3% gone stays clean",
      qg.page_absent(Counter({f"w{i}": 1 for i in range(30)}),
                     Counter({f"w{i}": 1 for i in range(29)})), 0.033)
check("page 10% gone is dead", qg.page_absent(PAGE, Counter({f"w{i}": 1 for i in range(18)})), 0.1)
check("page 15% gone is dead", qg.page_absent(PAGE, Counter({f"w{i}": 1 for i in range(17)})), 0.15)
check("too short to judge", qg.page_absent(Counter({"a": 1, "b": 1}), Counter()), None)

# Both signals are needed. High absence alone is ordinary serialisation noise —
# compat-list touches 14% absent on a page while losing nothing — and poor page
# recall alone fires on any reflowed page.
check("dead needs both signals",
      qg.content_dead_pages({"page_recalls": [0.99, 0.30, 0.20], "page_absent": [0.34, 0.34, 0.03]}),
      [1])
check("absence alone is not death",              # compat-list page 5: 0.84 recall, 14% absent
      qg.content_dead_pages({"page_recalls": [0.886, 0.841], "page_absent": [0.102, 0.143]}), [])
check("reflowed grid keeps its downgrade",       # compat-list, real numbers
      decide_recall_flags({"text_recall": 0.929, "high_value_recall": 1.0,
                           "page_recalls": [0.886, 0.841], "page_absent": [0.102, 0.143]}),
      ["TEXT_RECALL_WATCH"])
check("dead page overrides intact codes",        # V5 UL9540A page 3
      decide_recall_flags({"text_recall": 0.854, "high_value_recall": 0.988,
                           "page_recalls": [0.99, 0.059], "page_absent": [0.03, 0.343]}),
      ["TEXT_RECALL_LOW"])
check("deduplicated header is not a dead page",  # TÜV block: recall 0.30 but 3% absent
      decide_recall_flags({"text_recall": 0.93, "high_value_recall": 1.0,
                           "page_recalls": [0.99, 0.298], "page_absent": [0.02, 0.03]}),
      ["TEXT_RECALL_WATCH"])

# `intact` gates two different decisions with deliberately opposite polarity.
check("intact at the boundary", qg.high_value_intact({"high_value_recall": 0.98}), True)
check("just below the boundary", qg.high_value_intact({"high_value_recall": 0.979}), False)
check("unmeasurable is not intact", qg.high_value_intact({"high_value_recall": None}), None)
# Raising a region-drop detection needs positive evidence, so None must not
# corroborate: `intact is False`.
check("None does not corroborate a drop",
      qg.high_value_intact({"high_value_recall": None}) is False, False)
# Suppressing an alarm needs positive evidence the other way, so None must not
# suppress: `intact is not True`.
check("None does not suppress an alarm",
      qg.high_value_intact({"high_value_recall": None}) is not True, True)

# --- page markers are a gate input, not an artifact feature -----------------
# The written body has its markers stripped, so re-running the gate on a saved .md
# silently takes the whole-document fallback and answers a different question. That
# trap produced one wrong diagnosis; these lock the distinction.
MARKED = f"page one text{chr(10)}{qg.PAGE_MARK}{chr(10)}page two text"
check("marked output splits into pages", len(qg.split_pages(MARKED) or []), 2)
check("stripped output has no pages", qg.split_pages(MARKED.replace(qg.PAGE_MARK, "")), None)

# --- inject take / skip -----------------------------------------------------
DONOR_LINE = "Certified to IEC 62619 and UN38.3 for transport"


class _FakePdf:
    """Stands in for a PDF so the inject can be tested without one."""
    def __init__(self, pages):
        self.pages = pages


def _fake_page_texts(path):
    return path.pages


rr_page_texts = rr.page_texts
rr.page_texts = _fake_page_texts
try:
    # Output lacks the standards entirely -> the line is pulled in.
    md, got = rr.recover_high_value(_FakePdf([DONOR_LINE]), "Some unrelated prose here.")
    check("inject recovers missing standards", set(got) >= {"IEC 62619", "UN38.3"}, True)
    check("inject labels the source page", "(tr. 1)" in md, True)

    # Output already carries the same wording -> nothing is appended, because a
    # duplicate chunk is worse than a token the reader can find anyway.
    md2, got2 = rr.recover_high_value(_FakePdf([DONOR_LINE]), DONOR_LINE)
    check("inject skips a line already present", got2, [])
    check("inject leaves output untouched when nothing to add", md2, DONOR_LINE)

    # Under-counted is not missing: the token is in the output, just fewer times.
    # The multiplicity rule made the inject chase repeated page headers.
    md3, got3 = rr.recover_high_value(_FakePdf([DONOR_LINE, DONOR_LINE, DONOR_LINE]),
                                      "Certified to IEC 62619 and UN38.3 once only")
    check("inject ignores an under-counted token", got3, [])
    check("under-counted token is not listed as missing",
          rr.missing_high_value(_FakePdf([DONOR_LINE * 3]), DONOR_LINE), [])
finally:
    rr.page_texts = rr_page_texts

if FAILS:
    print(f"✗ {len(FAILS)} test hỏng:")
    for f in FAILS:
        print("   ·", f)
    sys.exit(1)
print("✓ tất cả test đạt")
