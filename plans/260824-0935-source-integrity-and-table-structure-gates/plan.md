# Plan — Gate toàn vẹn nguồn & cấu trúc bảng

**Trạng thái:** Phase 01 ✅ · Phase 02 ✅ (đổi chỉ báo) · Phase 03 ⛔ chặn bởi engine lock của PTL
**Phạm vi đã chốt:** 1a (preflight classifier) + gate cấu trúc bảng. **Không** gồm 1b (đường trích xuất vector-outline).
**Cơ sở:** [verification report](../reports/corpus-evidence-verification-260824-0903-deepdoctection-eval-corrections-report.md) · [feasibility report](../reports/feasibility-verification-260824-0935-ocr-into-pdf-translate-preflight-report.md)

## Vì sao

Ba lớp lỗi đo được trên production, **không lớp nào bị phát hiện hiện nay**:

| Lỗi | Bằng chứng | Repo |
|---|---|---|
| Mojibake ToUnicode | `PI STATION261 · Hướng dẫn sử dụng` — 13 324 token rác, `text_recall: 0.986`, `quality_flags: []`. 2 job đã sửa tay. | cả hai |
| Cấu trúc bảng hỏng | 130/186 bảng (70 %) ragged trên corpus T0; 3 user manual tệ nhất mang `flags: []` | doc-parser |
| Nguồn không dịch được | 7/80 job MANUAL_DTP; 59/61 trang là vector-outline chứ không phải scan | PTL |

## Phases

| # | Phase | Repo | Phụ thuộc |
|---|---|---|---|
| 01 | [Gate mojibake](phase-01-mojibake-gate.md) | doc-parser | — |
| 02 | [Gate cấu trúc bảng](phase-02-table-structure-gate.md) | doc-parser | sau 01 (cùng file) |
| 03 | [Preflight source classifier](phase-03-ptl-source-classifier.md) | pdf-translate-layout | dùng lại logic của 01 |

01 và 02 sửa cùng bộ file (`quality_gates.py`, `parse_document.py`, `test_quality_gates.py`) → **chạy tuần tự**, không song song.
03 ở repo khác → cần clone `pdf-translate-layout` riêng; có thể chạy song song với 01/02.

## Ngưỡng (đã đo, không đoán)

| Ngưỡng | Giá trị | Bằng chứng |
|---|---|---|
| `READABLE_RATIO_MIN` | **0.02** | mojibake 0,105 % · thấp nhất hợp lệ 7,784 % → biên 74×, chọn giữa cho margin 19× hai phía |
| `MIN_READABLE_TOKENS` | **200** | dưới ngưỡng này tỉ lệ không ổn định; cũng là guard tự nhiên cho tài liệu thuần CJK |
| ~~`TABLE_OFF_MODAL_MAX`~~ | 0.25 | ⚠️ **chỉ báo chết** — trung vị thật 0.000, chỉ 2/186 vượt. Giữ làm lưới an toàn. |
| `TABLE_EMPTY_CELL_MAX` | **0.50** | thay thế: anydoc 0.12–0.18 ô rỗng vs docling 0.00–0.02 cùng file |
| `TABLE_DEFECT_SHARE` | **0.25** | Storytelling P1 0.389 bị cờ · mọi thứ khác ≤0.091 |

Đo CJK: 3 tài liệu CJK-nặng (14,9–15,2 % body) đạt ratio 20,3–22,9 % — **cao hơn trung bình** vì song ngữ. Không cần nhánh riêng theo script.

## Acceptance criteria

1. `test_quality_gates.py` pass, có case mới cho cả hai gate (gồm case biên quanh ngưỡng).
2. Chạy lại 37 tài liệu T0 corpus: `MOJIBAKE_SUSPECT` bắt đúng `PI STATION261 · Hướng dẫn sử dụng`, **0 dương tính giả**.
3. `TABLE_STRUCTURE_BROKEN` bắt ≥3 user manual đã biết; **không** bắt output docling của cùng file đó.
4. `run_regression.py` không đổi kết quả 3 fixture cũ.
5. Hai cờ mới vào `quality_flags` frontmatter; **chỉ audit, chưa chặn index** (theo playbook: đo trước, chặn sau).
6. Phase 03: 7 job MANUAL_DTP được phân loại đúng TRUE_SCAN (2 trang) vs OUTLINED_VECTOR (59 trang).

## Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Ngưỡng mojibake đặt trên **1 ca dương tính** | Chỉ audit. Cần thêm mẫu trước khi chặn index. |
| Ngưỡng bảng đo trên **2 tài liệu** | Chỉ audit. Phase 02 có bước calibrate rộng hơn trước khi chốt. |
| Bảng markdown lồng nhau / cell có `\|` escape làm sai bộ đếm cột | Test case riêng; bỏ qua bảng <2 hàng body. |
| Đổi `quality_flags` phá downstream đang đọc frontmatter | Chỉ **thêm** cờ, không đổi/bỏ cờ cũ. |

## Ngoài phạm vi

- **1b** — trích xuất vector-outline (rasterize → OCR → suy style → paint). 15 tài liệu/71 trang. Người dùng xác nhận **xin được bản gốc từ Pytes** → ưu tiên đường vận hành trước.
- TEDS, `order_blocks` — hoãn, xem verification report.
- Sửa `figure_caption confidence=0.7` hardcode làm loãng log PTL (1218/1796 issue) — ghi nhận, không thuộc plan này.
