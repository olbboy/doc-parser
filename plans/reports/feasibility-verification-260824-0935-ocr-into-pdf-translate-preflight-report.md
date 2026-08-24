# Verify khả thi trước khi lập plan — "nối OCR doc-parser vào preflight pdf-translate-layout"

Ngày: 2026-08-24 · Kết luận: **kế hoạch #1 như đã phát biểu là SAI về kiến trúc.** Phải tách đôi.

## Kết luận ngắn

| Giả định trong khuyến nghị #1 | Kiểm chứng |
|---|---|
| "Nút thắt là tài liệu scan" | ❌ **Sai.** 59/61 trang bị chặn (97 %) là **chữ vector-outline**, không phải scan. Scan thật chỉ 2 trang. |
| "Nối OCR của doc-parser vào là xong" | ❌ **Sai.** doc-parser xuất **Markdown**; PTL cần **PDF có text layer** kèm font/size/flags/color/bbox từng ký tự. Không phải việc đấu nối. |
| "Có OCR thì PTL dịch được trang scan" | ❌ **Sai về nguyên tắc** với scan thật (xem §2). |
| "Tài liệu scan đến thường xuyên nên đáng đầu tư" | ✅ Đúng về tần suất — nhưng đầu tư phải nhắm **vector-outline**, không phải scan. |

---

## 1. Nguyên nhân chặn thật: chữ vector-outline, không phải scan

Phân rã 7 job MANUAL_DTP theo số **trang**:

| Job | SCANNED_PAGE | TEXT_AS_VECTOR_SUSPECT |
|---|---|---|
| DELARATION OF CONFORMITY-V16 Lite (1p) | 1 | 0 |
| Pi LV1单页20260410-Q (2p) | 1 | 1 |
| E-Box 48100R guide20251021-Q (8p) | 0 | 8 |
| Pi LV1 user manual-PYTES 1.7-Q (27p) | 0 | 26 |
| V16 Base-安装步骤-Q (2p) | 0 | 2 |
| V16 quick guide final-20251204-Q (11p) ×2 | 0 | 22 |
| **Tổng** | **2** | **59** |

Soi `V16 quick guide final-20251204-Q.pdf` bằng PyMuPDF:
```
page 1: chars=0  drawings=113   type={'f':113}   images=0  glyph-sized 105/113
page 2: chars=0  drawings=385   type={'f':385}   images=1  glyph-sized 385/385
page 3: chars=0  drawings=2373  type={'f':2373}  images=0  glyph-sized 2373/2373
```
`chars=0`, không ảnh, **100 % path là fill cỡ glyph** → font đã convert-to-outline. Đây là bản in "-Q" nhà máy gửi, không phải scan.

**Độ phủ corpus** (192 PDF duy nhất): outline-vector **15 tài liệu / 71 trang** · scan thật **14 tài liệu / 65 trang** · sạch 163 (85 %).

---

## 2. Với scan thật, vẽ chữ dịch vào là BẤT KHẢ THI theo thiết kế

`fit_paint.py` — **cả 4 lần** gọi `apply_redactions` (dòng 504, 1758, 1774, 1786) đều dùng:
```python
images=pymupdf.PDF_REDACT_IMAGE_NONE      # bỏ chữ, giữ ảnh/vector
```
Và trong toàn file **không có** `insert_image`, `inpaint`, hay ghi `Pixmap`.

→ PTL **không bao giờ sửa pixel ảnh**. Đó là lời hứa sản phẩm (giữ nguyên ảnh/đồ hoạ), không phải thiếu sót.

Hệ quả với trang scan, kể cả khi đã có text layer OCR hoàn hảo:
1. OCR chèn text layer vô hình lên ảnh scan
2. PTL trích, dịch
3. Redaction xoá **text layer vô hình** (vô hại, nó vốn vô hình)
4. PTL vẽ tiếng Việt lên baseline
5. **Ảnh scan mang chữ tiếng Anh vẫn nguyên bên dưới**

→ Chữ Việt đè lên chữ Anh nhìn thấy được. **`MANUAL_DTP` là định tuyến ĐÚNG cho scan thật, không phải lỗ hổng cần vá.**

Muốn làm thật thì phải xoá **pixel** chữ gốc rồi inpaint nền — một lớp năng lực hoàn toàn khác (masking vùng chữ + inpaint raster), không phải OCR.

---

## 3. Với chữ vector-outline: khả thi, nhưng là NĂNG LỰC MỚI, không phải tích hợp

**Thuận:** glyph là vector path → `PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED` (đã dùng ở `fit_paint.py:1775`) xoá được. Không có ảnh raster để chống (`img_area/page = 0.00`).

**Bốn việc khó, không cái nào doc-parser giải hộ:**

