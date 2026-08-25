# Audit toàn codebase doc-parser — sửa gate, pipeline, repair, docs, packaging

Nhánh: `claude/codebase-quality-verify-cb156e` · 17 file, +400/−50 · mọi thay đổi đã verify.

## Cách làm

5 reviewer song song (gates · pipeline · repair+runners · docs · packaging) → 27 phát hiện
→ xác minh đối kháng từng cái (mặc định *sai cho tới khi code chứng minh ngược lại*)
→ 15 confirmed, 1 rejected, 9 để lại chưa xác minh (severity thấp), 2 verifier lỗi hạ tầng.

Hai phát hiện rớt do verifier lỗi được tôi tự xác minh: hv falsy-zero (đã sửa + mutation
test) và release version guard (đã tái hiện, đã sửa).

**Không đổi bất kỳ ngưỡng đo được nào.** Mọi sửa đổi là sai *đại lượng* hoặc sai *luồng*,
không phải chỉnh số.

## Lỗi đã sửa

### Cấp cao — âm thầm làm hỏng kết quả

| # | File | Lỗi | Hệ quả |
|---|---|---|---|
| 1 | `quality_gates.py:382` | `region_dropped_pages()` lọc trang bằng **số loại từ** trong khi `evaluate()` chấm bằng **tổng lượt từ** | Trang lặp nhiều token kỹ thuật (đúng dạng bảng nhãn) có recall thấp thật nhưng bị loại khỏi phát hiện → `REGION_DROPPED` không bao giờ bắn, page-fill không chạy |
| 2 | `parse_document.py:267` | `(high_value_recall or 1)` biến `0.0` thành "chưa đo được" | Tài liệu **mất 100% mã model/đơn vị** — ca nặng nhất mà inject sinh ra để cứu — bị bỏ qua |
| 3 | `probe_document.py:106` | `route()` ném `KeyError` khi probe lỗi | **Một file hỏng giết cả batch** (tái hiện: PDF hỏng + XLSX giả) |
| 4 | `repair_dropped_regions.py` | `recover()` giả định `primary_pages[p] == trang PDF p` | Docling chỉ phát page-break giữa các trang **có item**; trang không sinh item làm lệch mọi đoạn sau → chấm điểm và vá vào **nhầm trang** |
| 5 | `repair_dropped_regions.py:42` | `split_blocks()` dán bảng với prose sau nó qua một dòng trống | Khối trộn từ vựng → gán nhầm trang |

Cơ chế (4) đã tái hiện thực nghiệm: PDF 3 trang, Docling chỉ sinh **1 item có provenance
ở trang 1**, `doc.pages = [1,2,3]`, **0 marker**. Đã thêm `aligned_pages()` — số đoạn phải
khớp số trang PDF, không khớp thì lùi về nhánh toàn-tài-liệu.

### Cấp trung — che giấu lỗi hoặc chức năng chết

| # | File | Lỗi | Sửa |
|---|---|---|---|
| 6 | `parse_document.py:129` | `run_gates()` nuốt mọi exception → `{}`, không phân biệt với "không có gì để chấm" | Cờ `GATE_EVAL_FAILED` + trường `gate_error` |
| 7 | `parse_document.py:217` | `--tier` nhận vào, truyền đi, **không bao giờ dùng** → T3 (MinerU hybrid) không tới được bằng bất kỳ cách nào tài liệu ghi | Ánh xạ tier→engine, `choices` chặn tier sai, tắt pre-batch khi ép tier |
| 8 | `parse_document.py:88` | Split sentinel Docling không kiểm số phần | Tài liệu chứa chuỗi đó làm output **lệch sang file khác**; nay raise, rơi về đường per-file |
| 9 | `repair_dropped_regions.py:107` | Báo trang đã vá kể cả khi bounds guard không ghi gì | `repaired` chỉ ghi cái thực sự ghi được |
| 10 | `pyproject.toml` | extra `anydoc` gọi sai tên gói (thực tế là `firecrawl-anydoc`); extra `mineru` thiếu `six` | Đối chiếu `setup-engines.sh`; đã xác nhận dist-info trong venv |

### Cấp thấp

`_run()` ném `IndexError` thay `RuntimeError` khi stderr toàn whitespace · trường `pages`
trong frontmatter mất giá trị `0` hợp lệ · `run_regression.py` thiếu timeout và hardcode
`PAGE_MARK` · `scan_unit_variants.py` không đọc `DOCPARSE_CORPUS_ROOT` (mọi README đều
ghi biến này) · 3 import chết, 2 semicolon, 1 lambda.

## Tài liệu lệch code

