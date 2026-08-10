---
name: doc-parse
description: "Convert PDF/DOCX/XLSX/PPTX to Markdown by auto-detecting the document and routing it to the cheapest engine that can handle it (anydoc, MarkItDown, Docling, MinerU). Use for RAG ingestion, bulk conversion, scanned Vietnamese PDFs, hidden-sheet workbooks, and dense technical tables."
user-invocable: true
when_to_use: "Invoke when converting documents to Markdown for a knowledge base or RAG index, or when one parser produced broken tables, missing headings, or empty output."
category: data
keywords: [pdf, docx, xlsx, pptx, markdown, ocr, rag, docling, mineru, anydoc, markitdown]
argument-hint: "<file-or-glob> [-o outdir] [--dry-run]"
metadata:
  author: BLVERA
  version: "2.0.0"
---

# doc-parse — chọn engine theo tài liệu, không theo thói quen

Bốn công cụ, không cái nào thắng mọi ca. Skill này **probe file trước (CPU, <100 ms, không model)**, phân loại, rồi gọi engine rẻ nhất còn đủ sức. Mọi ngưỡng trong router đều là số đo trên một corpus tài liệu kỹ thuật thật, không phải phỏng đoán.

## Dùng

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python
S=.claude/skills/doc-parse/scripts

