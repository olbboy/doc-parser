# Field notes — parse tài liệu sang Markdown

Bản ghi đầy đủ những gì **đo được** khi xây skill này (10–11/08/2026):
hành vi engine, bẫy cài đặt, sự thật về OCR tiếng Việt, license, và các lỗi kiến trúc
phải trả giá mới thấy.

Phương pháp luận (đo trước khi chốt, thiết kế thước đo, versioning) nằm ở
[`measurement-driven-upgrade-playbook.md`](measurement-driven-upgrade-playbook.md) —
không lặp lại ở đây. Tài liệu này là **dữ kiện**, cái kia là **cách làm**.

Môi trường đo: MacBook M5 Pro, 18 core, 48 GB, macOS 26.5. Phiên bản: anydoc `0.1.7` ·
MarkItDown `0.1.7` · Docling `2.119.0` · MinerU `3.4.4`.

---

## 1. Dòng thời gian

| Giai đoạn | Việc | Sản phẩm |
|---|---|---|
| Benchmark lại 4 engine | 11 tài liệu kỹ thuật thật, đo tốc độ + chất lượng, dựng PDF scan tiếng Việt có ground truth |
| Dựng skill `doc-parse` | probe → router 5 bậc → adapter 4 engine |
| Kiểm chứng bằng tài liệu ngoài corpus | một user manual 34 trang — phát hiện Docling vứt cả bảng |
| Phase A → B | gates, repair 2 tầng, harness 3 fixture |
| P2 → P2.1 → P2.1b | hiệu chỉnh ngưỡng, đổi ngữ nghĩa metric, luật trang chết |
| Xuất bản | tách bản public, loại tài liệu partner khỏi fixture |

---

## 2. Chế độ hỏng nguy hiểm nhất: thành công rỗng

MarkItDown `0.1.7` trên PDF scan trả `ok=True` với **0 ký tự**. Không exception, không
cảnh báo. Trong pipeline hàng loạt, tài liệu đó vào index như một trang trắng và **không
ai biết**.

Đối chiếu, anydoc báo lỗi dùng được:

```
UnsupportedError: PDF has no extractable text (Scanned, 4 pages): OCR is required
```

Chuỗi lỗi này về sau thành tín hiệu leo thang tier trong router.

> **Rút ra:** một engine trả rỗng mà báo thành công nguy hiểm hơn một engine crash. Mọi
> pipeline parse hàng loạt phải có cờ `EMPTY_SUCCESS` chặn index, không chỉ cờ
> `PARSE_FAILED`.

---

## 3. Hành vi engine — đo trên cùng tài liệu

### 3.1 Tốc độ

| Việc | anydoc | MarkItDown | Docling | MinerU |
|---|---|---|---|---|
| Office (5 file) | 0,5–20 ms | 23–1.076 ms | 94–923 ms | 27–802 ms (HTTP) |
| PDF text layer, 36 trang | **0,13 s** | 4,47 s | 16,9 s (2,13 tr/s) | 70,0 s (0,51 tr/s) |
| MinerU VLM qua MLX | — | — | — | 0,09–0,16 tr/s |

anydoc nhanh hơn MarkItDown **11–62×** — không phải vì tối ưu hơn mà vì nó là Rust không
chạy suy luận nào. Với vài chục file thì khác biệt vô nghĩa; chỉ đáng kể ở quy mô hàng
chục nghìn file hoặc khi parse đồng bộ trong request.

**Docling trên MPS chỉ nhanh hơn CPU 1,25×** (2,13 so với 1,71 tr/s). Đây là lý do không
cần đầu tư GPU rời cho nhánh này.

### 3.2 Chất lượng — bốn ca quyết định

| Ca | anydoc | MarkItDown | Docling | MinerU |
|---|---|---|---|---|
| Bảng lưới dày, header 2 tầng (246 dấu ✓) | giữ đủ ✓ nhưng **gộp header vào 1 ô** | 24 dải phân cách, header rỗng | **đúng cột** | **đúng + `colspan`/`rowspan` thật** |
| Bảng thông số không kẻ viền — ghép nhãn↔giá trị | **0/3** | 1/3 | **3/3** | **3/3** |
| Workbook 32 sheet, 18 ẩn | lộ **18/18** | lộ **18/18** | lọc | lọc, giữ đúng 14 tên sheet |
| PPTX 18 slide, 0 title placeholder | 0 heading | 18 × `### Notes:` | 0 heading | **15 `##` = 15 tiêu đề slide** |