- `docs/SKILL.md` quick-start trỏ `.claude/skills/doc-parse/scripts` — **không tồn tại trong repo**.
- `docs/SKILL.md` mục "giới hạn đã biết" vẫn nói mojibake chưa xử lý và dẫn một luật lọc
  (`tỉ lệ dòng một ký tự ≥ 0,50`) **chưa từng có trong code**; thực tế `MOJIBAKE_SUSPECT`
  đã có từ commit `8207221`.
- Bảng cờ ở cả 3 README + SKILL.md thiếu 4 cờ code đang phát:
  `MOJIBAKE_SUSPECT`, `TABLE_STRUCTURE_BROKEN`, `NEEDS_OCR`, `LAYOUT_RISK_MEDIUM`.
- SKILL.md metadata version 2.0.0 vs VERSION/pyproject 2.0.1.

Đã sửa hết. 4 cờ audit-only (nay 6, thêm `PROBE_FAILED` + `GATE_EVAL_FAILED`) được ghi rõ
là **chưa nằm trong tập chặn index**, đúng quyết định của plan `260824-0935`.

## Cải tiến thêm

- **Release workflow** kiểm tag khớp `pyproject.toml` **và** `VERSION` trước khi build.
  Repo này đã trôi version một lần (CHANGELOG 2.0.1 ghi lại). Regex thay `tomllib` vì step
  chạy trước `setup-python`. Đã test cả hai chiều.
- **CI chạy ruff** — config `[tool.ruff]` có sẵn nhưng chưa ai chạy (22 lỗi tồn đọng).
  Đã dọn lỗi thật; `E401`/`I001` đưa vào ignore kèm lý do vì import gộp là quy ước cố ý ở
  cả 8 script (sửa hết = churn ngược quy ước).

## Verify

| Kiểm tra | Kết quả |
|---|---|
| Unit test (lite venv) | ✓ đạt |
| Unit test (venv sạch chỉ `pypdfium2`+`pyyaml`, mô phỏng CI) | ✓ đạt |
| **Mutation test — đảo từng bản sửa** | **6/6 mutation bị test bắt** |
| ruff | ✓ sạch |
| py_compile toàn bộ script | ✓ |
| YAML workflow | ✓ |
| E2E: PDF thật 3 trang (anydoc) | `text_recall 0.826`, `hv 1.0` → `TEXT_RECALL_WATCH` (đúng luật hạ cấp) |
| E2E: cùng file qua Docling | `text_recall 1.0`, không cờ |
| E2E: batch 4 file gồm 2 file hỏng | 4/4 xử lý xong, file hỏng mang `PROBE_FAILED`/`GATE_EVAL_FAILED`, `EXIT=0` |
| `--tier T3` | route đúng `mineru`; `--tier T9` bị argparse chặn |
| `run_regression.py` | 0/3 — **thiếu fixture PDF** (là partner document, không nằm trong repo theo `testdata/README.md`), không phải hồi quy |

Mutation test là bằng chứng test có giá trị: mỗi lần khôi phục code lỗi, đúng test tương
ứng đỏ. `region_dropped_pages()`, `aligned_pages()`, `split_blocks()` trước đó **không có
test nào**.

## Chưa sửa — cần đo trước

**Chuẩn chứng nhận có khoảng trắng không được gấp trong `normalize()`.** Tái hiện:

```
ref "IEC 62619 ... UN 38.3"  vs  hyp "IEC62619 ... UN38.3"
→ high_value_recall = 0.0     (đơn vị/độ C cùng ca: 1.0)
```

Cùng nội dung, chỉ khác khoảng trắng → gate báo mất sạch → `HIGH_VALUE_MISSING` +
inject append lại toàn bộ dòng chuẩn. Comment trong `quality_gates.py:71-77` có bàn tới
việc dạng dính bị đếm hai lần nhưng **không** xét ca lệch dạng giữa ref và hyp.

Không sửa vì luật cứng của repo: *rule normalize chỉ thêm khi đo được **engine bất đồng**,
không phải khi biến thể tồn tại*. Hạ tầng đo đã có sẵn (`std_spaced` / `std_tight` trong
`scan_unit_variants.py`) nhưng corpus không nằm trong repo:

```bash
$DP scripts/scan_unit_variants.py --json /tmp/variants.json   # cần $DOCPARSE_CORPUS_ROOT
```

Chỉ thêm rule khi text layer và engine ghi khác nhau trên cùng file. Cảnh báo phụ: gấp
`EN\s?\d{2,6}` quá tay có thể dính nhầm văn bản thường.

## Quyết định của người dùng — đã áp dụng

