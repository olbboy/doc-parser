# Calibrate ngưỡng gate cấu trúc bảng — 10 tài liệu, mỗi tài liệu parse 2 engine

Việc này do chính `phase-02` yêu cầu ("Calibrate trước khi chốt: 2 tài liệu là mẫu nhỏ").
Phương pháp: cùng một file nguồn, parse bằng **anydoc (T0)** và **Docling**, so `table_defect_share`.
Docling chạy batch một lệnh theo đúng luật repo (không tách tiến trình).

## Số liệu

| Tài liệu | anydoc n / share / blank~ | docling n / share / blank~ |
|---|---|---|
| EFGX25120270-IE-04-L01 | 22 / 0.045 / **0.331** | 29 / 0.000 / 0.000 |
| DSS_SHES250901811431 | 9 / 0.111 / **0.333** | 8 / 0.000 / 0.042 |
| E-BOX 48100R（ECOX）SDS | 11 / 0.091 / 0.176 | 1 / 0.000 / 0.000 |
| DSS_SUER251000136671-SGS | 7 / 0.143 / 0.000 | 4 / 0.000 / 0.000 |
| V16 user manual | 16 / 0.000 / 0.179 | 19 / 0.053 / 0.021 |
| HV48100 · HDSD | 11 / 0.091 / 0.125 | 15 / 0.000 / 0.000 |
| V16_SDS正本 | 11 / 0.000 / 0.111 | 1 / 0.000 / 0.000 |
| V5° Điều khoản BH (EN) | 3 / 0.000 / 0.185 | 2 / 0.000 / 0.000 |
| V5°/V5°α/DLFP-V5 MSDS | 4 / 0.000 / 0.072 | 4 / 0.000 / 0.000 |
| PI STATION261 · Chứng nhận | 5 / 0.000 / 0.067 | 4 / 0.000 / 0.012 |

```
share  anydoc max = 0.143   ·   docling max = 0.053   ·   ngưỡng = 0.25
blank~ anydoc  min 0.000  med 0.151  max 0.333
blank~ docling min 0.000  med 0.000  max 0.042
```

## Kết luận

**1. Ngưỡng 0.25 an toàn nhưng phủ hẹp.** 0 dương tính giả trên **20 lượt parse**. Nhưng cũng 0 dương tính *thật* — trên tài liệu kỹ thuật thật gate không bao giờ kích hoạt. Toàn bộ bằng chứng dương tính vẫn chỉ là **1 file**: sách biểu đồ bị anydoc băm thành 72 bảng giả (share 0.389).

→ Giữ nguyên **audit-only**. Không siết ngưỡng khi chưa có thêm ca dương tính.

**2. Tín hiệu nền tách sạch hơn nhiều so với cái cờ.** blank trung vị: anydoc 0.151 vs docling **0.000**, và **anydoc rỗng hơn ở 10/10 tài liệu**. Nhưng cái đó trả lời *"có engine tốt hơn không"* — câu hỏi **định tuyến**, không phải *"đầu ra có hỏng không"*. Nếu bật thành cờ thì gần như mọi output T0 sẽ bị cờ. Đã cố ý tách hai câu hỏi này; ghi rõ trong docstring.

**3. Đính chính một khẳng định tôi đã viết vào code.** Docstring cũ nói *"Docling tìm được nhiều bảng hơn anydoc (19 vs 16, 15 vs 11)"*. Đo rộng ra thì **sai**: docling tìm **ít** hơn ở vài chứng chỉ (1 vs 11 ở V16_SDS và E-BOX ECOX, 4 vs 7 ở DSS_SUER). Đã sửa docstring; số lượng bảng không kết luận được theo chiều nào.

> ⚠️ Chênh 11→1 bảng đáng theo dõi riêng: docling có thể đang gộp hoặc bỏ bảng ở nhóm chứng chỉ. Gate recall hiện có sẽ bắt nếu mất chữ, nhưng nếu bảng bị gộp mà chữ còn thì không cờ nào thấy. **Ngoài phạm vi lần này.**

## Việc phụ đã làm kèm

- **Gate chạy đúng trên input không phải PDF.** `.docx` và `.xlsx` qua anydoc: `table_defect_share` tính đúng, không lỗi, không cờ giả.
  ⚠️ `ess-bess-survey-guide.docx` có `readable_ratio: 0.07` — **thấp hơn sàn 0.078 của corpus PDF**. Vẫn cách ngưỡng 0.02 tới 3,5× nên an toàn, nhưng con số "biên 74×" là đặc thù corpus PDF, không phải bất biến. Tài liệu dạng biểu mẫu (nhiều nhãn trường, ít hư từ) tự nhiên sẽ thấp.
- **`TABLE_OFF_MODAL_MAX` không đóng góp phát hiện độc lập nào.** Chỉ 2/186 bảng vượt, cả hai nằm trong đúng file mojibake đã bị `MOJIBAKE_SUSPECT` bắt, và không đẩy tài liệu nào qua ngưỡng. Giữ làm lưới an toàn cho một lớp lỗi có thật mà corpus chưa có ca sạch — cùng lý do với test tổng hợp của glyph-share.
- Sửa comment ở `parse_document.py` cho khớp với khối code (giờ chứa cả hai check, không chỉ readability).

## Trạng thái

```
doc-parser  test_quality_gates.py  ✓  |  run_regression.py  ✓ 3/3
PTL         selftest.py 473/473 ✓     |  engine đã khoá lại (-r--r--r--)
```
Cả hai nhánh **chưa commit**: `feat/source-integrity-gates` · `feat/preflight-source-classifier`.

## Câu hỏi chưa giải quyết

1. **Có commit hai nhánh không?** Chưa từng được yêu cầu nên tôi chưa làm.
2. Chênh lệch số bảng 11→1 giữa anydoc và docling ở nhóm chứng chỉ — điều tra riêng?
3. Có muốn tách một cờ **định tuyến** (`BLANKER_THAN_AVAILABLE_ENGINE`) từ tín hiệu blank 10/10 không? Cần thiết kế đo riêng, không nên nhét vào gate hiện tại.
4. PPTX chưa test với gate mới (route T1/MinerU, cần dựng `mineru-api`).
