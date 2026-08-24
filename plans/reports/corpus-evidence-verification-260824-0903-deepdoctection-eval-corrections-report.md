# Verification pass — đo corpus thật, đính chính báo cáo deepdoctection

Ngày: 2026-08-24 · Supersedes phần khuyến nghị của `tech-eval-260824-0851-deepdoctection-knowledge-transfer-report.md`
Bằng chứng: 110 PDF corpus (BLVera-Pytes-Drive + pytes-training-materials) · 80 job dịch production · 5 output doc-parser production · 1 lần chạy Docling thật.

## Đính chính (điều quan trọng nhất)

Báo cáo trước **ưu tiên hoàn toàn từ đọc code, chưa hề nhìn cái gì thực sự hỏng.** Đo xong, **2/6 khuyến nghị hàng đầu bị lật**, và khuyến nghị số một thật sự **không cần deepdoctection**.

| Khuyến nghị cũ | Trạng thái sau khi đo |
|---|---|
| doc-parser #1: metric TEDS | **Hạ bậc.** Reference `find_tables()` không phải ground truth, và về cấu trúc **không phủ được** 53/110 tài liệu bảng-không-viền — nơi rủi ro thật nằm. |
| pdf-translate-layout #1: port `order_blocks` | **Hạ bậc mạnh.** Chỉ 14/516 trang (2,7%) mà luật nửa-trang sai. 0/80 job production có issue code liên quan thứ tự đọc. |
| doc-parser #2: gate cấu trúc bảng | **Lên #1.** Bằng chứng production xác nhận (bên dưới). |
| — (chưa từng đề xuất) | **Mới, #1 tổng thể:** nối OCR của doc-parser vào preflight của pdf-translate-layout. |

---

## Trả lời 5 câu hỏi

### Q1 — Ưu tiên repo/hạng mục nào? → Trả lời bằng dữ liệu production, không phải suy luận từ code

**80 job dịch thật:** 66 RELEASED · 7 MANUAL_DTP · 5 TRANSLATED · 1 NEEDS_REVIEW · 1 REVOKED → tỉ lệ phát hành 82,5 %. **Cả hai pipeline đang chạy được.** Không có khủng hoảng nào.

**Cả 7 job MANUAL_DTP chết ở `preflight`** — trước cả stage extract:

| Job | Nguyên nhân |
|---|---|
| `pi_lv1_20260410-q`, `pi_lv1_user_manual`, `delaration_of_conformity-v16_lite`, `e-box_48100r_guide20251021` … | `SCANNED_PAGE` — trang chỉ có ảnh scan, không text layer |
| `v16_quick_guide_final-20251204` (×2), `v16_base` | `TEXT_AS_VECTOR_SUSPECT` — nhiều vector, không text layer |

→ **Thất bại số một của pdf-translate-layout là KHÔNG CÓ OCR.** 8,75 % tài liệu không bao giờ vào được pipeline. Trùng khớp với probe doc-parser: 11/110 (10 %) corpus cần OCR.

**Top issue P0/P1 trên 80 job** (không có mã nào về thứ tự đọc, không mã nào về bảng-không-viền):

```
95 NUMBER_DRIFT          60 G4_OUT_OF_CONTAINER   37 TRANSLATION_IDENTICAL
35 TARGET_LANG_SUSPECT   22 G4_COLLISION          18 G3_TARGET_NOT_FOUND
 8 G6_DIFF_OUTSIDE_MASK   7 G4_TABLE_RULE_CROSS
```
Hai cụm chi phối: **trung thực bản dịch** (NUMBER_DRIFT / IDENTICAL / LANG_SUSPECT ≈ 167) và **hình học fit/paint** (G3/G4 ≈ 100+). Không cụm nào deepdoctection giải được.

> ⚠️ Đọc cho đúng: vắng mã lỗi thứ-tự-đọc **không phải** bằng chứng không có vấn đề — hệ thống không đo thứ tự đọc. Thứ tự sai sinh ra bản dịch *hợp lý nhưng sai ngữ cảnh*, chỉ người review bắt được. Đây là điểm mù có thật, nhưng **không phải** nút thắt.

