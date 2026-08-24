# Đánh giá deepdoctection — khả năng nâng cấp `doc-parser` và `pdf-translate-layout`

Ngày: 2026-08-24 · Nguồn: `deepdoctection/deepdoctection` @ HEAD (v1.3.0, 2026-08-16), Apache-2.0, 3 246 sao, 8 issue mở.

## Kết luận (TL;DR)

| | Kết luận |
|---|---|
| Dùng deepdoctection làm **engine** (tier T4) trong doc-parser | **Không.** Backbone cũ (Detectron2 F-RCNN / DETR-DocLayNet / TATR / doctr), vắng mặt khỏi mọi benchmark parser 2026, nặng hơn Docling+MinerU đang có. Vi phạm nguyên tắc "engine rẻ nhất làm được việc". |
| Dùng deepdoctection làm **dependency runtime** | **Không.** Dự án gần như một-maintainer (JaMe76 ký toàn bộ release gần đây). |
| **Trích thuật toán/ý tưởng** sang cả 2 repo | **Có.** 6 thứ cụ thể, Apache-2.0 → tương thích cả MIT (doc-parser) lẫn AGPL-3.0 (pdf-translate-layout). |

Giá trị thật của deepdoctection không nằm ở model — nằm ở **lớp thuật toán hình học giữa detector và output**: thứ tự đọc theo cột, tiling bảng, refine cấu trúc ô, và metric TEDS. Đó chính là mảng cả hai repo đang mỏng nhất.

---

## 1. deepdoctection là gì (thực chất)

Monorepo 3 package: `dd_core` (datapoint/dataflow/mapper/utils) · `dd_datasets` · `deepdoctection` (pipe/extern/analyzer/eval/train).

Pipeline chuẩn (`analyzer/dd.py`, config `configs/conf_dd_one.yaml`):
```
Rotator → Layout detection → Table segmentation (row/col/cell) → Table refinement
        → OCR / PDF-miner → Word matching → Text ordering → Layout link (caption↔figure)
```
Mỗi stage là một `PipelineComponent` đăng ký vào `pipeline_component_registry`; dữ liệu là `Image` datapoint mang `ImageAnnotation` có sub-category, relationship cha/con và `service_id` (biết annotation nào do service nào sinh ra), serialise JSON được.

**So sánh với doc-parser:** doc-parser là *router* — probe → chọn engine → gate → repair. deepdoctection là *framework tự dựng engine*. Không cùng tầng. doc-parser không nên trở thành cái thứ hai.

**Vị thế thị trường 2026:** các benchmark parser mã nguồn mở năm nay xoay quanh Marker v2 / MinerU / Docling; deepdoctection không xuất hiện. Đây là tín hiệu rõ về độ chính xác end-to-end — nhưng không phủ định giá trị của các thuật toán rời bên trong.

---

## 2. Sáu thứ đáng lấy

### A. `OrderGenerator.order_blocks` — thứ tự đọc theo cột
`packages/deepdoctection/src/deepdoctection/pipe/order.py:201`

Thuật toán:
1. Sort block theo `(cy, cx)`.
2. Gán cột tham lam. Một block vào cột hiện có nếu **(x-chứa nhau theo một trong hai chiều, sai số `starting_point_tolerance=0.005` toạ độ tương đối) HOẶC (nối dòng gãy, `broken_line_tolerance=0.003`)** — **VÀ** kề dọc (`height_tolerance=2.0` × chiều cao block).
3. `_consolidate_columns` (`order.py:332`): ma trận IoA giữa các cột, `> 0.9` → cột con gộp vào cột cha.
4. `_connected_components` (`order.py:165`): nhóm các cột **chồng nhau theo trục y** thành component. Component sort theo `top`; cột trong component sort theo `(ulx, uly)`; block trong cột sort theo `(uly, ulx)`.

Bước 4 là mấu chốt: một tiêu đề chạy hết bề ngang nằm trên thân 2 cột tạo **component riêng** và được đọc trước — chứ không bị nhét vào một trong hai cột.

### B. `TableSegmentationRefinementService` — ép cấu trúc bảng thành hợp lệ
`pipe/refine.py:51-410`

Sau khi gán ô → `(row, col, rowspan, colspan)`, kết quả có thể **không hợp lệ**: hai ô cùng chiếm một tile, tile trống, vùng gộp không chữ nhật. Refine:
1. `tiles_to_cells` (`refine.py:51`): nổ mỗi ô thành các tile `(row+k, col+l)`.
2. `connected_component_tiles` (`refine.py:91`): tile là node, ô chiếm nhiều tile là cạnh → tìm component liên thông.
3. `generate_rectangle_tiling` (`refine.py:183`): ép mỗi component thành hình chữ nhật.
4. `generate_html_payload` (`refine.py:351`): xuất HTML `colspan`/`rowspan` **bảo đảm well-formed**.