$DP $S/probe_document.py file.pdf                 # chỉ xem sẽ đi tier nào
$DP $S/parse_document.py *.pdf *.xlsx -o parsed/  # parse thật
$DP $S/parse_document.py docs/*.pdf -o out/ --dry-run   # xem kế hoạch cho cả lô
$DP $S/parse_document.py file.pdf -o out/ --engine docling   # ép engine
```

Cài engine lần đầu: `bash .claude/skills/doc-parse/scripts/setup-engines.sh` (~3,4 GB venv + ~2 GB model, tải một lần).

## Bậc thang

| Bậc | Engine | Dùng cho | Chi phí đo được |
|---|---|---|---|
| **T0** | anydoc | Office đơn giản, PDF text layer bố cục thường | 0,5–150 ms/file |
| **T0b** | MarkItDown | `.msg` `.ipynb` `.zip` URL audio — nguồn không ai khác đọc được | — |
| **T1** | MinerU (HTTP `office`) | XLSX có sheet ẩn / nhiều ô gộp, DOCX có ô gộp, mọi PPTX | 0,03–0,8 s/file |
| **T2** | Docling | PDF bảng lưới dày, bảng thông số không kẻ viền, **mọi PDF scan** | 2,1 trang/s |
| **T3** | MinerU `hybrid-engine` | cần giữ `colspan`/`rowspan` thật, hoặc công thức | 0,17 trang/s — chạy lô |

## Router quyết định thế nào

| Tín hiệu probe | → | Lý do (đã đo) |
|---|---|---|
| PDF `chars/page < 50` | T2 + OCR | không có text layer; anydoc báo lỗi, **MarkItDown trả rỗng mà vẫn `ok=True`** |
| PDF `paths/page > 400` | T2 | bảng lưới dày. `compat-list.pdf` = 5078 nét/trang; anydoc gộp header 2 tầng vào 1 ô |
| PDF có hình + `chars/page < 1200` | T2 | bảng thông số không kẻ viền. Ghép nhãn↔giá trị: Docling 3/3, MinerU 3/3, MarkItDown 1/3, **anydoc 0/3** |
| XLSX có sheet ẩn | T1 | anydoc + MarkItDown lộ **18/18** sheet ẩn; Docling và MinerU lọc sạch |
| XLSX > 50 vùng gộp | T1 | chỉ HTML của MinerU giữ được span |
| DOCX ≥ 3 bảng có `gridSpan`/`vMerge` | T1 | `<td><p>` giữ nhiều giá trị trong một ô |
| PPTX | T1 | engine duy nhất dựng được tiêu đề slide, kể cả khi file không dùng title placeholder |
| `.doc/.xls/.ppt` cũ | T0 | chỉ anydoc đọc được |
| còn lại | T0 | anydoc |

**Phải đếm cả `vMerge`**, không chỉ `gridSpan`: ô nối tiếp của gộp dọc vẫn sinh một `<w:tc>`, nên phép so `số ô ≠ hàng × cột` bỏ sót toàn bộ gộp dọc.

## OCR tiếng Việt

Router chọn theo hệ điều hành: **macOS → Vision `vi-VT`** (mã của Apple, *không phải* `vi-VN` — dùng sai thì Docling raise lỗi), **Linux → Tesseract `vie`**. Hai engine này tương đương nhau; chọn theo nền tảng, không theo chất lượng.

Đo trên 6 trang scan của HV48100 user manual (1.780 từ, 1.576 ký tự có dấu, ground truth = text layer gốc):

| Engine | word recall | ký tự có dấu | giây/6 trang |
|---|---|---|---|
| Tesseract `vie` | 96,7% | 97% | 23 |
| MinerU `vlm-engine` (Pro-2605) | 96,2% | **99,8%** | 50 |
| macOS Vision `vi-VT` | 96,1% | 97% | 22 |
| EasyOCR `vi` | 91,3% | 94% | 29 |
| **RapidOCR `vi`** | **49,7%** | **46%** | 25 |
| **MinerU `pipeline`** | **51,9%** | **50%** | 18 |
| MarkItDown | **0%** | 0 | 0,01 |

**Không dùng RapidOCR cho tiếng Việt** dù nó khai báo hỗ trợ `vi`. **Không dùng MinerU backend `pipeline`** cho tiếng Việt — tập model OCR của nó không có tiếng Việt và `mineru --lang` không nhận `vi`.

Vì vậy chuỗi dự phòng cho PDF scan là `docling+OCR → mineru:vlm-engine`, **không bao giờ** `pipeline`. Đây từng là bug thật: `parse_one` gán `backend="pipeline"` cho mọi tier ≠ T3, nên một scan tiếng Việt mà Docling lỗi sẽ rơi thẳng vào đường phá dấu.

## Hai quy tắc vận hành bắt buộc

1. **Không bao giờ shell ra `mineru` CLI trong vòng lặp.** CLI trả phí import interpreter + torch mỗi lần gọi: đo được 6,4 s/file so với 0,03 s qua HTTP. Skill tự dựng `mineru-api` thường trú ở `127.0.0.1:8123` khi cần và tái dùng.
2. **Gom file Docling thành lô.** Tiến trình Docling mới tốn ~10 s `torch.compile` trước trang đầu. Truyền nhiều file trong một lệnh — skill tự gom nhóm cùng cấu hình OCR vào một tiến trình (đo được: 2 file 33 s gộp so với 88 s tách).

## Cờ chất lượng trong frontmatter

Mỗi file ra kèm YAML frontmatter: `parser`, `parser_tier`, `parser_reason`, `attempts`, `quality_flags`.

| Cờ | Nghĩa | Xử lý |
|---|---|---|
| `PARSE_FAILED` | mọi engine thất bại | **không index**, vào hàng chờ |
| `EMPTY_SUCCESS` | engine báo thành công nhưng 0 ký tự | **không index** — chế độ hỏng nguy hiểm nhất |
| `HIDDEN_SHEET_LEAK_RISK` | workbook có sheet ẩn | rà trước khi index; sheet ẩn trong HSMT thường là phương án cũ hoặc giá nội bộ |
| `PANDAS_NOISE` | output có `NaN`/`Unnamed:` | đổi engine (MarkItDown sinh 16.724 token `NaN` trên một file CKKT) |
| `DENSE_TABLE_GRID` / `BORDERLESS_SPEC_TABLE` | tài liệu bảng khó | đã tự lên T2 |
| `NO_HEADING_STYLES` | DOCX không dùng Heading style | **sửa template**, không parser nào cứu được |
| `LAYOUT_RISK_UNADDRESSED` | tài liệu khó nhưng phải dùng engine rẻ | xếp lại lịch chạy |
| `TEXT_RECALL_LOW` | mất > 5% từ, **và** mất cả mã model/đơn vị **hoặc** có trang nội dung chết | không auto-index |
| `TEXT_RECALL_WATCH` | mất 2–5% từ, hoặc mất > 5% nhưng token quan trọng còn nguyên | ghi số, index bình thường |
| `HIGH_VALUE_MISSING` | mất > 10% mã model / đơn vị / chuẩn IEC — kể cả khi `text_recall` cao, **và inject không cứu được** | rà tay trước khi index |
| `HIGH_VALUE_RECOVERED` | đã kéo lại được mã/đơn vị/chuẩn bị mất từ text layer | xem `high_value_recovered` |
| `REGION_DROPPED` | engine vứt cả một vùng có chữ; **đã tự vá** | xem `repaired_pages` |
| `REGION_DROPPED_UNREPAIRED` | phát hiện vùng bị vứt nhưng không vá được, và có bằng chứng độc lập là mất thật | xem `dropped_pages`, đổi engine |

## Cái gì được vào index

```
chặn:  PARSE_FAILED · EMPTY_SUCCESS · TEXT_RECALL_LOW · HIGH_VALUE_MISSING
       (+ HIDDEN_SHEET_LEAK_RISK cho workbook thầu)
vào:   mọi thứ còn lại — WATCH · REGION_DROPPED · HIGH_VALUE_RECOVERED là dấu vết
       "đã can thiệp", không phải phiếu phủ quyết
```

**`high_value_recall = None` không chặn.** Tài liệu ít hơn 5 loại mã/đơn vị thì không đủ căn cứ để kết luận, và đó không phải bằng chứng mất mát — đòi một tín hiệu high-value dương mới cho index sẽ phạt đúng lớp cert và báo cáo ngắn. `04-iec-60731` sau khi vá đạt `text_recall` 0,985 với `hv = None`: vào index bình thường.

**Cờ chấm trên bản cuối cùng đưa vào index, không phải trên output thô của engine.** Nên vá một trang có thể làm trang khác thôi bị coi là chết — từ vựng của nó giờ nằm trong khối vừa chèn, tức nó *đang có* trong tài liệu. Đó là hệ quả của việc `page_absent` hỏi "chữ này còn trong tài liệu không", không phải lỗi. Muốn xem engine thô bỏ gì thì chạy `--engine` ép và đọc số trước khi vá; đừng gắn cờ theo đó.

## Ba thước đo, không một ngưỡng

Không có một con số nào phân biệt được "vứt mất một khối" với "sắp xếp lại một bảng lưới". Nên có ba, và cờ cứng cần **hai tín hiệu đồng ý**:

| Chỉ số (ghi trong frontmatter) | Đo gì |
|---|---|
| `text_recall` | tỉ lệ từ trong text layer gốc sống sót vào output |
| `high_value_recall` | tỉ lệ **loại** token quan trọng còn sống sót ít nhất một lần: mã model (`BMU-8`), đơn vị (`51.2V`, `5.12kWh`), mã DIP, chuẩn (`IEC62619`, `UN38.3`) |
| `page_recalls[i]` | như trên nhưng theo từng trang, để khoanh vùng trang nào mất; các trang < 0,90 được ghi vào frontmatter thành `low_recall_pages` |
| `page_absent[i]` | tỉ lệ từ vựng của trang **biến mất khỏi toàn tài liệu** — miễn nhiễm với header lặp, vì header luôn có mặt ở trang khác |

Vì sao cần cả ba — hai ca thật đứng cạnh nhau:

| File | `text_recall` | `high_value_recall` | Kết luận |
|---|---|---|---|
| `compat-list.pdf` (Docling) | 0,929 | **1,000** | Docling **đúng** — nó sắp xếp lại lưới dày chứ không mất gì. Chỉ `WATCH` |
| `hv48100` trang nhãn (Docling thuần) | 0,638 | **0,032** | Docling **mất thật** cả bảng 14 model → vá |
| `datasheet.pdf` (Docling thuần) | 0,930 | **0,842** | mất 3–4 chuẩn `IEC*`/`UN38.3` nằm rải trong bảng thông số |
| `datasheet.pdf` (sau `hv-inject`) | **0,952** | **1,000** | đã kéo lại đủ từ text layer |

**Ngưỡng `HIGH_VALUE_MISSING = 0,90` đã được kiểm chứng**, không phải phỏng đoán: 0 báo động giả trên 12 tài liệu / 5 lớp, hai ca mất thật (0,842 và 0,032) nằm rất xa. Caveat trung thực: corpus không có file nào trong vùng 0,85–0,95, nên 0,90 đúng ở chỗ không gây hại chứ chưa phải điểm tối ưu đo được; hành vi quanh ngưỡng được pin bằng unit test.

**`high_value_recall` đếm sự hiện diện, không đếm số lần.** Một số hiệu tài liệu lặp ở header 47 trang mà engine gộp lại còn 13 lần **không** bị tính là mất. Cách đếm theo bội số từng làm cả 3/3 lần cờ bắn trên 12 tài liệu đều là báo động giả, trong khi cách đếm hiện diện giữ nguyên hai ca mất thật (0,842 và 0,032 — đều dưới 0,90 rất xa). 

## Hai kiểu vá, hai kiểu mất

| Kiểu mất | Dấu hiệu | Cách vá | Ví dụ |
|---|---|---|---|
| **Region drop** | cả trang mất chữ, recall trang < 0,90 + placeholder ảnh | anydoc page-fill: chèn lại khối donor vắng, đúng trang | `hv48100` bảng nhãn 14 model |
| **Sparse high-value drop** | trang còn nguyên, chỉ vài mã/chuẩn bên trong biến mất | token-inject: lấy đúng dòng text layer chứa token, append cuối, **không đụng bảng** | `datasheet` mất 4 chuẩn IEC/UN |

Hai kiểu này cần hai công cụ khác nhau. Trên `datasheet`, page-fill chạy nhưng lấy được **0 khối** — khối donor không hề vắng, chỉ vài token bên trong nó vắng. Đó là lý do phải có tầng thứ hai làm việc ở mức dòng.

**Đừng chạy lại gate trên body `.md` đã ghi.** Mốc trang (`<!-- docparse:page -->`) là neo nội bộ, bị gỡ trước khi ghi để không làm bẩn chunk RAG — nên chạy lại `region_dropped_pages` trên artifact sẽ âm thầm rơi vào nhánh dự phòng và trả lời một câu hỏi khác. Muốn audit quyết định vá thì đọc `low_recall_pages` / `dropped_pages` / `repaired_pages` trong frontmatter.

Mọi cờ chỉ được quyết định **sau khi cả hai bước vá chạy xong**, để không còn báo động thừa trên output mà bước sau đã sửa.

**Hai giới hạn đã biết, cố ý chưa xử lý:**

- *Mất một token đơn lẻ trong túi high-value lớn.* `bao-gia-pin-v16.pdf` rơi mất `20,48kWh` — dung lượng trong bảng báo giá — nhưng hv vẫn 0,980. Hạ ngưỡng để bắt nó sẽ kéo lại hai ca sạch. Cần một cờ mềm riêng, không nhét vào `HIGH_VALUE_MISSING`.
- *Text layer hỏng.* Tài liệu có ToUnicode lỗi cho ra mojibake (`FDO 3DUDPHWHUV`); "mất token" ở đó là mất so với một ground truth không đọc được. Luật lọc hiện tại (`tỉ lệ dòng một ký tự ≥ 0,50`) không bắt loại này.

Chọn engine cho cert: **để router quyết**. Ép `--engine docling` lên SDS/UN38.3 không cứu thêm mã chuẩn nào (hv đã 1,000 ở cả hai đường) mà mất thêm prose (`text_recall` 0,985→0,973 và 0,964→0,908) và tốn 150–190× thời gian.

**Mã model còn nguyên không có nghĩa là văn xuôi còn nguyên.** Luật hạ cấp `TEXT_RECALL_LOW → WATCH` khi `hv` intact bị **rút lại** ngay khi có một *trang nội dung chết*:

```
content_dead(page) ⇔ page_recall < 0,50  AND  page_absent >= 0,10
```

`V5 UL9540A.pdf` giữ 0,988 mã chuẩn trong khi 5 trang — một trang 322 từ — biến mất khỏi output, và từng lọt qua chỉ với `WATCH` nhờ đúng số mã chuẩn đó.

`page_absent ≥ 0,10` **một mình là nhiễu tuần tự hoá bình thường**, không phải tín hiệu: `V5 UL9540A.pdf` có 30/47 trang vượt mốc đó nhưng chỉ 5 trang thực sự chết. Vì vậy frontmatter chỉ ghi `content_dead_pages`; đừng nâng con số 30 thành cảnh báo.

Ngưỡng `0,10` là **tạm thời, hiệu chỉnh bên trong phép hội** — chọn từ khe 3% (header lặp) so với 15%+ (mất thật) *trong nhóm đã lọc bởi `page_recall < 0,50`*, trên 8 trang ứng viên. Nó **chưa** được hiệu chỉnh như một chỉ số độc lập, và đo rộng hơn có thể làm khe dịch.

Hai điều kiện **phải đi cùng**, mỗi cái loại một kiểu nhiễu: `page_recall` thấp một mình bắt nhầm trang bị sắp xếp lại; `page_absent` cao một mình bắt nhầm nhiễu tuần tự hoá thông thường — `compat-list` chạm 14% trên một trang mà không mất gì. Đừng thay bằng "trang có bao nhiêu loại từ": đo trên corpus thì đại lượng đó **nghịch** với mất mát (khối header TÜV 74 loại từ mất 3%; header một dòng 27 loại từ mất 15%).

`high_value_recall` cũng là thứ chốt cờ `REGION_DROPPED_UNREPAIRED`: khi vá không lấy được gì **và** mọi mã model/đơn vị còn nguyên thì chính phép phát hiện đã báo nhầm — đúng ca `compat-list`, nơi Docling trải một bảng lưới qua nhiều trang mà không mất dấu ✓ nào.

Nếu chỉ nhìn `text_recall` thì hai ca này gần như nhau (0,93 vs 0,64 còn phân biệt được, nhưng trên toàn tài liệu 34 trang thì Docling chỉ tụt xuống 0,957 — dưới mọi ngưỡng hợp lý). `high_value_recall` mới là thứ tách bạch chúng.

## Vá vùng bị vứt (`REGION_DROPPED`)

Kích hoạt khi **recall của một trang < 0,90** và có thêm một tín hiệu xác nhận: engine để lại `<!-- image -->` ở trang mà text layer vẫn còn chữ, **hoặc** cả tài liệu mất mã model/đơn vị. Khi đó chạy anydoc (~0,2 s) và **chỉ chèn lại những khối mà output chính thực sự không có** (recall của khối < 0,5), đúng trang đó.

Khối donor được so với **đoạn output của đúng trang nó thuộc về**, không so với toàn tài liệu. Trên một quick guide 15 trang, từ vựng của danh sách phụ kiện (`Pin`, `Tấm che`, `giá treo tường`) lặp khắp nơi, nên khối trang 5 bị mất vẫn "trông như đã có" tới 58–80% và bị từ chối; so với đoạn trang 5 thì nó bằng 0. Phép so toàn tài liệu giữ lại làm **guard chống trùng** (`BLOCK_NEARLY` 0,85).

Đây **không phải merge hai file Markdown**. Không có neo trang/vùng thì merge mù sinh chunk trùng và bảng vỡ. Ở đây Docling xuất kèm mốc trang (`page_break_placeholder`), khối donor được gán trang bằng độ trùng từ vựng, và bảng nào Docling đã dựng đúng thì không bị đụng tới.

Đo được trên 3 trang HV48100 (16–18): `text_recall` 0,638 → **0,989**, `high_value_recall` 0,138 → **1,000**, bảng 14 dòng model quay lại đầy đủ. Cùng lúc `compat-list.pdf` **không bị vá** — 246 dấu ✓ nguyên vẹn, parser vẫn là `docling`.

**Không có luật "trang lưới dày thì bỏ qua".** Trên HV48100 chính bảng bị vứt lại là lưới dày nhất tài liệu (3.202 nét vẽ/trang) — luật đó sẽ bỏ qua đúng trang cần cứu. Thứ giữ `compat-list` an toàn là phép thử vắng-mặt theo từng khối, không phải mật độ nét vẽ.

## Chuỗi dự phòng

Dựng lại **sau mỗi lần thất bại**, không dựng một lần trước vòng lặp. Khi anydoc trả `"OCR is required"`, router đặt `needs_ocr=True` và chuỗi còn lại **chỉ giữ engine có OCR** — nếu dựng trước, MarkItDown vẫn nằm cuối chuỗi và sẽ được thử trên PDF scan, đúng engine trả rỗng im lặng.

## Bẫy cài đặt đã gặp thật

- `mineru-models-download` báo `exit 0` nhưng thiếu `models/MFR/unimernet_hf_small_2503/model.safetensors` (810 MB) → mọi lần parse PDF chết. `setup-engines.sh` tải bù file này.
- `six` là dependency ẩn của MinerU 3.4.4; thiếu nó thì lỗi hiện ra dưới dạng `HybridDependencyError` sai lệch.
- `pip install "markitdown[all]"` mặc định ra 0.1.5 chứ không phải 0.1.7 (extra `all` cần pre-release Azure) → cần `--prerelease=allow`.
- Docling và MinerU đều tải model qua HuggingFace lần đầu; môi trường có allowlist phải pre-stage.
