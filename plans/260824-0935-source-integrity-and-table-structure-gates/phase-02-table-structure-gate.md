# Phase 02 — Gate hợp lệ cấu trúc bảng

> ⚠️ **Đã sửa khi thực thi.** Chỉ báo "raggedness cột" trong file này là **sai** — con số
> 70 % ragged đến từ một script đo ad-hoc dùng `.strip("|")` tham lam. Đo lại đúng: trung vị
> off-modal = 0.000, chỉ 2/186 bảng vượt 0.25. Chỉ báo thật là **mật độ ô rỗng**
> (anydoc 0.12–0.18 vs docling 0.00–0.02 trên cùng file). Chi tiết:
> [implementation report](../reports/implementation-260824-0956-source-integrity-gates-phase-01-02-report.md).

**Repo:** doc-parser · **Phụ thuộc:** Phase 01 (cùng bộ file)

## Vấn đề

Không gate nào kiểm cấu trúc bảng. `PANDAS_NOISE` chỉ dò `NaN`/`Unnamed:` và **chỉ chạy cho anydoc/markitdown** (`parse_document.py:322`).

Đo trên 37 tài liệu T0 corpus Pytes: **130/186 bảng (70 %)** có số cột không đồng nhất. Ba user manual tệ nhất mang `quality_flags: []`:

| Tài liệu | ragged/tổng |
|---|---|
| `PI STATION261 · Hướng dẫn sử dụng` | 17/25 |
| `V16 user manual-PYTES 1.0` | 10/16 |
| `HV48100 · Hướng dẫn sử dụng` | 9/11 |

Không chỉ là mất `colspan`. Engine **bịa cấu trúc bảng từ nội dung phi bảng** — biểu đồ, danh sách, dòng địa chỉ bị băm thành lưới pipe:
```
||Survey Results||||100%|Non Profit Support||
```
Rác đó vào index RAG trông như dữ liệu có thẩm quyền.

## Ý tưởng gốc

Bất biến tiling của `deepdoctection/pipe/refine.py`: *mọi tile trong lưới `n_row × n_col` phải được phủ đúng một lần.* Ở đây áp bản model-free lên markdown: **mọi hàng phải cùng số cột**.

Đã kiểm chứng trên Docling thật (`datasheet.pdf`): lưới 26×2 = 52 tile, chỉ 47 ô → **5 lỗ, 0 chồng lấn**, đúng các hàng tiêu đề lẽ ra `colspan=2`.

## Files

| File | Thay đổi |
|---|---|
| `scripts/quality_gates.py` | thêm `TABLE_OFF_MODAL_MAX`, `TABLE_DEFECT_SHARE`, `MIN_TABLE_BODY_ROWS`, `parse_md_tables(md)`, `table_defects(md)` |
| `scripts/parse_document.py` | cờ `TABLE_STRUCTURE_BROKEN`; `table_defect_share` vào frontmatter |
| `scripts/test_quality_gates.py` | case: bảng đều, bảng ragged, bảng 1 hàng, cell chứa `\|` escape, không có bảng |

## Các bước

1. `parse_md_tables(md)` — gom các khối dòng liên tiếp bắt đầu/kết thúc bằng `|`. Bỏ hàng separator (`^[\s|:\-]+$`). Bỏ bảng có `< MIN_TABLE_BODY_ROWS` (2) hàng body.
2. Đếm cột: split theo `|` **không** đứng sau `\`, sau khi strip `|` hai đầu.
3. Mỗi bảng: `off_modal = (số hàng có width ≠ modal) / (số hàng body)`. Lỗi khi `> TABLE_OFF_MODAL_MAX`.
4. Document: `defect_share = số bảng lỗi / tổng số bảng`. `> TABLE_DEFECT_SHARE` → `TABLE_STRUCTURE_BROKEN`.
5. Frontmatter ghi `table_defect_share` khi có ≥1 bảng.

## Ngưỡng

`TABLE_OFF_MODAL_MAX = 0.25` · `TABLE_DEFECT_SHARE = 0.25` · `MIN_TABLE_BODY_ROWS = 2`

Đo so sánh **cùng file, hai engine** (docling làm chuẩn đối chứng):

| Tài liệu | engine | bảng | off-modal>25 % | off-modal trung vị |
|---|---|---|---|---|
| V16 user manual | anydoc T0 | 16 | 6 (**38 %**) | 0,17 |
| V16 user manual | docling | 21 | 2 (10 %) | **0,00** |
| HV48100 HDSD | anydoc T0 | 11 | 3 (**27 %**) | 0,21 |
| HV48100 HDSD | docling | 15 | 1 (7 %) | **0,00** |

Docling đạt trung vị 0,00 ở cả hai → 0,25 tách sạch, margin ~2×. Docling cũng tìm ra **nhiều bảng hơn** (21 vs 16, 15 vs 11) → cờ này gián tiếp báo "chọn sai engine".

## Validation

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python
$DP scripts/test_quality_gates.py
$DP scripts/run_regression.py
```
Rồi: chạy 37 tài liệu T0 — cờ phải bắt ≥3 user manual đã biết. Chạy lại 2 file trên với `--engine docling` — **không** được bắt.

**Calibrate trước khi chốt:** 2 tài liệu là mẫu nhỏ. Trước khi coi ngưỡng là ổn định, chạy anydoc-vs-docling trên ≥8 tài liệu có bảng và kiểm ngưỡng vẫn tách. Ghi kết quả vào `reports/`.

## Rủi ro & rollback

- Bảng hợp lệ dùng `colspan` giả lập (hàng tiêu đề gộp) sẽ ragged **đúng luật markdown**. → ngưỡng đặt theo tỉ lệ, không theo tuyệt đối; và chỉ audit.
- Bảng trong code fence sẽ bị bắt nhầm. → bỏ qua vùng nằm giữa ``` fences.
- Rollback: gỡ `flags.append`; hàm mới thuần đọc, không đổi hành vi cũ.