Bất biến rút ra, dùng được **không cần model**: *mọi tile trong lưới `n_row × n_col` phải được đúng một ô phủ, và mọi vùng gộp phải là hình chữ nhật.*

### C. Metric TEDS — `eval/tedsmetric.py`
Tree-Edit-Distance Similarity trên cây HTML bảng (APTED), có chế độ `structure_only` (bỏ qua nội dung, chỉ chấm cấu trúc). Deps: `apted`, `distance`, `lxml` — đều nhẹ, thuần Python. `rename()` phạt 1.0 khi lệch `tag`/`colspan`/`rowspan`, phạt Levenshtein chuẩn hoá khi lệch nội dung ô.

### D. `LAYOUT_NMS_PAIRS` — NMS theo cặp lớp + ưu tiên
`configs/conf_dd_one.yaml`, service `AnnotationNmsService` (`pipe/common.py:459`).

Bảng khai báo: `COMBINATIONS` (cặp lớp) × `PRIORITY` (giữ lớp nào) × `THRESHOLDS` (ngưỡng riêng từng cặp). Ví dụ `(table, text) → giữ table, ngưỡng 0.01`; `(figure, caption) → giữ figure, 0.001`. Giải quyết đúng lớp xung đột "block text bị phát hiện nằm trong bảng".

Giá trị nằm ở **hình dạng config khai báo**, không ở model.

### E. `match_anns_by_intersection` — IoA có trọng số
`packages/dd_core/src/dd_core/mapper/match.py:38`

Nhận xét cốt lõi (docstring, `match.py:70-78`): khi một child cắt N parent, tổng IoA = 1 nên **mỗi IoA co lại ~1/N** → ngưỡng tuyệt đối mất ổn định. `use_weighted_intersections=True` nhân IoA với số lần cắt để hiệu chỉnh. `max_parent_only=True` cho gán độc quyền (parent IoA cao nhất).

Hàm numpy thuần, ~40 dòng, port sang repo nào cũng được.

### F. `tile_tables_with_items_per_table` — kéo giãn hàng/cột phủ kín bảng
`pipe/segment.py:399`

Kéo hàng theo chiều dọc, cột theo chiều ngang cho tới khi **mọi điểm trong bảng thuộc về một hàng và một cột**. Hai luật: `left` (mép trên hàng kéo lên tới mép dưới hàng trên) và `equal` (cả hai mép kéo tới giữa khe). Hệ quả: không còn text rơi vào khe giữa các ô mà không được gán.

---

## 3. Áp dụng cho `doc-parser`

### Khoảng trống hiện tại (đọc từ `scripts/quality_gates.py`, `scripts/parse_document.py`)

Toàn bộ gate hiện tại đo **một câu hỏi duy nhất: "chữ còn không?"** — `text_recall`, `high_value_recall`, `page_absent`, `content_dead_pages`. Ba thứ **chưa bao giờ được đo**:

1. **Cấu trúc bảng** — README nêu đích danh các chế độ hỏng ("merges headers", "24 empty separators", "borderless 0/3") nhưng không flag nào bắt được. `PANDAS_NOISE` chỉ dò `NaN`/`Unnamed:` và chỉ chạy cho anydoc/markitdown (`parse_document.py:322-324`). Một bảng bị Docling trộn hết header vẫn qua sạch mọi gate nếu chữ còn đủ.
2. **Thứ tự đọc** — recall là phép đếm bag-of-words. Một trang 2 cột bị engine đọc đan xen đạt `text_recall = 1.000`.
3. **Định lượng bảng để định tuyến** — `docs/measurement-driven-upgrade-playbook.md` yêu cầu "đo trước khi đổi ngưỡng", nhưng ranh giới T2↔T3 ("khi cần giữ colspan/rowspan thật") hiện là **phán đoán bằng mắt**, không có số.

### Khuyến nghị, xếp theo giá trị/chi phí

**#1 — Metric TEDS-structure (GIÁ TRỊ CAO)**
Cổng đo còn thiếu, không phải cổng chặn. Cách rẻ nhất:
- Reference: `PyMuPDF page.find_tables()` trên PDF có text layer + bảng có viền → HTML.
- Hypothesis: bảng trong markdown output → HTML.
- `TEDS(structure_only=True)` → một con số.

Dùng để: (a) chứng minh/bác bỏ các tuyên bố bảng trong README bằng số; (b) đặt ngưỡng T2↔T3 **có đo đạc**; (c) làm metric hồi quy trong `run_regression.py`.
Chi phí: ~150 LOC + 3 dep nhỏ. Chỉ chạy khi đo, không nằm trên đường parse nóng.
Cảnh báo: `find_tables()` chỉ làm được bảng có viền → reference chỉ phủ tập con. Không thay được đánh giá thủ công cho bảng không viền.