Bốn câu hỏi dưới đây đã được chốt: **1C · 2A · 3A · 4A**.

### 1C — chặn `PROBE_FAILED` khi không chấm được `readable_ratio` ✅ đã làm

Thêm cờ chặn mới `PROBE_FAILED_UNVERIFIED` (`parse_document.py:source_unverified`).
`PROBE_FAILED` **vẫn không tự chặn** — đó là kết quả đo, không phải thận trọng:

| File | PROBE_FAILED | readable_ratio | Cờ chặn mới | Nội dung |
|---|---|---|---|---|
| `corrupt.pdf` | có | không chấm được | **có** | rác |
| `fake.xlsx` | có | không chấm được | **có** | rác |
| `mislabeled.xlsx` (PDF đổi đuôi) | có | 0,329 | **không** | đúng 100% |

Mutation test: bỏ điều kiện `readable` → 2 test đỏ; đảo điều kiện → 3 test đỏ.

**Giới hạn đã ghi vào docs:** tài liệu ngắn hoặc thuần phi-Latin cũng cho
`readable_ratio = None`, nên probe lỗi trên đúng loại đó bị chặn oan. Hiệu chỉnh trên
3 file — cần đo rộng hơn trước khi dùng ở quy mô lớn.

### 2A — T3 giữ force-only ✅ đã ghi rõ

Không đổi code (đã đúng sau bản sửa `--tier`). Bổ sung vào `README.md` + `README_vi.md`:
T3 **không bao giờ** được router tự chọn; probe không đo gì hàm ý `colspan` thật hay công
thức; T3 chậm hơn T2 12× (100 trang: ~10 phút vs ~48 giây).

### 3A — đo trước khi gấp khoảng trắng mã chuẩn ✅ đã ghi vào giới hạn

Không đổi `normalize()`. Ghi thành giới hạn thứ ba trong `docs/SKILL.md`, kèm cả ba phép
đo đã làm (no-op khi cùng dạng · không làm loãng túi token · đếm hai lần là vô hại) và
lệnh đo còn thiếu. **Đính chính báo cáo trước:** phần "rủi ro dương tính giả khi gấp" tôi
viết ban đầu là **sai** — token như `EN 50` vốn đã nằm trong túi ở dạng rời, gấp lại chỉ
đổi tên chứ không kéo thêm rác (đo được 20 loại token trước và sau).

### 4A — người dùng cấp fixture ✅ harness đã sẵn sàng

Không đổi code kiểm thử. `run_regression.py` khi thiếu fixture giờ chỉ thẳng sang mục
tương ứng trong `testdata/README.md`. Vẫn **0/3** cho tới khi có file.

## Câu hỏi chưa giải quyết

1. **Ba fixture regression** — cần bạn thả file vào `testdata/regression/`. Đây là mục
   duy nhất khiến không thể khẳng định tuyệt đối các bản sửa đường vá; mọi thứ khác đã
   verify bằng đo đạc.
2. **Corpus cho `scan_unit_variants.py`** — cần `$DOCPARSE_CORPUS_ROOT` để chốt rule
   khoảng trắng mã chuẩn (giới hạn thứ ba trong SKILL.md).
3. **Ngưỡng `readable_ratio = None` của 1C hiệu chỉnh trên 3 file.** Nên chạy lại trên
   corpus rộng để đo tỉ lệ chặn oan tài liệu ngắn / thuần phi-Latin.
4. **Wiring của cờ không có unit test.** `source_unverified()` được test kỹ, nhưng việc
   `parse_one()` thật sự gọi nó và gắn cờ thì chỉ E2E xác nhận (mutation xoá dòng gắn cờ
   **không** bị unit test bắt). Đúng cấu trúc sẵn có của repo — mọi cờ khác cũng vậy —
   và là thứ 3 fixture regression sẽ phủ.
5. **`TABLE_OFF_MODAL_MAX` (2/186 lần kích hoạt)** — treo từ report `260824-0956`:
   giữ làm lưới an toàn hay bỏ?

Status: DONE
Summary: 15 phát hiện đã xác minh + 2 tự xác minh đều đã sửa và verify bằng mutation test;
quyết định 1C/2A/3A/4A đã áp dụng; tài liệu đồng bộ lại với code; không đụng ngưỡng đo
được nào.
Concerns: fixture regression không có trong repo nên `run_regression.py` vẫn 0/3 — cần
bổ sung từ corpus riêng trước khi tin hoàn toàn vào đường page-fill/inject. Ngưỡng của
cờ chặn mới hiệu chỉnh trên 3 file, chưa đủ rộng.
