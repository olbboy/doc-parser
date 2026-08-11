<p align="center">
  <img src="docs/assets/doc-parser.png" alt="doc-parser" width="120" />
</p>

<h1 align="center">doc-parser</h1>
<h3 align="center">Bộ định tuyến phân tích tài liệu · PDF / DOCX / XLSX / PPTX → Markdown</h3>

<p align="center"><em>Chọn engine rẻ nhất còn đủ sức xử lý từng tài liệu.</em></p>

<p align="center">
  <a href="https://github.com/olbboy/doc-parser/releases"><img src="https://img.shields.io/github/v/release/olbboy/doc-parser?color=blue" alt="release" /></a>
  <a href="https://github.com/olbboy/doc-parser/stargazers"><img src="https://img.shields.io/github/stars/olbboy/doc-parser?style=flat&logo=github" alt="stars" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="license MIT" /></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-Keep%20a%20Changelog-orange" alt="changelog" /></a>
</p>

<p align="center">
  🌐 <a href="README.md">English</a> ·
  <a href="README_AI.md">AI Bootstrap</a> ·
  <a href="docs/SKILL.md">Tài liệu tham khảo</a> ·
  <a href="docs/document-parsing-field-notes.md">Field Notes</a>
</p>

<br/>

## Giới thiệu

> **Nếu bạn là AI agent, hãy đọc [README_AI.md](README_AI.md) và thực thi ngay.**

`doc-parser` chuyển **PDF / DOCX / XLSX / PPTX** thành Markdown sạch cho pipeline RAG.
Thay vì đẩy mọi file qua cùng một parser, công cụ này **probe file trước** (CPU, < 100 ms,
không load model), định tuyến đến engine rẻ nhất đủ khả năng, đo những gì engine bỏ sót,
và sửa lại.

Mọi ngưỡng trong router đều lấy từ số đo trên corpus tài liệu kỹ thuật thật — không phải
phỏng đoán. Chi tiết xem [`docs/document-parsing-field-notes.md`](docs/document-parsing-field-notes.md).

---

## Tại sao phải định tuyến

Không engine nào thắng mọi ca. Đo trên cùng bộ tài liệu:

| | anydoc | MarkItDown | Docling | MinerU |
|---|---|---|---|---|
| Tốc độ file Office | **0,5 – 20 ms** | 23 – 1.076 ms | 94 – 923 ms | 27 – 802 ms (HTTP) |
| Bảng lưới dày | gộp header | 24 dải phân cách rỗng | **đúng cột** | **đúng + `colspan` thật** |
| Bảng thông số không viền (nhãn↔giá trị) | 0/3 | 1/3 | **3/3** | **3/3** |
| Sheet ẩn trong workbook | lộ 18/18 | lộ 18/18 | **lọc sạch** | **lọc sạch** |
| PDF scan | báo lỗi rõ | **`ok=True`, 0 ký tự** | OCR | OCR |
| OCR tiếng Việt (giữ dấu) | — | 0% | **96–97%** (Vision / Tesseract) | **99,8%** (VLM) |

Chế độ hỏng nguy hiểm nhất: MarkItDown trả `ok=True` với 0 ký tự trên PDF scan — tài liệu
vào index như trang trắng, không ai biết.

---

## Cách hoạt động

```
probe    (CPU, <100 ms, không model)
  ↓
route  → T0 anydoc · T0b MarkItDown · T1 MinerU/office · T2 Docling · T3 MinerU/hybrid
  ↓
gate   → text_recall · high_value_recall · page_absent
         (so với text layer gốc của PDF)
  ↓
repair → page-fill từ engine text-layer (region drop)
         token-inject từ text layer (mất token thưa)
  ↓
flag   → chấm điểm trên output cuối, sau mọi bước vá
```

Mỗi file output kèm YAML frontmatter: engine đã chạy, lý do chọn, những gì đã vá, cờ chất
lượng nào bắt — parse hỏng sẽ thấy được thay vì im lặng.

### Các bậc định tuyến

| Bậc | Engine | Dùng cho | Chi phí đo được |
|---|---|---|---|
| **T0** | anydoc | Office đơn giản, PDF text layer thường | 0,5 – 150 ms/file |
| **T0b** | MarkItDown | `.msg`, `.ipynb`, `.zip`, URL, audio | — |
| **T1** | MinerU `office` | XLSX có sheet ẩn / ô gộp, DOCX có ô gộp, mọi PPTX | 0,03 – 0,8 s/file |
| **T2** | Docling | PDF bảng lưới dày, bảng thông số không viền, **mọi PDF scan** | 2,1 trang/s |
| **T3** | MinerU `hybrid` | Cần giữ `colspan`/`rowspan` thật hoặc công thức | 0,17 trang/s — chạy lô |