> 📌 Nhiễu cần biết: `REGION_CONFIDENCE_LOW` = 1796 (top volume) nhưng **1218 trong đó là `figure_caption confidence=0.7`** — một hằng số hardcode ở `extract_group.py:915`, không phải tín hiệu bất định. Mã lỗi này đang làm loãng log.

**Bằng chứng production doc-parser** — `Storytelling with Data - P1.md`:
```yaml
parser: anydoc   parser_tier: T0   parser_reason: "PDF text layer, bố cục đơn giản"
text_recall: 0.996   quality_flags: []          # ← sạch mọi gate
```
Nhưng: **72 bảng, 59 ragged (82 %), 7 cột rỗng.** Soi vào thì chúng **không phải bảng** — anydoc băm biểu đồ/infographic thành lưới pipe giả:
```
||Survey Results||||100%|Non Profit Support||
|19%|11% 5% 40%||Bored Not great OK Kind of interested Excited||90% 80% 70% ...
```
→ **doc-parser cấp giấy chứng nhận sạch cho rác.** Đây không phải chuyện "giữ colspan" — đây là **engine bịa ra cấu trúc bảng từ nội dung phi bảng**, rồi rác đó vào index RAG trông như dữ liệu có thẩm quyền. `P2.md` 23/34 ragged, cùng dạng.

**Kết luận Q1 — thứ tự ưu tiên đã đảo:**

| # | Hành động | Repo | Bằng chứng | Cần deepdoctection? |
|---|---|---|---|---|
| 1 | Nối OCR doc-parser vào preflight pdf-translate-layout | PTL | 7/80 job chết ở preflight | **Không** |
| 2 | Gate hợp lệ cấu trúc bảng | doc-parser | 59/72 bảng hỏng, `quality_flags: []` | Chỉ mượn *bất biến* |
| 3 | (Tuỳ) TEDS thu hẹp cho bảng có viền | doc-parser | 49 bảng / 26 doc | Có |
| 4 | (Hoãn) `order_blocks` | PTL | 2,7 % trang | Có |

### Q2 — Corpus đo TEDS? → **49 bảng chấm được (≥3×3) trong 26 tài liệu có text layer**, trên 110 PDF

Đủ số lượng làm công cụ hồi quy. **Nhưng có lỗi phương pháp mà báo cáo trước bỏ sót:**
1. `find_tables(strategy="lines_strict")` **không phải ground truth** — nó cũng là heuristic. TEDS so với nó = "mức đồng thuận với PyMuPDF", không phải độ chính xác.
2. Nó đọc vạch vẽ thật → **về cấu trúc không thể** dựng reference cho bảng không viền. Mà 53/110 tài liệu (48 %) mang cờ `BORDERLESS_SPEC_TABLE`.

→ TEDS sẽ đo đúng 26 tài liệu **không** rủi ro, bỏ trắng 53 tài liệu có rủi ro. **Không phải công cụ đo đầu tiên.** Gate bất biến cấu trúc thì **không cần reference nào cả** — chạy được trên cả hai loại.

### Q3 — Bảng không viền có phải yêu cầu thật? → **Có với doc-parser (và đã được xử lý). Không phải nút thắt với pdf-translate-layout.**

Đo bằng chính probe đã hiệu chỉnh của doc-parser trên 110 PDF:
```
TIER   T0 anydoc 37  |  T2 docling 62  |  T2 docling+ocr 11  |  T1 0  |  T3 0
FLAGS  BORDERLESS_SPEC_TABLE 53  ·  NEEDS_OCR 11  ·  DENSE_TABLE_GRID 9  ·  LAYOUT_RISK_MEDIUM 5
```
- **53/110 (48 %)** mang bảng spec không viền → có thật, và **nhiều**.
- Router **đã** đẩy toàn bộ sang T2/Docling (đo 3/3 trên ca này). **doc-parser đã giải quyết xong.**
- **T3 không bao giờ kích hoạt.** Nên tiền đề "cần đo để chỉnh ranh giới T2↔T3" trong báo cáo trước **không phải vấn đề đang tồn tại**.
- pdf-translate-layout: 0 mã lỗi bảng-không-viền trên 80 job; mã bảng duy nhất là `TABLE_ROW_SPLIT` (27, P2).