Hai chi tiết đáng nhớ:

- **MarkItDown đọc XLSX bằng `pandas.read_excel().to_html()`**, nên mọi ô rỗng thành `NaN`.
  Một workbook chào giá 32 sheet sinh **16.724 token `NaN` + 163 header `Unnamed:`** đi
  thẳng vào embedding. Một file 14 KB cũng nhiễm 230 token.
- **Sheet ẩn là vấn đề bảo mật, không chỉ nhiễu.** Trong workbook đó, 18 sheet bị ẩn chứa
  phương án cũ và số liệu không dành cho bên ngoài. Hai engine rẻ đưa hết vào output.

### 3.3 Docling có thể **vứt** một vùng có chữ

Phát hiện quan trọng nhất về Docling, tìm ra khi kiểm chứng bằng một tài liệu ngoài corpus
(HV48100 user manual): trang 17 có bảng nhãn sản phẩm 14 dòng model
(`HV48100 BMU-5` … `BMU-15` kèm điện áp, dung lượng, mã định danh). Toàn bộ nằm trong text
layer. Docling xuất ra:

```
## 2.3 Mô tả nhãn Bộ điều khiển pin

<!-- image -->
```

Chuỗi `BMU-8` xuất hiện **0 lần**. Thử cả ba chế độ (tắt OCR / OCR theo vùng / OCR toàn
trang) — mất cả ba. anydoc giữ nguyên 14/14 dòng.

**Độ dài output không phát hiện được:** Docling xuất **nhiều ký tự hơn** anydoc (76.860 so
với 59.802) nhờ đệm khoảng trắng bảng, trong khi thực tế mất nội dung. Đây là lý do sinh ra
toàn bộ tầng gate về sau.

Công bằng với Docling: cùng trang đó nó dựng bảng cổng kết nối **chuẩn hơn cả `pdftotext`**.
Nó đánh đổi, không kém.

---

## 4. OCR tiếng Việt — nơi trực giác sai nhiều nhất

Đo trên 6 trang scan của HV48100 manual (1.780 từ, **1.576 ký tự có dấu**), ground truth là
text layer gốc:

| Engine | word recall | ký tự có dấu | giây/6 trang |
|---|---|---|---|
| Docling + Tesseract `vie` | **96,7%** | 97% | 23 |
| MinerU `vlm-engine` (Pro-2605) | 96,2% | **99,8%** | 50 |
| Docling + macOS Vision `vi-VT` | 96,1% | 97% | 22 |
| Docling + EasyOCR `vi` | 91,3% | 94% | 29 |
| **Docling + RapidOCR `vi`** | **49,7%** | **46%** | 25 |
| **MinerU `pipeline`** | **51,9%** | **50%** | 18 |
| MarkItDown | **0%** | 0 | 0,01 |

### Ba điều phải nhớ

**Khai báo hỗ trợ ≠ hỗ trợ được.** `vi` **thật sự** nằm trong 52 ngôn ngữ của PP-OCRv6, và
Docling resolve đúng — không phải no-op. Nhưng thực tế mất 54% dấu thanh. Đọc danh sách
ngôn ngữ hỗ trợ không thay được một phép đo.

**Mã ngôn ngữ của Apple là `vi-VT`, không phải `vi-VN`.** Dùng `vi-VN` thì Docling raise
`Invalid language preference`. Danh sách đầy đủ lấy bằng:

```python
from ocrmac import ocrmac; print(ocrmac.SUPPORTED_LANGUAGES)
```

**MinerU tiếng Việt phải tách theo backend.** `pipeline` tệ (50% dấu) vì tập model OCR tải
về chỉ có `ch`, `en`, `arabic`, `el`, `cyrillic`, `devanagari`, `eslav` — **không có tiếng
Việt**, và `mineru --lang` không nhận `vi` lẫn `latin`. Nhưng `vlm-engine` với
MinerU2.5-Pro-2605 giữ **99,8%** dấu. Kết luận "MinerU kém tiếng Việt" đúng cho một nửa
và sai cho nửa kia.

