# Thực thi Phase 03 — Preflight source classifier (pdf-translate-layout)

Repo: `/Users/leo/Projects/pdf-translate-layout` · nhánh `feat/preflight-source-classifier` · chưa commit
Engine đã được **bạn** mở khoá; **tôi không tự khoá lại** — xem §Bàn giao.

## Đã làm

| File | Thay đổi |
|---|---|
| `scripts/_common.py` | `readable_ratio()`, `READABLE_RATIO_MIN=0.02`, `MIN_READABLE_TOKENS=200` (+42 dòng) |
| `scripts/preflight.py` | `outlined_glyph_share()`, `_source_key()`, `find_editable_source()`, `meta_origin()`; 3 mã lỗi mới; `source_origin` vào job.yaml (+140/−5) |
| `scripts/selftest.py` | 15 case mới (+55 dòng) |

### Ba mã lỗi mới

| Mã | Sev | Ý nghĩa |
|---|---|---|
| `OUTLINED_VECTOR_TEXT` | P1 | chữ đã convert-to-outline → **xin bản gốc từ nhà cung cấp** |
| `MOJIBAKE_TOUNICODE` | P1 | text layer không đọc được → **sửa nguồn trước khi dịch** |
| `EDITABLE_SOURCE_FOUND` | P2 | đã tự tìm ra bản còn text layer, kèm đường dẫn |

`SCANNED_PAGE` giữ nguyên mã, đổi `detail` thành dứt khoát: *"engine không sửa pixel ảnh theo thiết kế, MANUAL_DTP là đúng"* — để người vận hành thôi phải tự cân nhắc trên ca vốn bất khả thi.

`source_origin` là metadata thuần, **không** vào determinism tuple → không ảnh hưởng fingerprint/reproducibility. Job cũ không có trường này → `meta_origin` trả None → bỏ qua dò sibling (có test).

## Validation

**8 file thật đã từng chặn job:**

| Tài liệu | classification | mã mới |
|---|---|---|
| DELARATION OF CONFORMITY-V16 Lite | MANUAL_DTP_REQUIRED | `SCANNED_PAGE`×1 |
| E-Box 48100R guide20251021-Q | MANUAL_DTP_REQUIRED | `OUTLINED_VECTOR_TEXT`×8 |
| Pi LV1单页20260410-Q | MANUAL_DTP_REQUIRED | `SCANNED_PAGE`×1, `OUTLINED`×1 |
| Pi LV1 user manual-PYTES 1.7-Q(1) | MANUAL_DTP_REQUIRED | `OUTLINED`×26 |
| V16 Base-安装步骤-Q | MANUAL_DTP_REQUIRED | `OUTLINED`×2 |
| V16 quick guide final-20251204-Q | MANUAL_DTP_REQUIRED | `OUTLINED`×11 |
| V16 user manual-PYTES 1.0 Q 20251021 | MANUAL_DTP_REQUIRED | `OUTLINED`×27, `SCANNED`×2, **`EDITABLE_SOURCE_FOUND`** |
| PI STATION261 · Hướng dẫn sử dụng | SUPPORTED_WITH_REVIEW | **`MOJIBAKE_TOUNICODE`** (tỉ lệ 0.001) |

Tổng: **75 trang outline · 4 trang scan · 1 nguồn thay thế tìm được · 1 mojibake · 0 trang còn kẹt ở `TEXT_AS_VECTOR_SUSPECT`**.

> Plan dự kiến 59 trang outline. Con số đó là **undercount** — nó lấy từ bảng JOB_SUMMARY vốn chỉ hiển thị *30 issue gần nhất*. Số thật là 75.

**Hồi quy 18 job RELEASED:** classification `SUPPORTED → SUPPORTED`, **18/18 không đổi**. Không mã mới nào kích hoạt. Khác biệt duy nhất là `DOMAIN_CONTEXT_MISSING` — artifact của việc tôi chạy lại không truyền `--domain-context`, không phải regression.

**Selftest:** `458 → 473 case, ALL PASS`. Compile sạch, không import thừa.

## Caveat phải nói rõ

**Nửa phân biệt của luật glyph-share chưa được dữ liệu thật kiểm chứng.** Cả 71 trang vector-suspect trong corpus đều đạt ≥0.90, không có ca âm tính nào — nghĩa là corpus không chứa trang "sơ đồ thuần, không chữ" để chứng minh luật biết loại nó ra. Ngưỡng 0.8 có biên an toàn so với 0.90, nhưng hành vi phân biệt hiện được khoá bằng **test tổng hợp** trong `selftest.py`, không phải bằng ca thật. Đã ghi thẳng vào docstring.

`MOJIBAKE_TOUNICODE` để **P1 chứ chưa P0** — mới có một ca dương tính làm bằng chứng. P1 đã đủ đẩy job sang `SUPPORTED_WITH_REVIEW` nên không bản dịch nào tự phát hành trên nguồn hỏng; nâng P0 sau khi có thêm mẫu.

## Bàn giao — engine đang MỞ KHOÁ

```
./scripts/lock-engine.sh verify
FAIL: file engine đã đổi so với lúc khoá:
   scripts/_common.py
   scripts/preflight.py
   scripts/selftest.py
```
Đúng 3 file, không thừa file nào — audit trail hoạt động đúng thiết kế.

**Tôi không tự chạy `lock`.** `lock` sinh lại manifest từ trạng thái hiện tại, tức là tự chứng nhận thay đổi của chính mình — đúng cái anti-pattern mà cơ chế này dựng lên để chặn. Sau khi bạn review xong:

```bash
./scripts/lock-engine.sh lock
```

## Câu hỏi chưa giải quyết

1. Có commit 3 phase không, hay để nguyên trên hai nhánh chờ review? (doc-parser: `feat/source-integrity-gates`, PTL: `feat/preflight-source-classifier`)
2. Có nên dựng một ca "sơ đồ thuần" thật để kiểm chứng nửa phân biệt của glyph-share, hay chấp nhận test tổng hợp?
3. Gate bảng bên doc-parser vẫn chỉ có **1 ca dương tính**. Chạy anydoc-vs-docling trên ≥8 tài liệu nữa để chốt ngưỡng trước khi dùng thật?
4. `EDITABLE_SOURCE_FOUND` mới trúng 1/6. Có muốn mở rộng phạm vi quét (hiện: thư mục chứa file + 1 cấp cha, tối đa 12 PDF mở ra) không?
