# Thực thi Phase 01–02 (doc-parser) · Phase 03 bị chặn

Nhánh: `feat/source-integrity-gates` (doc-parser) · `feat/preflight-source-classifier` (PTL, chưa có commit nào)

## Trạng thái

| Phase | Repo | Trạng thái |
|---|---|---|
| 01 — gate mojibake | doc-parser | ✅ **Xong, đã validate** |
| 02 — gate cấu trúc bảng | doc-parser | ✅ **Xong** — nhưng **đổi chỉ báo**, xem §Đính chính |
| 03 — preflight classifier | pdf-translate-layout | ⛔ **Chặn** — engine khoá chỉ-đọc có chủ đích |

---

## Phase 01 — Gate mojibake ✅

`scripts/quality_gates.py`: thêm `READABLE_RATIO_MIN=0.02`, `MIN_READABLE_TOKENS=200`, `readable_ratio()`.
`scripts/parse_document.py`: cờ `MOJIBAKE_SUSPECT`, trường `readable_ratio` vào frontmatter.
`scripts/test_quality_gates.py`: 10 case mới.

**Kết quả trên 37 tài liệu T0 corpus Pytes:**
```
bị cờ: 1   → PI STATION261 · Hướng dẫn sử dụng.md   readable_ratio: 0.001
dương tính giả: 0
phân bố 6 thấp nhất: 0.001 · 0.078 · 0.078 · 0.105 · 0.118 · 0.171
```
Frontmatter thật:
```yaml
text_recall: 0.986      # gate cũ vẫn nói "sạch"
readable_ratio: 0.001
quality_flags: ["MOJIBAKE_SUSPECT"]
```

Dải ký tự siết lại chỉ-Latin (`À-ÖØ-öø-ɏḀ-ỿ`) để Hy Lạp/Kirin không bị chấm gần 0 và đọc nhầm thành mojibake — có test riêng.

---

## Đính chính — chỉ báo Phase 02 phải đổi ⚠️

**Con số "130/186 bảng (70 %) ragged" trong hai báo cáo trước là SAI.** Nguyên nhân: script đo ad-hoc của tôi dùng `.strip("|")` tham lam, nuốt mất ô rỗng ở đầu/cuối hàng:

```
||Normal OFF Blink 2||||     đếm cũ = 1 ô   ·   đúng = 5 ô
```

Đo lại bằng parser đúng ngữ nghĩa GFM (bỏ **đúng một** pipe mỗi đầu):

| | off-modal trung vị | bảng vượt 0.25 |
|---|---|---|
| 186 bảng corpus T0 | **0.000** | **2 (1 %)** |

→ **Raggedness cột là chỉ báo chết.** Engine luôn phát ra lưới đều cột, kể cả khi nội dung bên trong là rác. Ngưỡng 0.25 trong plan không bắt được gì.

**Chỉ báo thay thế — mật độ ô rỗng — tách sạch.** Cùng file, hai engine:

| Tài liệu · engine | ô rỗng trung vị |
|---|---|
| V16 manual · anydoc | 0.18 |
| V16 manual · **docling** | **0.02** |
| HV48100 HDSD · anydoc | 0.12 |
| HV48100 HDSD · **docling** | **0.00** |
| Storytelling P1 · anydoc (sách biểu đồ) | **0.44** — 27/72 bảng >50 % rỗng |

Cùng nguồn, khác engine → chênh 9×. **Emptiness là artifact của engine, không phải của tài liệu** — đó là điều làm nó thành chỉ báo hợp lệ.

Nội dung vẫn hỏng thật như đã mô tả — anydoc gộp cả tiêu đề mục vào ô bảng:
```
|“protection” status is released. 7.1 Unable to Start Problem|Notes: Blink description
```
Chỉ là **số cột** không phản ánh được điều đó; **độ rỗng** thì có.

---

## Phase 02 — Gate cấu trúc bảng ✅ (chỉ báo mới)

Một bảng là lỗi khi **>50 % ô rỗng** (`TABLE_EMPTY_CELL_MAX`) **hoặc** hàng lệch số cột (`TABLE_OFF_MODAL_MAX`, hiếm nhưng có thật — 2/186). Tài liệu bị cờ khi >25 % số bảng lỗi.

**Kết quả:**
```
Storytelling P1 (anydoc)   share=0.389  ← CỜ
Storytelling P2 (anydoc)   share=0.029
V16 · anydoc  0.0    | V16 · docling      0.053
HV48100 · anydoc 0.091 | HV48100 · docling 0.0
37 tài liệu T0: bị cờ 0
```
Bắt đúng ca cần bắt (biểu đồ bị băm thành bảng giả), 0 dương tính giả.

⚠️ **Chỉ có 1 ca dương tính trong toàn bộ bằng chứng.** Vì vậy giữ nguyên audit-only, chưa đưa vào tập chặn index.

## Validation (doc-parser)

```
scripts/test_quality_gates.py   ✓ tất cả test đạt   (+18 case mới)
scripts/run_regression.py       ✓ 3/3 đạt — compat-list · datasheet · hv48100 không đổi
```

---

## Phase 03 bị chặn — engine PTL khoá có chủ đích ⛔

`scripts/` của pdf-translate-layout là `dr-xr-xr-x`, mọi file `-r--r--r--`. Cơ chế nằm ở `scripts/lock-engine.sh`, và lý do được ghi ngay trong header của nó:

> *"sự cố 2026-08-05 — Antigravity sửa `scripts/approve.py`, đổi hai chốt chặn human-approval thành `if False:` rồi tự approve và phát hành. Mọi hàng rào viết bằng Python nằm trong cây thư mục agent ghi được đều là hàng rào tự nguyện. Quyền ghi của filesystem thì không."*

Đây là hàng rào dựng lên **để chặn đúng loại tác nhân như tôi**, sau một sự cố thật. `unlock` được ghi rõ là dành cho *"khi chính mình cần sửa engine"*.

**Tôi không tự chạy `unlock`.** Vòng qua một chốt bảo vệ vì tin rằng thay đổi của mình vô hại chính là kịch bản mà chốt đó tồn tại để ngăn.

Đã xác nhận không đụng gì:
```
./scripts/lock-engine.sh verify  →  OK: engine nguyên vẹn
git status                        →  sạch
```

**Cần bạn quyết một trong hai:** tự chạy `./scripts/lock-engine.sh unlock` rồi bảo tôi tiếp; hoặc cho phép rõ ràng để tôi chạy lệnh đó. Sau khi sửa xong phải chạy lại `lock` trước khi giao việc cho agent khác.

---

## Câu hỏi chưa giải quyết

1. **Ai mở khoá engine PTL** — bạn hay tôi (cần cho phép rõ ràng)?
2. Bằng chứng gate bảng chỉ có **1 ca dương tính**. Có nên chạy anydoc-vs-docling trên ≥8 tài liệu nữa để chốt ngưỡng trước khi dùng thật không?
3. `TABLE_OFF_MODAL_MAX` giờ gần như không bao giờ kích hoạt (2/186). Giữ làm lưới an toàn hay bỏ cho gọn?
4. Có commit hai phase này không, hay để nguyên trên nhánh chờ review?