> **Hệ quả vận hành:** chuỗi dự phòng cho PDF scan phải là `docling+OCR → mineru:vlm-engine`,
> **không bao giờ** `pipeline`. Đây từng là bug thật trong skill: `parse_one` gán
> `backend="pipeline"` cho mọi tier ≠ T3, nên scan tiếng Việt lỗi Docling sẽ rơi thẳng vào
> đường phá dấu.

---

## 5. Bẫy cài đặt — bốn cái mất thời gian nhất

| Bẫy | Triệu chứng | Cách qua |
|---|---|---|
| `mineru-models-download` báo `exit 0` nhưng tải thiếu | Config ghi đầy đủ, nhưng thiếu `models/MFR/unimernet_hf_small_2503/model.safetensors` (810 MB) → mọi lần parse PDF chết với `OSError` trần | `hf_hub_download('opendatalab/PDF-Extract-Kit-1.0', 'models/MFR/.../model.safetensors')` |
| `six` là dependency ẩn của MinerU 3.4.4 | Gỡ `six` → báo `HybridDependencyError: requires mineru[pipeline], including torch` — tức **chỉ sai người dùng đi cài lại thứ đã có** | `pip install six` |
| `markitdown[all]` mặc định ra **0.1.5**, không phải 0.1.7 | Extra `all` cần `azure-ai-contentunderstanding>=1.2.0b1` (pre-release), resolver lùi version. Hai bản khác nhau thật ở PDF | `--prerelease=allow` |
| Docling / MinerU đều tải model qua HuggingFace lần đầu | Trong phiên này HF **stall 2 lần** ở file lớn | `HF_HUB_ENABLE_HF_TRANSFER=1`, kill và chạy lại; môi trường có allowlist phải pre-stage |

Ngoài ra, `timeout` không có trên macOS (GNU coreutils) — một lệnh bọc `timeout` chạy im
lặng không làm gì và báo exit 0 giả.

---

## 6. Hai quy tắc vận hành bắt buộc

### 6.1 Không bao giờ shell ra CLI của MinerU trong vòng lặp

| Cách gọi | `doa.xlsx` | `gia-pi-station.docx` |
|---|---|---|
| CLI, service tạm | 6,38 s | 5,71 s |
| CLI, `--api-url` thường trú | 3,69 s | 3,82 s |
| **HTTP `POST /file_parse`** | **0,027 s** | **0,239 s** |

**236× trên file nhỏ.** Phần lớn chi phí là import interpreter + torch mỗi lần gọi, không
phải parse. Ngay cả `--api-url` vẫn tốn ~3,7 s chỉ để khởi động client.

### 6.2 Gom file Docling thành lô

Tiến trình Docling mới tốn **~10 s `torch.compile`** trước trang đầu; lần convert đầu tiên
trong một tiến trình sạch đo được **205 giây** cho một file 2 trang (gồm cả tải model).
Hai file chạy gộp: 33 s, chạy tách: 88 s.

Cả hai quy tắc dẫn tới cùng một kết luận: **worker thường trú**, không process-per-file.

---

## 7. Ba lỗi kiến trúc phải trả giá mới thấy

### 7.1 Chuỗi dự phòng phải dựng lại sau mỗi lần thất bại

Dựng một lần trước vòng lặp thì khi anydoc trả `"OCR is required"`, MarkItDown vẫn nằm
cuối chuỗi và sẽ được thử trên PDF scan — đúng engine trả rỗng im lặng. Phải dựng lại để
chuỗi còn lại **chỉ giữ engine có OCR**.

### 7.2 Tên file output đụng nhau, ghi đè im lặng

`doa.pdf` và `doa.xlsx` cùng ghi ra `doa.md`; file chạy sau đè file trước, không cảnh báo.
Phát hiện tình cờ vì `doa.pdf` mất `text_recall` trong frontmatter — hoá ra đang đọc
frontmatter của `doa.xlsx`.