| Việc | Vì sao khó |
|---|---|
| **Khôi phục style** | `extract_group.py` đọc `span["font"]`, `size`, `flags`, `color` từ rawdict để quyết bold/italic/serif/mono (`style_of`, `is_bold_font`, `is_serif_font`). Glyph outline **không có** thuộc tính nào trong số đó. Phải suy từ hình học — cap-height ra cỡ chữ, độ đậm nét ra bold. |
| **Baseline chính xác** | PTL vẽ tại baseline chính xác từ `span["origin"]`/`chars[].origin`. OCR chỉ cho hộp từ. |
| **Độ mịn redaction** | `LINE_ART_REMOVE_IF_TOUCHED` xoá **mọi** path bị rect chạm. Trang 3 có 2373 path glyph; xoá vùng chữ sẽ ăn cả nét đồ hoạ/khung bảng chồng lên. PTL đã có pass vẽ lại vạch bảng (dòng 1772-1776) nhưng sơ đồ trộn chữ thì hỏng. |
| **Chất lượng OCR** | Phải render raster rồi OCR; độ chính xác là của OCR (đo được: ocrmac 96–97 %, MinerU VLM 99,8 % tiếng Việt) chứ không còn là text layer chuẩn xác. |

Đây là **nhiều tuần**, có rủi ro trung thực layout thật — không phải "đấu nối".

---

## 4. Lối tắt vận hành chỉ cứu được 1/6

Kiểm tra có bản nguồn chưa outline không (đã loại output `_VI` và artifact trong `translation/jobs/`):

| File bị chặn | Nguồn thay thế dùng được |
|---|---|
| `V16 user manual-PYTES 1.0 Q 20251021_…` | ✅ `V16 user manual-PYTES 1.0 20251204(1).pdf` |
| `Pi LV1 user manual-PYTES 1.7-Q(1)` | ❌ không có |
| `V16 quick guide final-20251204-Q` | ❌ không có |
| `E-Box 48100R guide20251021-Q` | ❌ không có |
| `V16 Base-安装步骤-Q` | ❌ không có |
| `Pi LV1单页20260410-Q` | ❌ không có |

→ "Xin bản editable từ nhà cung cấp" **không** phải lời giải tổng quát, nhưng **đáng tự động dò** vì khi trúng thì chi phí bằng 0.

---

## 5. Đề xuất tách đôi

**1a — Preflight classifier (rẻ, làm ngay).** Không thêm năng lực mới; biến `MANUAL_DTP` câm thành chỉ dẫn hành động, và gộp luôn phát hiện mojibake ở báo cáo trước:

| Phân loại | Thông điệp cho người vận hành |
|---|---|
| `TRUE_SCAN` (2 trang) | MANUAL_DTP là đúng — dừng cân nhắc, kiến trúc không cho phép |
| `OUTLINED_VECTOR` (59 trang) | Cần bản editable; **tự dò sibling** trong corpus (trúng 1/6, chi phí 0) |
| `MOJIBAKE_TOUNICODE` | Sửa ToUnicode ở nguồn (đã tự làm tay 2 lần) |

Dùng chung cho **cả hai repo**: doc-parser cần đúng bộ phân loại này để chặn index, PTL cần nó ở preflight.

**1b — Đường trích xuất vector-outline (lớn, quyết riêng).** Rasterize → OCR → suy style từ hình học → vẽ kèm line-art redaction. 15 tài liệu / 71 trang corpus. Nhiều tuần, rủi ro trung thực layout.

**Thứ tự đề nghị sau verify:**
1. **1a preflight classifier + gate mojibake** (cả hai repo) — rẻ, gỡ tắc quyết định
2. **Gate cấu trúc bảng** (doc-parser) — 130/186 bảng ragged
3. *(Quyết riêng)* **1b** — hoặc chấp nhận MANUAL_DTP cho 15 tài liệu

---

## Câu hỏi chưa giải quyết

1. **Chốt tách 1a/1b?** — nếu đồng ý, plan sẽ viết cho 1a + gate bảng; 1b để dành quyết định riêng.
2. **Xin bản editable từ Pytes có khả thi không?** Nếu có kênh hỏi nhà cung cấp, 1b mất phần lớn lý do tồn tại — 15 tài liệu là hữu hạn và có nguồn.
3. Ngưỡng phân loại `OUTLINED_VECTOR`: hiện mượn heuristic của PTL (`n_chars<5 and drawings>40`). Có nên siết bằng tỉ lệ path cỡ-glyph (đo được 100 % ở ca thật) để tránh nhầm trang sơ đồ thuần?
4. MinerU cell bbox — vẫn chưa test (Docling đã xác nhận CÓ).
