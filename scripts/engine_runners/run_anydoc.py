#!/usr/bin/env python3
"""anydoc adapter. Prints Markdown on stdout; raises with anydoc's own message
(e.g. "OCR is required") so the router can escalate on it."""
import sys, anydoc
sys.stdout.write(anydoc.to_markdown(sys.argv[1]))