Với một thư mục nguồn giữ cả `.docx` và `.pdf` của cùng một tài liệu, đây là **mất dữ liệu
im lặng**. Sửa: nếu đích đã tồn tại và `source_file` khác → ghi thành `<stem>-<ext>.md`.

### 7.3 Service con ghi rác vào CWD

`mineru-api` tạo thư mục scratch theo task **dưới CWD**. Chạy từ gốc repo → **43 MB thư mục
`output/`** với 39 task dir. Sửa: `cwd=` trỏ vào temp khi spawn.

> **Rút ra chung:** ba lỗi này không lộ ra trong bất kỳ test đơn lẻ nào. Chúng chỉ xuất
> hiện khi chạy **một thư mục thật** — đó là lý do phải có ít nhất một lần chạy toàn corpus
> trước khi tin pipeline.

---

## 8. Đọc benchmark công bố

Quy ước dùng suốt vòng này: 🔬 = tự đo, 📄 = số công bố. **Không trộn hai loại khi ra
quyết định.**

| Bẫy | Ca cụ thể |
|---|---|
| **Benchmark tự chấm** | OmniDocBench v1.6 do chính nhóm MinerU tạo trong paper MinerU2.5-Pro |
| **Cùng một con số, hai nghĩa** | "93,6 TEDS" của TableFormer là *PubTabNet, bảng đã cắt sẵn, model 2022*; "93,62" của MinerU2.5-Pro là *OmniDocBench full, parse cả trang, 2026*. Không so được với nhau |
| **Nhầm danh tính model** | MDPBench chấm **MinerU-2.5** ra 58,8 điểm tiếng Việt. MinerU 3.4.4 mặc định dùng **Pro-2605** — model khác, đo lại được 96,2% word recall. Trích số cho sai model là kết luận ngược |
| **Số của đối thủ chạy** | olmOCR-Bench do Datalab chạy, trong đó Marker của chính họ đứng đầu |

Và bài học lớn nhất: **báo cáo trước đó của chính tôi có 4 chỗ sai** chỉ vì sandbox không
tải được model, buộc phải trích số công bố. Chạy lại trên máy thật đảo ngược hai khuyến
nghị (RapidOCR, và đánh giá MinerU tiếng Việt).

---

## 9. License — rủi ro nhỏ hơn tưởng, nhưng có điều kiện

MinerU dùng license riêng, không phải OSI: "MinerU Open Source License" = Apache 2.0 **cộng
điều khoản thêm**. Ba điểm đã kiểm:

1. **Ngưỡng thương mại** (MAU > 100 triệu hoặc doanh thu tháng > 20 triệu USD) — không chạm.
2. **Nghĩa vụ ghi công bắt buộc**: dịch vụ trực tuyến xây trên MinerU phải nêu rõ và dễ
   thấy. **Áp dụng ngay** nếu nhúng vào sản phẩm có giao diện.
3. **Bẫy weight**: `MinerU2.5-2509-1.2B` là **AGPL-3.0**; bản `Pro-2605` là Apache 2.0.

Điểm 3 tưởng là rủi ro lớn, nhưng đo được: **MinerU 3.4.4 tự tải Pro-2605 (Apache)** làm
mặc định. Rủi ro AGPL chỉ phát sinh nếu cố tình ghim weight 2509.

anydoc, MarkItDown, Docling: MIT sạch. Model Docling: Apache-2.0 / CDLA / MIT.

---

## 10. Xuất bản — cái gì không được ra ngoài

Khi clone skill sang repo public, bộ fixture (3,4 MB) là **tài liệu partner Pytes**, và
chính `testdata/README.md` do tôi viết đã ghi *"không phát hành ra ngoài"*.

Cách xử lý giữ được cả hai: **loại PDF, giữ harness và bảng mô tả fixture cần thoả tính
chất gì**. Người clone về vẫn dựng được bộ regression của riêng họ; hành vi vẫn được pin
bằng `expected/*.json` và unit test không cần dữ liệu.

Hai chi tiết vận hành:

- SSH key trên máy chưa đăng ký GitHub → `gh repo create --push` fail ở bước push dù repo
  đã tạo. Chuyển remote sang HTTPS, đi qua credential helper của `gh`.
- **Hai bản clone lệch doc rất nhanh.** Bản public được viết lại lúc clone, bản gốc thì
  không — một mô tả fixture lỗi thời tồn tại ở bản gốc thêm nhiều giờ.

---

## 11. Những chỗ tôi tự sai và tự sửa

Ghi lại vì đây là phần dễ mất nhất khi nhìn lại một dự án đã xong.

| Nhận định ban đầu | Số đo cho thấy |
|---|---|
| anydoc giữ bảng compat-list "tra được" | **Không.** Nó gộp header 2 tầng vào một ô. Chỉ Docling và MinerU hybrid cho bảng tra được theo cột |
| Nên dùng Docling + RapidOCR `lang=["vi"]` cho tiếng Việt | **Đảo ngược.** RapidOCR là engine tệ nhất trong nhóm (46% dấu) |
| MinerU kém tiếng Việt | Đúng cho `pipeline`, **sai cho VLM** (99,8% dấu) |
| Phải ghim weight Pro-2605 để tránh AGPL | 3.4.4 **đã** mặc định Pro-2605 |
| `#7` tốn một lần chạy anydoc thừa vì ngưỡng `hv < 0,99` | **Không kiểm chứng được, có lẽ sai** — bảng đo sau khi nới giống hệt trước |
| `high_value_recall` của datasheet là 0,571 | 0,536 — mẫu số đổi khi pattern học nhận thêm `UN38.3`, không phải hồi quy |
| Khe "3% vs 15%" đủ để `page_absent` đứng một mình | Khe chỉ tồn tại **trong nhóm đã lọc**; trên toàn tập là phân bố liên tục |

Bốn chỗ đầu đến từ việc trích số công bố thay vì đo. Ba chỗ sau đến từ việc khái quát hoá
từ một tập con. Không chỗ nào đến từ code sai.

---

## 12. Bảng tra nhanh

| Hằng số / sự thật | Giá trị |
|---|---|
| Mã ngôn ngữ Vision cho tiếng Việt | `vi-VT` (không phải `vi-VN`) |
| `mineru --lang` hỗ trợ | `ch ch_server korean ta te ka th el arabic east_slavic cyrillic devanagari` — **không có `vi`, không có `latin`** |
| MinerU backend trên Apple Silicon | tự chọn `mlx-engine`; nạp model lần đầu 704,9 s |
| Weight mặc định MinerU 3.4.4 | `MinerU2.5-Pro-2605` (Apache 2.0) |
| Dung lượng model | Docling ~164 MB + TableFormer · MinerU pipeline 1,7 GB · MinerU VLM ~2,5 GB |
| Cách phát hiện PDF scan | `chars/page < 50` trên mẫu vài trang đầu |
| Cách phát hiện bảng lưới dày | `vector paths/page > 400` (compat-list 5.078; datasheet 46) |
| Đếm ô gộp DOCX | phải cộng cả `vMerge`, không chỉ `gridSpan` — bỏ `vMerge` sót 5/13 bảng |
| Biến thể đơn vị trong 510 PDF kỹ thuật | `kW h` = 0 · `A h` = 0 · `m m` = 14 (toàn artifact file diff) |

---

## Câu hỏi chưa có lời đáp

1. Nhánh Office (xlsx/docx/pptx) và nhánh scan chưa qua vòng gate/repair như nhánh PDF
   text layer — chúng dựa vào benchmark ban đầu. Corpus P2 không có file Office nào.
2. Chưa có gì tự động chạy `run_regression.py`; trên repo public càng khó vì không kèm
   fixture. Bước rẻ nhất nếu muốn siết: một GitHub Action chỉ chạy `test_quality_gates.py`
   (không cần PDF, phủ toàn bộ số học của gate).
3. Thứ tự fallback cho PDF **không** cần OCR vẫn để MinerU `pipeline` khi tier ≠ T3 — rủi
   ro tiềm ẩn với PDF text-layer tiếng Việt nếu engine chính lỗi. Chưa đo, đang trong backlog.