**#2 — Flag `TABLE_STRUCTURE_BROKEN` (GIÁ TRỊ CAO, RẺ)**
Lấy bất biến từ mục B, áp thẳng lên markdown output, **không cần model**:
- mọi hàng cùng số cột;
- không có hàng toàn rỗng ngoài separator;
- không có cột toàn rỗng;
- hàng header không rỗng;
- số hàng ≥ 2.

Bắt đúng "24 empty separators" và "merges headers". ~60 LOC, 0 dep, chạy được cho mọi engine (hiện `PANDAS_NOISE` chỉ chạy 2 engine).
**Quy tắc bắt buộc:** đo trên corpus trước khi cho vào tập chặn index — theo playbook. Ban đầu chỉ để audit.

**#3 — Gate thứ tự đọc (GIÁ TRỊ TRUNG BÌNH, đo trước)**
Chạy `order_blocks` trên block của text layer → dãy tham chiếu; so với thứ tự token trong markdown bằng Kendall tau hoặc số cặp nghịch thế. Lớp gate hoàn toàn mới ("có đúng chỗ không") bên cạnh lớp hiện có ("có còn không").
Rủi ro: engine hợp lệ vẫn reflow (Docling gộp đoạn); dễ báo động giả. **Phải đo tỉ lệ dương tính giả trên corpus trước.** Không đưa vào tập chặn.

**Không lấy:** registry/dataflow/pipeline machinery (YAGNI — luận điểm của doc-parser chính là *không* làm framework nặng); model Detectron2/TATR (Docling + MinerU đã tốt hơn); doctr OCR (chính field-notes của doc-parser đã đo Vision/Tesseract/MinerU-VLM thắng trên tiếng Việt).

---

## 4. Áp dụng cho `pdf-translate-layout`

### Khoảng trống hiện tại

**Thứ tự đọc** — `scripts/extract_group.py:921-940`:
```python
# 2 cột nếu có gutter rõ
left_col  = [r for r in horiz if (r.bbox[0]+r.bbox[2])/2 <  pw/2]
right_col = [r for r in horiz if (r.bbox[0]+r.bbox[2])/2 >= pw/2]
two_col = len(horiz)>=6 and len(left)>=2 and len(right)>=2 and (rmin-lmax) > 0.06*pw
# ngược lại:
ordered = sorted(horiz, key=lambda r: (round(r.bbox[1]/4), r.bbox[0]))
```
Hỏng ở: **3+ cột** (rơi về band-sort y/4 → đan xen); **tiêu đề/bảng chạy hết bề ngang trên thân 2 cột** (tâm rơi về một phía, bị xếp vào cột đó); **sidebar/callout hẹp hơn nửa trang**; **gutter mờ** (< 6% pw).

**Ảnh hưởng thực tế — cần nói chính xác:** `reading_index` **không** quyết định vị trí vẽ (vẽ theo bbox). Nó quyết định thứ tự region đưa vào `build_context_graph.py` và `translate_prep.py` → tức là **ngữ cảnh LLM nhận được**. Thứ tự sai = ngữ cảnh sai = bản dịch kém, **không phải** layout lệch. Đây là lỗi chất lượng dịch, không phải lỗi trung thực layout.

**Bảng** — `extract_group.py:233` dùng `page.find_tables()` → đúng như README ghi nhận: chỉ bảng có viền.

### Khuyến nghị, xếp theo giá trị/chi phí

**#1 — Thay heuristic 2-cột bằng `order_blocks` (GIÁ TRỊ CAO)**
Port mục A. ~120 LOC numpy thuần, **không thêm dependency** (đã có PyMuPDF; chỉ cần IoA — vài dòng numpy). Xử lý được N cột, tiêu đề toàn ngang, sidebar, cột lồng nhau.
Tham số bắt đầu từ giá trị của deepdoctection (`starting_point_tolerance=0.005`, `broken_line_tolerance=0.003`, `height_tolerance=2.0`) nhưng **phải hiệu chỉnh lại trên corpus V16/V5/HV48100** — chúng được tune cho DocLayNet, không phải cho datasheet kỹ thuật.
Kiểm chứng: `reading_index` chỉ vào translation context, nên regression test là so **thứ tự region**, không phải so pixel. Rẻ.

**#2 — Kéo giãn/tiling ô bảng (GIÁ TRỊ TRUNG BÌNH)**
Port mục F. Ô từ `find_tables()` để lại khe; text rơi vào khe không được gán ô nào → hoặc mất context, hoặc `container` sai → wrap sai. Tiling `equal` đóng khe. Cộng hưởng tốt với `column_consensus` (`extract_group.py:399`) đã có.