> 🗑 **Rút lại:** con số "210 trang bảng không viền" ở lần đo đầu là **nhiễu**. `strategy="text"` băm prose thành lưới giả — đoạn văn thành "19r×4c", dòng địa chỉ thành "64r×11c". Đã kiểm mẫu và loại bỏ.

### Q4 — Docling/MinerU có bbox từng ô? → **Docling: CÓ, đã kiểm chứng chạy thật**

Chạy Docling 2.119.0 trên chính fixture bảng **không viền** (`testdata/regression/datasheet.pdf`):
```
TableItem: 26r x 2c, cells=47      table prov: page 2, bbox [33.3,118.0,563.0,758.1]
cell r0-1 c0-1 rs=1 cs=1 hdr=True  bbox=[38.2,88.9,68.0,98.5]  txt='Mode'
cells WITH bbox: 47/47
```
Có đủ: `bbox` mọi ô · `start/end_row_offset_idx` · `start/end_col_offset_idx` · `row_span` · `col_span` · `column_header` · `prov.page_no`.

**Hai cạm bẫy tích hợp đã đo được:**
1. **Gốc toạ độ lệch nhau.** `TableItem.prov[].bbox.coord_origin = BOTTOMLEFT`, còn `TableCell.bbox.coord_origin = TOPLEFT`. Page height 841.89. Phải lật: `y_top = 841.89 − y_bottom`. Không lật thì bbox bảng nằm sai chỗ so với ô của chính nó. PyMuPDF dùng TOPLEFT → **bbox ô dùng thẳng được, bbox bảng thì không.**
2. **Lưới thiếu ô.** 26×2 = 52 tile, chỉ 47 ô → **5 lỗ, 0 chồng lấn**, đúng tại cột 1 các hàng {1, 12, 15, 19, 24} — là các hàng tiêu đề mục lẽ ra phải `colspan=2`. Docling **không mã hoá ô spanning**. Chính đây là thứ bất biến tiling của `refine.py` bắt được.

**MinerU: chưa test** (cần dựng `mineru-api`). Vẫn mở.

### Q5 — Corpus hiệu chỉnh `order_blocks`? → **Quá mỏng để chỉnh. Đừng chỉnh.**

Bộ dò cột độc lập (chiếu khoảng-x, tìm thung lũng trắng — **không** tái dùng luật nửa-trang đang bị đánh giá), 516 trang:

| | Số trang | Số tài liệu |
|---|---|---|
| 2 cột | 19 | 13 |
| **3+ cột** (luật nửa-trang không biểu diễn nổi) | **4** | 3 |
| **Khối toàn-ngang trên thân nhiều cột** (luật nửa-trang xếp sai) | **10** | 8 |
| → **Tổng mặt lỗi thật** | **14 / 516 = 2,7 %** | ~9 |

14 trang không đủ để hiệu chỉnh 3 ngưỡng (`starting_point_tolerance`, `broken_line_tolerance`, `height_tolerance`) — sẽ overfit. Ngưỡng gốc của deepdoctection tune cho DocLayNet, không cho datasheet kỹ thuật.

> Lần đo đầu ra "5 trang / 3 tài liệu" là **circular** — dùng đúng heuristic nửa-trang đang bị đánh giá làm bộ dò. Đã thay bằng bộ dò độc lập; con số thật cao hơn ~3× nhưng vẫn nhỏ.

---

## Điểm mù mà 5 câu hỏi cũ đã bỏ sót

`/essential-questions` (MODE=decide) lộ ra 4 câu chưa từng hỏi. Ba câu đầu đã tự trả lời được:

| Câu hỏi | Trả lời |
|---|---|
| ★★★ **Cái gì thực sự hỏng trong vận hành?** | 7/80 job chết vì thiếu text layer; 59/72 bảng hỏng lọt gate sạch. **Không câu nào trong 5 câu cũ hỏi điều này.** |
| ★★★ **Không làm gì thì sao?** | 82,5 % release. Cả hai pipeline chạy được. Đây là **cải tiến, không phải cứu hoả** — chọn đúng 1-2 việc, đừng làm cả 6. |
| ★★ **Corpus Pytes có đại diện cho cả hai repo không?** | Có — 80 job dịch chính là tài liệu Pytes. Giả định trước đó nay đã kiểm chứng. |
| ★★ **Tôi có bị dính vào khung deepdoctection vì đã bỏ công nghiên cứu nó?** | **Có.** Hai hành động giá trị nhất (#1 OCR, #2 gate cấu trúc) cần **zero** deepdoctection. Framework chỉ đóng góp *bất biến* cho #2. |

Câu `Purpose` (8 Elements) vẫn mở — xem cuối.

---

## Điều gì còn đứng vững từ báo cáo trước

Không thay đổi: **không** dùng deepdoctection làm engine hay dependency; giấy phép Apache-2.0 tương thích cả hai repo; `reading_index` chỉ vào ngữ cảnh dịch chứ không vào vị trí vẽ (**đã xác minh** — chỉ xuất hiện ở `build_context_graph.py` và `translate_prep.py`, không có ở `fit_paint.py`); bất biến tiling của `refine.py` là ý tưởng đúng và nay có bằng chứng production hậu thuẫn.

---

## Bổ sung sau khi người dùng chốt hướng — hai phát hiện mới

Người dùng chọn **"cả hai, làm tuần tự"** và xác nhận **tài liệu scan đến thường xuyên**. Đo thêm hai vòng thì lộ ra một lớp lỗi thứ ba, chưa từng nằm trong bất kỳ khuyến nghị nào.

### Phát hiện A — bảng hỏng lan rộng trên chính corpus kỹ thuật (không chỉ sách data-viz)

> ⛔ **PHÁT HIỆN A ĐÃ BỊ BÁC BỎ.** Con số 70 % dưới đây đến từ một script đo ad-hoc dùng
> `.strip("|")` tham lam, nuốt mất ô rỗng đầu/cuối hàng (`||Normal OFF||||` đếm 1 ô thay vì 5).
> Đo lại đúng ngữ nghĩa GFM: off-modal **trung vị 0.000**, chỉ **2/186** bảng vượt ngưỡng.
> Chỉ báo thật là **mật độ ô rỗng**, không phải số cột. Giữ đoạn này làm dấu vết điều tra;
> đừng trích số. Xem [implementation report](implementation-260824-0956-source-integrity-gates-phase-01-02-report.md)
> và [calibration report](calibration-260824-1022-table-gate-threshold-on-paired-engines-report.md).


Chạy doc-parser trên 37 tài liệu T0 của corpus Pytes:

```
tài liệu có bảng : 35 / 37        bảng tổng: 186
ragged           : 130  = 70 %    có cột rỗng: 11
```
Ba ca tệ nhất mang `quality_flags: []` — **sạch mọi gate**:

| Tài liệu | ragged/tổng | flags hiện có |
|---|---|---|
| `PI STATION261 · Hướng dẫn sử dụng` | 17/25 | `[]` |
| `V16 user manual-PYTES 1.0` | 10/16 | `[]` |
| `HV48100 · Hướng dẫn sử dụng` | 9/11 (2 cột rỗng) | `[]` |

Đây là **user manual** — đúng thứ đi vào knowledge base. Ca sách data-viz (59/72) không phải ngoại lệ; nó là biểu hiện đậm của vấn đề chung. Đóng câu hỏi mở #5 của báo cáo trước: tỉ lệ trên corpus kỹ thuật là **70 %**, không phải ca biên.

### Phát hiện B — mojibake ToUnicode: lỗi toàn phần, vô hình với cả hai pipeline ⭐

`PI STATION261 · Hướng dẫn sử dụng.md` chứa:
```
(XURSHDQ JHQHUDO *UHHFH …
```
Dịch ngược **shift +29** → `European general Greece`. Đây là **ToUnicode CMap hỏng** — PDF phát ra glyph index thay vì mã Unicode. Toàn bộ 13 324 token là rác.

doc-parser báo cáo về file này:
```yaml
text_recall: 0.986      quality_flags: []
```

**Vì sao gate mù theo thiết kế:** `text_recall` so output với *chính text layer của PDF*. Text layer đã hỏng → tham chiếu và giả thuyết hỏng giống hệt nhau → recall ≈ 1.0. Gate hỏi "engine có giữ được thứ text layer có không", **không bao giờ hỏi "thứ đó có đọc được không"**.

pdf-translate-layout cũng không bắt. Toàn bộ mã lỗi preflight sinh ra:
```
ARBITRARY_ANGLE_TEXT · DOMAIN_CONTEXT_MISSING · ENCRYPTED_OPENABLE · ENCRYPTED_PDF
SCANNED_PAGE · SIGNED_PDF · TEXT_AS_VECTOR_SUSPECT · VERTICAL_WMODE
```
Không có mục nào về ToUnicode/mojibake.

**Bằng chứng người dùng đã trả giá thủ công — hai lần:**
```
jobs/pi_station_261_ex_user_manual_-_tounicode_repaired__8205383e__20260808T041056
jobs/luxpower_guide_for_v5_-_tounicode_repaired__55939f7d__20260808T193426
```
Tên job tự nó là bằng chứng: nguồn phải được sửa tay trước khi dịch được.

**Phát hiện rẻ, biên độ tách rất rộng.** Tỉ lệ token trúng stopword (EN ∪ VI):

| Tài liệu | hit-rate |
|---|---|
| `PI STATION261 · Hướng dẫn sử dụng` (mojibake) | **0,105 %** |
| Kế tiếp thấp nhất (nameplate song ngữ, thấp hợp lệ) | 7,78 % |
| Tài liệu bình thường | 17–25 % |

Ngưỡng bất kỳ trong khoảng 1–5 % tách sạch. Một tỉ lệ, ~20 dòng, không dependency, dùng chung được cho **cả hai repo**.

Tần suất: **1/35 tài liệu T0** (≈3 %) trong corpus, cộng 2 job đã sửa tay. Hiếm — nhưng khi xảy ra là **mất trắng**, và hiện **không có gì bắt được**.

---

## Thứ tự ưu tiên cuối cùng (sau khi người dùng chốt: cả hai, tuần tự)

| # | Hành động | Repo | Bằng chứng production | deepdoctection? |
|---|---|---|---|---|
| **1** | Nối OCR doc-parser (Docling + `ocrmac:vi-VT`) vào preflight PTL | PTL | 7/80 job chết ở preflight; người dùng xác nhận scan đến thường xuyên | **Không** |
| **2** | Gate mojibake (tỉ lệ stopword) | **cả hai** | 2 job sửa tay; 13k token rác qua gate sạch | **Không** |
| **3** | Gate hợp lệ cấu trúc bảng | doc-parser | 130/186 (70 %) ragged; ca tệ nhất `flags: []` | Chỉ mượn *bất biến* `refine.py` |
| 4 | (Hoãn) TEDS thu hẹp cho bảng có viền | doc-parser | 49 bảng/26 doc; reference không phải ground truth | Có |
| 5 | (Hoãn) `order_blocks` | PTL | 2,7 % trang; 0 mã lỗi production | Có |

**Ba việc đầu — chiếm gần như toàn bộ giá trị đo được — cần zero code deepdoctection.** Đóng góp thật của framework thu về đúng một thứ: bất biến tiling ở hạng mục #3.

---

## Câu hỏi chưa giải quyết

1. **MinerU có bbox từng ô không** — chưa test, cần dựng `mineru-api`. (Docling đã xác nhận CÓ.)
2. Gate mojibake và gate bảng nên **chặn index hay chỉ audit** lúc đầu? Playbook nói đo trước → nghiêng audit, nhưng là quyết định chính sách.
3. Ngưỡng stopword: 1 %, 2 % hay 5 %? Biên độ tách rộng (0,105 % vs 7,78 %) nên chọn 2 % là an toàn — nhưng mới có **1 ca dương tính**, cần thêm mẫu trước khi chốt chặn.
4. Tài liệu **Trung/Nhật** trong corpus sẽ trúng thấp tự nhiên với stopword EN/VI — cần nhánh riêng theo script trước khi bật gate.
