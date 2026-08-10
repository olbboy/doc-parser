#!/usr/bin/env python3
"""Put back the pages a layout-aware engine dropped, using a text-layer engine.

This is deliberately not a merge of two Markdown files. Two documents cannot be
aligned line by line without page/region anchors, and trying produces duplicated
chunks and broken tables. Instead: only pages already flagged as dropped are
touched, and only donor blocks whose content is genuinely absent from the primary
output are taken.

Absence is the only guard. An earlier version also skipped pages drawn as dense
ruled grids, on the theory that a layout engine always owns those — measurement
killed it: `compat-list.pdf` is 5078 vector paths per page and Docling parses it
perfectly, while the HV48100 nameplate is 3202 paths per page and Docling throws
it away. Path density tells you a grid is present, not whether the engine kept the
text inside it.
"""
import re

from quality_gates import (words, recall, page_texts, normalize,
                           high_value_tokens, PAGE_MARK)

BLOCK_MISSING = 0.50        # donor block counts as absent below this recall
# Insurance, not a tuned constant: it has never rejected a block — the highest
# other-page overlap measured was 0.71. It exists for the failure mode the page-local
# test cannot see on its own, where an engine dumps a page's content onto a
# neighbouring page and the block is already present, just not where it belongs.
# Do not lower it to 0.71 to make it fire; that would be fitting to this corpus.
BLOCK_NEARLY = 0.85         # ...unless the whole output already carries it this well
MIN_BLOCK_WORDS = 6


def split_blocks(md):
    """Markdown blocks, with contiguous table rows kept together as one block."""
    blocks, buf, in_table = [], [], False
    for line in md.splitlines():
        is_row = line.lstrip().startswith("|")
        if not line.strip() and not in_table:
            if buf:
                blocks.append("\n".join(buf).strip())
                buf = []
            continue
        if in_table and not is_row and line.strip():
            blocks.append("\n".join(buf).strip())
            buf, in_table = [], False
        in_table = is_row
        buf.append(line)
    if buf:
        blocks.append("\n".join(buf).strip())
    return [b for b in blocks if b]


def assign_block_pages(blocks, pages):
    """Map each donor block to the PDF page its wording overlaps most."""
    page_w = [words(p) for p in pages]
    out = []
    for b in blocks:
        bw = words(b)
        if sum(bw.values()) < MIN_BLOCK_WORDS:
            out.append(None)
            continue
        best, best_score = None, 0.0
        for i, pw in enumerate(page_w):
            score = sum(min(c, pw.get(w, 0)) for w, c in bw.items())
            if score > best_score:
                best, best_score = i, score
        # require the winning page to explain most of the block, else it is noise
        out.append(best if best_score >= 0.6 * sum(bw.values()) else None)
    return out


def recover(pdf_path, dropped_pages, donor_md, primary_md, primary_pages=None):
    """Return (markdown, repaired_pages). Empty repair list means nothing changed."""
    if not dropped_pages or not donor_md:
        return primary_md, []

    pages = page_texts(pdf_path)
    blocks = split_blocks(donor_md)
    assigned = assign_block_pages(blocks, pages)
    primary_words = words(primary_md)

    # No "this page is a dense grid, skip it" guard: on the HV48100 nameplate the
    # dropped table *is* the dense grid (3202 vector paths on that page), so such a
    # guard skips exactly the page that needs repair. What keeps a well-parsed grid
    # like compat-list untouched is the per-block absence test below — a block whose
    # content the primary already carries is never appended.
    # Absence is judged against the *page* the block belongs to, not the whole file.
    # On a 15-page product guide the words of a parts list ("Pin", "Tấm che", "giá
    # treo tường") recur everywhere, so a page-5 block whose combination was dropped
    # still scored 0.58-0.80 against the document and was refused. Against page 5's
    # own segment it scores 0.0. The document-wide check stays as a duplication
    # guard: a block the rest of the output already carries well is not re-inserted.
    page_words = [words(p) for p in (primary_pages or [])]

    repaired, additions = [], {}
    for p in dropped_pages:
        take = []
        for b, page in zip(blocks, assigned):
            if page != p:
                continue
            bw = words(b)
            local = recall(bw, page_words[p]) if p < len(page_words) else recall(bw, primary_words)
            whole = recall(bw, primary_words)
            if local is not None and local < BLOCK_MISSING and (whole or 0) < BLOCK_NEARLY:
                take.append(b)
        if take:
            additions[p] = take
            repaired.append(p + 1)                      # 1-based for humans

    if not additions:
        return primary_md, []

    if primary_pages:
        out = list(primary_pages)
        for p, take in additions.items():
            if p < len(out):
                out[p] = out[p].rstrip() + "\n\n" + "\n\n".join(take)
        return (PAGE_MARK + "\n").join(out), repaired

    # No page anchors in the primary output: append once, labelled, never inline.
    tail = "\n\n".join(
        f"## [khôi phục từ trang {p + 1}]\n\n" + "\n\n".join(take)
        for p, take in sorted(additions.items()))
    return primary_md.rstrip() + "\n\n" + tail + "\n", repaired


