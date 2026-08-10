#!/usr/bin/env python3
"""MarkItDown adapter. Only used for sources no other engine reads
(.msg, .ipynb, .zip, URLs, audio) — it fails silently-empty on scanned PDFs."""
import sys
from markitdown import MarkItDown
sys.stdout.write(MarkItDown(enable_plugins=False).convert(sys.argv[1]).text_content)
