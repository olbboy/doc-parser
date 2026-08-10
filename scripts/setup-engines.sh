#!/usr/bin/env bash
# Build the three engine venvs and pre-stage models for doc-parse.
# Idempotent: skips whatever already exists. Needs `uv` and Python 3.12.
set -euo pipefail

DP="${DOCPARSE_HOME:-$HOME/.local/share/doc-parse}"
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
export HF_HUB_ENABLE_HF_TRANSFER=1 MINERU_MODEL_SOURCE=huggingface

mkdir -p "$DP"

# markitdown[all] resolves to 0.1.5 without --prerelease because its `all` extra
# pulls a beta Azure package; 0.1.7 is the version this skill is tuned against.
if [ ! -x "$DP/lite/bin/python" ]; then
  "$UV" venv --python 3.12 "$DP/lite"
  VIRTUAL_ENV="$DP/lite" "$UV" pip install --prerelease=allow \
    "markitdown[all]==0.1.7" firecrawl-anydoc python-docx python-pptx openpyxl
fi

# ocrmac is macOS-only (Apple Vision); harmless to skip elsewhere.
if [ ! -x "$DP/docling/bin/python" ]; then
  "$UV" venv --python 3.12 "$DP/docling"
  EXTRAS="rapidocr,easyocr"
  [ "$(uname)" = "Darwin" ] && EXTRAS="$EXTRAS,ocrmac"
  VIRTUAL_ENV="$DP/docling" "$UV" pip install "docling[$EXTRAS]" hf_transfer
fi

# `six` is an undeclared MinerU dependency; without it the failure surfaces as a
# misleading "requires mineru[pipeline]" error. `mlx` is the Apple Silicon engine.
if [ ! -x "$DP/mineru/bin/python" ]; then
  "$UV" venv --python 3.12 "$DP/mineru"
  EXTRAS="core"
  [ "$(uname -m)" = "arm64" ] && [ "$(uname)" = "Darwin" ] && EXTRAS="core,mlx"
  VIRTUAL_ENV="$DP/mineru" "$UV" pip install "mineru[$EXTRAS]" six requests hf_transfer
fi

echo "== tải model MinerU pipeline =="
"$DP/mineru/bin/mineru-models-download" -s huggingface -m pipeline || true

# The downloader exits 0 while leaving this 810 MB checkpoint missing, which
# makes every later PDF parse die with a bare OSError. Fetch it explicitly.
echo "== bù checkpoint MFR mà mineru-models-download bỏ sót =="
"$DP/mineru/bin/python" - <<'PY'
from huggingface_hub import hf_hub_download
print(hf_hub_download('opendatalab/PDF-Extract-Kit-1.0',
                      'models/MFR/unimernet_hf_small_2503/model.safetensors'))
PY

echo "== tải model Docling =="
"$DP/docling/bin/docling-tools" models download || true

echo "Xong. Kiểm tra: $DP/lite/bin/python <skill>/scripts/probe_document.py <file>"