# --- sparse high-value recovery ---------------------------------------------
# A different failure from a dropped region: the page survives, but individual
# certification standards, model codes or temperature limits vanish inside it.
# `datasheet.pdf` loses IEC62477 / IEC62619 / IEC63056 / UN38.3 / 0-55°C while its
# page recall stays at 0.91-0.96, so page-level fill has nothing to grab — the donor
# block is not absent, only a few tokens inside it are. Recovery therefore works at
# line granularity, and appends rather than replaces so the layout engine's spec
# table stays exactly as it parsed it.
MAX_RECOVERED_LINES = 40
LINE_MISSING = 0.60


def missing_high_value(pdf_path, primary_md):
    """High-value tokens the text layer has and the output lost entirely.

    Absent, not under-counted — the same presence rule the gate uses. Comparing
    occurrence counts made the inject chase repeated page headers: on
    `V5 UL9540A.pdf` it "recovered" a document number that appeared 13 times in the
    output already, simply because the text layer repeated it 50 times.
    """
    ref = high_value_tokens("\n".join(page_texts(pdf_path)))
    got = high_value_tokens(primary_md)
    return sorted(tok for tok in ref if got.get(tok, 0) == 0)


def recover_high_value(pdf_path, primary_md):
    """Append the text-layer lines carrying tokens the primary output dropped.

    Returns (markdown, recovered_tokens). Lines are taken in page order, deduped,
    and only when the line itself is largely absent from the output — a line whose
    wording the primary already carries would add a duplicate chunk for the sake of
    one token.
    """
    missing = missing_high_value(pdf_path, primary_md)
    if not missing:
        return primary_md, []

    primary_words = words(primary_md)
    taken, seen, recovered = [], set(), set()
    for page_no, page in enumerate(page_texts(pdf_path), 1):
        for line in normalize(page).splitlines():
            line = line.strip()
            if not line or line in seen:
                continue
            hits = [t for t in missing if t in line]
            if not hits:
                continue
            lw = words(line)
            if sum(lw.values()) >= 3 and (recall(lw, primary_words) or 0) >= LINE_MISSING:
                continue                       # the output already says this
            seen.add(line)
            taken.append((page_no, line))
            recovered.update(hits)
            if len(taken) >= MAX_RECOVERED_LINES:
                break
        if len(taken) >= MAX_RECOVERED_LINES:
            break

    if not taken:
        return primary_md, []
    body = "\n".join(f"- (tr. {p}) {line}" for p, line in taken)
    tail = ("## [khôi phục token quan trọng]\n\n"
            "Các dòng dưới đây lấy trực tiếp từ text layer của PDF vì engine chính "
            "đã bỏ mất mã model, đơn vị hoặc chuẩn chứng nhận trong đó.\n\n" + body)
    return primary_md.rstrip() + "\n\n" + tail + "\n", sorted(recovered)
