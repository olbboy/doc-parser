# Phase 03 — Preflight source classifier (pdf-translate-layout)

**Repo:** `olbboy/pdf-translate-layout` (AGPL-3.0) — **không** nằm trong workspace này; cần clone riêng.
**Phụ thuộc:** dùng lại `readable_ratio` của Phase 01 (port sang, không import chéo repo)

## Vấn đề

7/80 job dừng ở `MANUAL_DTP` với thông điệp không phân biệt được hai tình huống có tính khả thi **trái ngược nhau**:

| Trang | Mã hiện tại | Thực chất | Dịch được không |
|---|---|---|---|
| 2 | `SCANNED_PAGE` | ảnh raster | **Không bao giờ** — `fit_paint.py` dùng `PDF_REDACT_IMAGE_NONE` ở cả 4 lần `apply_redactions`; không có `insert_image`/`inpaint`. Chữ Việt sẽ đè lên chữ Anh trong ảnh. |
| 59 | `TEXT_AS_VECTOR_SUSPECT` | glyph convert-to-outline | Về nguyên tắc có (line-art redaction xoá được) — nhưng cần năng lực mới = **1b, ngoài phạm vi** |

Người vận hành hiện không có cách biết nên **bỏ cuộc** hay **đi xin bản gốc**.

Thêm: preflight không có kiểm mojibake, dù 2 job đã phải sửa ToUnicode tay
(`pi_station_261_ex_user_manual_-_tounicode_repaired`, `luxpower_guide_for_v5_-_tounicode_repaired`).

## Yêu cầu

Biến `MANUAL_DTP` câm thành **chỉ dẫn hành động**. Không thêm năng lực trích xuất nào.

## Files

| File | Thay đổi |
|---|---|
| `scripts/preflight.py` | tách `TEXT_AS_VECTOR_SUSPECT` → `OUTLINED_VECTOR_TEXT`; thêm `MOJIBAKE_TOUNICODE`; thêm gợi ý hành động vào `detail` |
| `scripts/_common.py` | thêm `readable_ratio` (port từ Phase 01) |

## Các bước

1. **Siết phân loại vector.** Hiện tại: `n_chars < 5 and not scanned and len(drawings) > 40` — bắt nhầm trang sơ đồ thuần. Thêm điều kiện tỉ lệ path cỡ glyph:
   ```
   glyph_like = [d for d in drawings if d.rect.width < 20 and d.rect.height < 20]
   outlined   = len(glyph_like) / max(len(drawings), 1) >= 0.8
   ```
   Đo trên ca thật `V16 quick guide final-20251204-Q.pdf`: trang 1 **105/113 = 93 %**, trang 2 **385/385 = 100 %**, trang 3 **2373/2373 = 100 %**. Ngưỡng 0,8 an toàn.
   - `outlined` → `OUTLINED_VECTOR_TEXT` (P1): *"chữ đã convert-to-outline — xin bản gốc từ nhà cung cấp"*
   - còn lại → giữ `TEXT_AS_VECTOR_SUSPECT` (trang sơ đồ thuần)

2. **Dò sibling editable.** Khi có `OUTLINED_VECTOR_TEXT`, quét thư mục cha (đệ quy 2 cấp) tìm file cùng gốc tên có text layer:
   - chuẩn hoá tên: bỏ hậu tố `-Q`/`Q`, chuỗi số ≥6 chữ số, `(n)`
   - **loại** file `*_VI.pdf` và mọi thứ nằm dưới `translation/jobs/` (là output, không phải nguồn)
   - trúng → issue P2 `EDITABLE_SOURCE_FOUND` kèm đường dẫn
   Đo: trúng **1/6** file bị chặn (`V16 user manual-PYTES 1.0 20251204(1).pdf`). Chi phí bằng 0 khi trúng.

3. **Kiểm mojibake.** Với trang có text layer, chạy `readable_ratio` trên text trích được. `< 0.02` → `MOJIBAKE_TOUNICODE` (P0 — chặn): *"ToUnicode CMap hỏng, sửa nguồn trước khi dịch"*.
   P0 vì dịch tiếp là lãng phí toàn bộ chi phí LLM.

4. **`SCANNED_PAGE` giữ nguyên mã**, đổi `detail` thành dứt khoát: *"ảnh raster — pipeline không sửa pixel ảnh theo thiết kế; MANUAL_DTP là đúng"*.

## Validation

Chạy lại preflight trên 7 job MANUAL_DTP + 2 job `*_tounicode_repaired`:

| Kỳ vọng | Số lượng |
|---|---|
| `OUTLINED_VECTOR_TEXT` | 59 trang / 5 tài liệu |
| `SCANNED_PAGE` | 2 trang / 2 tài liệu |
| `EDITABLE_SOURCE_FOUND` | 1 tài liệu |
| `MOJIBAKE_TOUNICODE` | 2 tài liệu (bản *chưa* repair) |

Không job nào đang `RELEASED` được đổi trạng thái (kiểm hồi quy trên 66 job).

## Rủi ro & rollback

- Ngưỡng glyph 0,8 đo trên **1 tài liệu**. → calibrate trên cả 15 tài liệu outline trong corpus trước khi chốt.
- `MOJIBAKE_TOUNICODE` là P0 (chặn). Rủi ro dương tính giả cao hơn Phase 01. → cân nhắc P1 ở lần đầu, nâng P0 sau khi có thêm mẫu.
- Dò sibling đọc ngoài thư mục job → chỉ đọc, không ghi; giới hạn 2 cấp; bỏ qua lỗi quyền lặng lẽ.
- Rollback: các mã mới đều là **thêm**; hạ về `TEXT_AS_VECTOR_SUSPECT` là đổi một nhánh `if`.
