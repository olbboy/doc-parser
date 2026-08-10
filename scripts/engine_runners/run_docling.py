#!/usr/bin/env python3
"""Docling adapter: layout + TableFormer, optional full-page OCR.

Takes many files in one call on purpose. A fresh Docling process pays ~10 s of
torch.compile warm-up before its first page; batching amortises that across the
whole group. Outputs are separated by a sentinel line.

OCR engine defaults come from the router. On Vietnamese, macOS Vision (vi-VT --
Apple's code, not vi-VN) and Tesseract (vie) both keep ~95% of diacritics;
RapidOCR keeps 44% despite nominally supporting `vi`, so it is not offered here.
"""
import argparse, sys
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions, AcceleratorOptions, AcceleratorDevice,
    TesseractCliOcrOptions, OcrMacOptions, EasyOcrOptions)
from docling.document_converter import DocumentConverter, PdfFormatOption

SPLIT = "<<<DOCPARSE-SPLIT>>>"
# Page anchors let the caller score recall per page and repair only the pages that
# lost content, instead of blind-merging two Markdown files.
PAGE_MARK = "<!-- docparse:page -->"

a = argparse.ArgumentParser()
a.add_argument("files", nargs="+"); a.add_argument("--ocr"); a.add_argument("--lang")
a = a.parse_args()

opt = PdfPipelineOptions()
opt.accelerator_options = AcceleratorOptions(num_threads=8, device=AcceleratorDevice.AUTO)
opt.do_table_structure = True
opt.table_structure_options.do_cell_matching = True
opt.do_ocr = bool(a.ocr)
if a.ocr:
    cls = {"ocrmac": OcrMacOptions, "tesseract": TesseractCliOcrOptions, "easyocr": EasyOcrOptions}[a.ocr]
    opt.ocr_options = cls(lang=[a.lang], force_full_page_ocr=True)

conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opt)})
for i, f in enumerate(a.files):
    if i:
        sys.stdout.write("\n" + SPLIT + "\n")
    sys.stdout.write(conv.convert(f).document.export_to_markdown(
        page_break_placeholder=PAGE_MARK))
