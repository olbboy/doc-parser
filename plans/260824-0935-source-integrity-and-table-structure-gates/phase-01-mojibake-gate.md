# Phase 01 — Gate mojibake (ToUnicode hỏng)

**Repo:** doc-parser · **Phụ thuộc:** không

## Vấn đề

PDF có ToUnicode CMap hỏng phát ra glyph index thay vì Unicode. Text layer đọc ra là rác:
```
(XURSHDQ JHQHUDO *UHHFH     →  shift +29  →  European general Greece
```

**Gate hiện tại mù theo thiết kế.** `quality_gates.evaluate()` so output với *chính text layer của PDF*. Text layer đã hỏng → tham chiếu và giả thuyết hỏng giống hệt → `recall ≈ 1.0`. Kết quả thật trên `PI STATION261 · Hướng dẫn sử dụng`:
```yaml
text_recall: 0.986   high_value_recall: —   quality_flags: []
```
13 324 token rác vào index với giấy chứng nhận sạch.

Gate hỏi *"engine có giữ được thứ text layer có không"* — chưa bao giờ hỏi *"thứ đó có đọc được không"*.

## Yêu cầu

Đo trên **output markdown** (không phải text layer), engine-agnostic, mọi `doc_kind`.

## Files

| File | Thay đổi |
|---|---|
| `scripts/quality_gates.py` | thêm `READABLE_RATIO_MIN`, `MIN_READABLE_TOKENS`, `_STOPWORDS_EN`, `_STOPWORDS_VI`, `readable_ratio(text)` |
| `scripts/parse_document.py` | thêm cờ `MOJIBAKE_SUSPECT` vào khối tính `flags`; thêm `readable_ratio` vào frontmatter khi không None |
| `scripts/test_quality_gates.py` | case: mojibake thật, văn bản EN sạch, VI sạch, song ngữ CJK, dưới ngưỡng token |

## Các bước

1. `quality_gates.py` — hàm mới:
   - tách token `[A-Za-zÀ-ỹ]{2,}` từ body (bỏ frontmatter ở phía gọi)
   - `None` nếu `< MIN_READABLE_TOKENS` (200) — không đủ mẫu để phán, **không** đọc None là "sạch"
   - trả `max(hit_EN, hit_VI) / len(tokens)`, làm tròn 3 chữ số
   - dùng `max` chứ không phải tổng: tài liệu VI thuần không bị phạt vì thiếu stopword EN
2. `parse_document.py` — sau khối `PANDAS_NOISE`, thêm:
   - tính `readable_ratio` trên `md` (đã bỏ frontmatter — lúc này `md` chưa gắn frontmatter, dùng trực tiếp)
   - `< READABLE_RATIO_MIN` → `flags.append("MOJIBAKE_SUSPECT")`
3. Frontmatter: thêm `readable_ratio` cạnh `text_recall`, chỉ khi không None (đã có cơ chế lọc `if v is not None`).
4. Tests.

## Ngưỡng

`READABLE_RATIO_MIN = 0.02` · `MIN_READABLE_TOKENS = 200`

Đo trên 35 tài liệu T0 corpus Pytes:

| Tài liệu | ratio |
|---|---|
| `PI STATION261 · Hướng dẫn sử dụng` (mojibake) | **0,105 %** |
| Thấp nhất hợp lệ (nameplate song ngữ EN/FR, 334 token) | 7,784 % |
| Tài liệu thường | 17–25 % |
| CJK-nặng (14,9–15,2 % body) | 20,3–22,9 % |

Biên 74×. Ngưỡng 0,02 cho margin ~19× cả hai phía.

## Validation

```bash
DP=$HOME/.local/share/doc-parse/lite/bin/python
$DP scripts/test_quality_gates.py
$DP scripts/run_regression.py          # 3 fixture cũ không đổi
```
Rồi chạy lại 37 tài liệu T0 corpus: đúng **1** hit, đúng file đã biết, **0 dương tính giả**.

## Rủi ro & rollback

- Ngưỡng dựa trên **1 ca dương tính**. → chỉ audit, **không** thêm vào tập chặn index.
- Tài liệu thuần CJK/Ả Rập không có token Latin → `None`, bị bỏ qua. Đúng hành vi mong muốn; ghi rõ trong docstring.
- Rollback: gỡ 1 dòng `flags.append` — cờ chỉ là phần thêm, không đụng cờ cũ.