---

## Cài đặt nhanh

### Yêu cầu

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv)
- ~3,4 GB cho engine venvs; ~2 GB model (tải một lần)

### Cài

```bash
git clone https://github.com/olbboy/doc-parser.git
cd doc-parser
bash scripts/setup-engines.sh
```

Trên **Apple Silicon**: tự cài MinerU MLX backend.
Trên **Linux**: dùng Tesseract thay macOS Vision cho OCR.

### Parse đầu tiên

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python

# Probe file — xem sẽ đi tier nào, kèm lý do
$DP scripts/probe_document.py report.pdf

# Chuyển đổi
$DP scripts/parse_document.py report.pdf -o out/
```

---

## Cờ chất lượng

| Cờ | Nghĩa | Xử lý |
|---|---|---|
| `PARSE_FAILED` | Mọi engine thất bại | **Không index** |
| `EMPTY_SUCCESS` | Engine báo thành công nhưng 0 ký tự | **Không index** — nguy hiểm nhất |
| `HIDDEN_SHEET_LEAK_RISK` | Workbook có sheet ẩn | Rà trước khi index |
| `TEXT_RECALL_LOW` | Mất > 5% từ **và** mất mã model/đơn vị **hoặc** có trang chết | **Không index** |
| `HIGH_VALUE_MISSING` | Mất > 10% mã model/đơn vị/chuẩn sau khi vá | Rà tay trước khi index |
| `HIGH_VALUE_RECOVERED` | Đã kéo lại được mã/đơn vị từ text layer | Dấu vết kiểm toán |
| `REGION_DROPPED` | Engine vứt một vùng — **đã tự vá** | Xem `repaired_pages` |
| `TEXT_RECALL_WATCH` | Mất 2–5%, token quan trọng còn nguyên | Ghi nhận, index bình thường |

### Chính sách index

```
Chặn:  PARSE_FAILED · EMPTY_SUCCESS · TEXT_RECALL_LOW · HIGH_VALUE_MISSING
Cho qua: mọi thứ còn lại — WATCH · REGION_DROPPED · HIGH_VALUE_RECOVERED là dấu vết kiểm toán
```

---

## Hai quy tắc vận hành bắt buộc

1. **Không bao giờ shell ra `mineru` CLI trong vòng lặp.** Đo được 6,4 s/file so với
   0,03 s qua HTTP. Công cụ dùng `mineru-api` thường trú.

2. **Gom file Docling thành lô.** Tiến trình mới tốn ~10 s `torch.compile`. 2 file gộp:
   33 s. 2 file tách: 88 s.

---

## Biến môi trường

| Biến | Mặc định | Mục đích |
|---|---|---|
| `DOCPARSE_HOME` | `~/.local/share/doc-parse` | Gốc cho tất cả engine venv và model cache |
| `DOCPARSE_MINERU_URL` | `http://127.0.0.1:8123` | URL của `mineru-api` thường trú |
| `DOCPARSE_CORPUS_ROOT` | *(không có)* | Path đến corpus rộng hơn cho hiệu chỉnh ngưỡng |

---

## Kiểm thử

```bash
# Unit test — không cần PDF
$DP scripts/test_quality_gates.py

# Regression suite (cần 3 file PDF fixture — xem testdata/README.md)
$DP scripts/run_regression.py
```

---

## Tài liệu

| File | Nội dung |
|---|---|
| [`docs/SKILL.md`](docs/SKILL.md) | Bảng định tuyến, ngữ nghĩa cờ, bằng chứng ngưỡng — **đọc đây trước** |
| [`docs/document-parsing-field-notes.md`](docs/document-parsing-field-notes.md) | Những gì đã đo: hành vi engine, bẫy cài đặt, OCR tiếng Việt, 7 kết luận bị đảo ngược |
| [`docs/measurement-driven-upgrade-playbook.md`](docs/measurement-driven-upgrade-playbook.md) | Cách nâng cấp an toàn: đo trước quyết định, thiết kế thước đo, versioning |
| [`testdata/README.md`](testdata/README.md) | Đặc tả fixture regression |
| [`examples/parse-datasheet/README.md`](examples/parse-datasheet/README.md) | Ví dụ đầu-cuối: parse datasheet bảng thông số không viền |
| [`README_AI.md`](README_AI.md) | Bootstrap cho AI agent |
| [`CHANGELOG.md`](CHANGELOG.md) | Lịch sử phiên bản |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Hướng dẫn đóng góp |

---

## Đóng góp

Xem [CONTRIBUTING.md](CONTRIBUTING.md). Nguyên tắc cốt lõi: **đo trước khi thay đổi bất kỳ ngưỡng hoặc luật định tuyến nào.**

---

## License

MIT — xem [LICENSE](LICENSE).