**#3 — IoA có trọng số cho gán line→ô/container (TRUNG BÌNH-THẤP)**
Port mục E. Một line cắt nhiều ô (do `fragment_row` / `split_multicol_rows`) chịu đúng vấn đề IoA co lại mà docstring `match.py` mô tả. Hàm nhỏ, thay tại chỗ.

**#4 — Config NMS theo cặp cho xung đột `region_type` (THẤP)**
Chuỗi `elif` phân loại region (`extract_group.py:905-919`) đang trộn thứ tự ưu tiên vào luồng điều khiển. Bảng khai báo kiểu `LAYOUT_NMS_PAIRS` tách ưu tiên khỏi logic → dễ chỉnh, dễ đo. Refactor thuần, không đổi hành vi.

**KHÔNG làm: nhúng model bảng không viền của deepdoctection.**
Sẽ kéo torch + Detectron2/TATR + ~1 GB weights vào một repo hiện thuần PyMuPDF, không model, AGPL. Phá thiết kế.

**Đường rẻ hơn cho bảng không viền — nối hai repo:** doc-parser đã đo Docling **3/3** và MinerU **3/3** trên bảng spec không viền. Nếu pdf-translate-layout thật sự cần bảng không viền, hướng đi là **gọi T2/T3 của doc-parser như một oracle hình học ô bảng**, không phải nhúng deepdoctection.
⚠️ **Chưa kiểm chứng:** Docling `DoclingDocument` có mang provenance bbox cho ô bảng; MinerU trả HTML nhưng bbox ở mức **vùng bảng**, chưa rõ có bbox từng ô ở toạ độ trang không. Phải xác minh trước khi lên kế hoạch.

---

## 5. Giấy phép

| Repo | License | Nhận Apache-2.0? |
|---|---|---|
| deepdoctection | Apache-2.0 | — |
| doc-parser | MIT | ✅ Được. Giữ nguyên copyright header + kèm bản Apache-2.0 cho phần code sao chép. |
| pdf-translate-layout | AGPL-3.0 | ✅ Được, một chiều (AGPLv3 hấp thụ được Apache-2.0). |

Nếu **viết lại** thuật toán từ mô tả (không copy-paste) thì không ràng buộc gì — nhưng ghi nguồn vẫn nên làm.

---

## 6. Bảng quyết định gộp

| Hạng mục | doc-parser | pdf-translate-layout | Chi phí |
|---|---|---|---|
| Metric TEDS-structure | **Làm — ưu tiên 1** | không | ~150 LOC, 3 dep nhỏ |
| Bất biến cấu trúc bảng → flag | **Làm — ưu tiên 2** | cân nhắc (validate lưới trước fit) | ~60 LOC, 0 dep |
| `order_blocks` (thứ tự đọc theo cột) | gate, sau khi đo | **Làm — ưu tiên 1** | ~120 LOC, 0 dep |
| Tiling hàng/cột bảng | không | **Làm — ưu tiên 2** | ~80 LOC, 0 dep |
| IoA có trọng số | không | Làm — ưu tiên 3 | ~40 LOC |
| Config NMS theo cặp | N/A (không có layout model) | Refactor — ưu tiên 4 | thuần refactor |
| deepdoctection làm engine/dep | **Không** | **Không** | — |
| Model Detectron2/TATR/doctr | **Không** | **Không** | — |
| Pipeline/registry/dataflow framework | **Không** (YAGNI) | **Không** | — |

---

## Câu hỏi chưa giải quyết

1. **Ưu tiên nào?** doc-parser (đo lường bảng) hay pdf-translate-layout (thứ tự đọc) trước — hay cả hai song song?
2. **Corpus đo TEDS.** `DOCPARSE_CORPUS_ROOT` hiện trỏ vào đâu, và trong đó có bao nhiêu PDF **có viền bảng + có text layer** để dựng reference bằng `find_tables()`? Dưới ~20 file thì con số TEDS chưa đủ để đặt ngưỡng.
3. **Bảng không viền của pdf-translate-layout có phải yêu cầu thật không**, hay giới hạn "bordered tables only" đang chấp nhận được? Quyết định này chi phối toàn bộ mục 4-#4.
4. **Docling/MinerU có trả bbox từng ô bảng ở toạ độ trang không?** Cần xác minh trước khi coi doc-parser là oracle hình học cho pdf-translate-layout.
5. Ngưỡng `order_blocks` cần hiệu chỉnh lại trên corpus nào — V16 + V5 + HV48100 đã đủ đại diện chưa?
