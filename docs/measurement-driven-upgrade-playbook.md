# Playbook nâng cấp dựa trên số đo

Rút từ vòng phát triển skill `doc-parse` (P2 → P2.1 → P2.1b, ~15 vòng review). Dùng khi
nâng version một công cụ có **ngưỡng, cờ, hoặc quyết định tự động** — parser, classifier,
gate chất lượng, router, bất cứ thứ gì phải trả lời "cái này đủ tốt chưa?".

Không dùng cho code không có ngưỡng (CRUD, UI, glue). Ở đó test thường là đủ.

---

## 1. Nguyên tắc

> **Đề xuất → đo trên corpus thật → mới implement.** Không đảo thứ tự, kể cả khi đề xuất
> nghe hiển nhiên đúng.

Trong vòng `doc-parse`, **bốn** giả định nghe rất hợp lý đã bị chính số đo bác bỏ. Cả bốn
đều suýt được chốt trước khi đo. Thứ ngăn lại không phải phán đoán tốt hơn mà là nhịp làm
việc: mỗi lần sắp đụng vào một hằng số hay một trục đo, phải đo trước.

Chi phí một phép đo thường là 10–60 phút. Chi phí một ngưỡng sai nằm im trong production
là một lớp tài liệu bị index sai mà không ai biết.

---

## 2. Bốn dạng sai lầm — nhận diện để tránh lặp

Mỗi ca dưới đây là một **dạng**, không phải giai thoại. Khi thấy mình đang lý luận theo
dạng nào, dừng lại và đo.

### 2.1 Proxy nghe hợp lý thay cho đo trực tiếp

| Ca | Proxy | Thực tế |
|---|---|---|
| "Lưới dày thì engine layout thắng, đừng vá" | mật độ nét vẽ | File lưới dày nhất (3.202 nét/trang) lại là file bị vứt mất bảng; file dày hơn nữa (5.078) thì parse hoàn hảo. Mật độ đo *có lưới hay không*, không đo *engine có giữ chữ trong lưới không* |
| "Trang giàu từ vựng mới là trang nội dung thật" | số loại từ ≥ T | Khối header TÜV giàu từ (74 loại: địa chỉ, điện thoại, fax) mất 3%; header một dòng nghèo từ (27 loại) mất 15%. Hai đại lượng **nghịch** nhau |

**Dấu hiệu:** câu lý luận có dạng "X thường đi kèm Y, nên dùng X thay Y".
**Cách sửa:** đo trực tiếp Y. Nếu Y đo được rẻ (thường là vậy), proxy không có lý do tồn tại.

### 2.2 Thước đo tự sinh ra mất mát giả

`datasheet.pdf` báo mất 4 giá trị nhiệt độ. Thực tế **chưa bao giờ mất** — text layer viết
`0°C`, Docling viết `0 ° C`, và regex chỉ chấp nhận tối đa một khoảng trắng.

Hệ quả nếu không phát hiện: mọi tài liệu có `°C` mang một khoản mất giả cố định, và đợt
hiệu chỉnh ngưỡng sau đó lệch theo.

**Dấu hiệu:** một chỉ số báo mất mát mà không giải thích được *cái gì* mất.
**Cách sửa:** trước khi tin con số, in ra **danh sách token bị coi là mất** và đọc bằng mắt.
Nếu chúng có mặt trong output dưới dạng khác → lỗi chuẩn hoá, không phải mất mát.

### 2.3 Đơn giản hoá một tín hiệu

Hai lần một tín hiệu bị đề xuất cho đứng một mình, hai lần corpus bác:

| Đề xuất | Vỡ ở đâu |
|---|---|
| `page_absent ≥ 0,10` tự quyết định "trang chết" | File canh gác `compat-list` chạm 0,143 mà không mất gì → harness rớt 2/3 |
| Bỏ `page_recall`, chỉ giữ `page_absent` | Khe "3% vs 15%" hoá ra chỉ tồn tại *bên trong* nhóm đã lọc bởi `page_recall < 0,50`. Trên toàn bộ trang, phân bố liên tục, không khe |

**Dấu hiệu:** "hai điều kiện này rườm rà, một cái là đủ".
**Cách sửa:** trước khi bỏ một điều kiện, đo phân bố của điều kiện còn lại **trên toàn tập**,
không chỉ trên nhóm đã bị điều kiện kia lọc. Khe trong tập con thường không tồn tại ở tập mẹ.

### 2.4 Đếm bội số khi câu hỏi là hiện diện

`high_value_recall` từng tính `Σ min(count_ref, count_out) / Σ count_ref`. Một số hiệu ở
header lặp 50 trang, engine gộp còn 13 → bị tính "mất 37 token" dù thông tin còn nguyên.

Trên 12 tài liệu, **3/3 lần cờ bắn đều là báo động giả**. Đổi sang đếm *loại token còn ít
nhất một lần*: ba báo động giả tắt, hai ca mất thật vẫn bị bắt (0,842 và 0,032).

**Dấu hiệu:** chỉ số phạt việc engine khử trùng lặp.
**Cách sửa:** hỏi lại câu hỏi nghiệp vụ. "IEC62619 có trong tài liệu không?" là *hiện diện*.
"Đoạn văn này còn bao nhiêu phần?" mới là *bội số*. Dùng đúng loại cho đúng câu hỏi.

---

## 3. Quy trình một vòng nâng cấp

```
1. ĐỀ XUẤT   viết rõ trục đo, ngưỡng dự kiến, và ca nào sẽ đổi hành vi
2. ĐO        dry-run trên corpus; KHÔNG ghi file, KHÔNG sửa code
3. ĐỌC       nếu số bác bỏ trục đo → dừng, báo cáo, đợi chốt lại. Không tự chuyển trục
4. IMPLEMENT chỉ khi số ủng hộ; kèm unit test biên ngay trong cùng thay đổi
5. VERIFY    unit test + regression harness + chạy lại toàn corpus, so trước/sau
6. GHI       cập nhật doc và version trong **cùng** thay đổi, không để sang vòng sau
```

**Bước 3 là bước hay bị bỏ nhất.** Khi số đo bác bỏ trục, phản xạ tự nhiên là tự chọn trục
khác rồi implement luôn. Đừng — đổi biến quyết định là quyết định của người review, không
phải của người đo. Chỉnh một hằng số thì tự làm được; đổi *cái được đo* thì phải trình.

### Cổng bắt buộc trước khi sửa một cơ chế vá

Dry-run cả chế độ cũ và mới, in ra bảng: mỗi ca **sẽ** được xử lý thế nào ở mỗi chế độ,
cộng một cột **rủi ro** (trùng lặp, chèn thừa). Chỉ merge khi:

- ca mục tiêu chuyển đúng chiều
- **file canh gác không đổi**
- cột rủi ro bằng 0, hoặc lệch có giải thích được

---

## 4. Thiết kế thước đo — checklist

| Câu hỏi | Vì sao |
|---|---|
| Chỉ số này trả lời **câu hỏi nghiệp vụ** nào? | "Còn tra được không" khác "còn đủ số lần không" |
| Hiện diện hay bội số? | xem 2.4 |
| Cờ **cứng** có đủ hai tín hiệu độc lập chưa? | Một tín hiệu luôn có kiểu nhiễu riêng. Hai tín hiệu, mỗi cái loại một kiểu |
| `None` nghĩa là gì, và **cực** nào? | Không đủ dữ liệu ≠ không có vấn đề. Xem 4.1 |
| Chuẩn hoá có **đối xứng** hai phía không? | Chỉ chuẩn hoá một phía là tự tạo lệch |
| Chấm trên **sản phẩm cuối** hay output thô? | Cờ phải mô tả thứ thực sự đi vào index |

### 4.1 Cực của `None` — đây là chỗ dễ sai nhất

Cùng một giá trị `None` phải có cực **ngược nhau** ở hai loại quyết định:

```
nâng một cảnh báo   →  dùng `intact is False`     →  None KHÔNG chứng thực
dập một cảnh báo    →  dùng `intact is not True`  →  None KHÔNG dập
```

Nguyên tắc chung: **thiếu bằng chứng không bao giờ được dùng làm bằng chứng.** Muốn nâng
cảnh báo thì cần bằng chứng có vấn đề; muốn dập cảnh báo thì cần bằng chứng không có vấn đề.
`None` không cung cấp cả hai.

### 4.2 Chấm sau khi vá, không phải trước

Cờ phải phản ánh bản cuối cùng đưa vào index. Hệ quả: vá chỗ này có thể làm chỗ kia thôi
bị gắn cờ — chấp nhận được, vì câu hỏi là "bản giao ra còn thiếu gì", không phải "engine
thô bỏ gì".

Đánh đổi: hai chỉ số không còn độc lập, một thay đổi ở khâu vá có thể lặng lẽ đổi cờ.
Regression harness là thứ canh chuyện đó.

---

## 5. Fixture và corpus — tài sản bền nhất

Sau tất cả, thứ đáng giữ không phải con số `0,90` hay `0,10` mà là **bộ fixture và corpus
đo**. Mọi ngưỡng đều có thể phải chỉnh; thứ cho phép chỉnh an toàn là khả năng chạy lại.

### Một bộ fixture tốt

| Tính chất | Ví dụ từ `doc-parse` |
|---|---|
| **Mỗi file khoá một failure mode khác nhau** | region drop · sparse token loss · false-positive guard |
| **Có ít nhất một file canh gác** — nơi công cụ *đúng* và không được báo động | `compat-list`: recall thấp mà không mất gì. File này đã bắt được 2/4 đề xuất sai |
| **Có cặp đối nghịch** — cùng bề ngoài, ngược kết quả | `compat-list` và `hv48100` đều là lưới dày; một cái parse hoàn hảo, một cái bị vứt. Cặp này là thứ cấm dùng mật độ nét vẽ làm luật |

File canh gác quan trọng hơn file mục tiêu. Ai cũng nhớ kiểm "ca xấu có bị bắt không";
ít người kiểm "ca tốt có bị bắt nhầm không" — mà đó mới là chỗ ngưỡng chết.

### Pin hành vi bằng **biên**, không bằng số thực

```json
{ "must_flags": ["HIGH_VALUE_RECOVERED"], "high_value_recall_min": 0.98 }
```

Không pin `0.571`. Con số đó từng đổi thành `0.536` khi pattern học nhận thêm một dạng mã
chuẩn — cùng hành vi, khác mẫu số. Pin số thực biến một cải tiến đúng thành test đỏ.

### Bộ test không cần dữ liệu

Ngoài fixture, giữ một tầng unit test **không cần file thật**: số học của chỉ số, biên của
ngưỡng, ngữ nghĩa `None`. Nó chạy trong một giây, không phụ thuộc corpus, và là chỗ duy nhất
pin được hành vi ở vùng ngưỡng mà corpus không có ca nào chạm tới.

> Corpus 12 file không có tài liệu nào trong vùng 0,85–0,95. Ngưỡng `0,90` được pin bằng
> unit test tổng hợp, và điều đó **được ghi rõ là chưa hiệu chỉnh trên phân bố thật**.

---

## 6. Versioning

| Thay đổi | Bump |
|---|---|
| Đổi **ngữ nghĩa** một chỉ số công khai (cùng tài liệu ra số khác) | **major** |
| Thêm cờ / chỉ số mới, cờ cũ giữ nguyên nghĩa | minor |
| Chỉnh hằng số trong cùng ngữ nghĩa, sửa doc | patch |

`doc-parse` lên `2.0.0` vì `high_value_recall` đổi từ đếm bội số sang đếm hiện diện: cùng
một PDF, bản 1.0 trả `0,843`, bản 2.0 trả `0,988`. Ai từng hiểu "≥ 0,95 nghĩa là…" theo bản
cũ sẽ đọc sai bản mới. **Chưa ai pin** không phải lý do để tránh major — định nghĩa đổi là
đổi.

---

## 7. Chống lệch tài liệu

Doc drift xuất hiện đúng ở chỗ hành vi vừa được cải thiện: tài liệu còn mô tả trạng thái
*trước* khi sửa.

Sau mỗi vòng, quét ba chỗ:

1. **Mô tả fixture** — kỳ vọng còn khớp harness không? (`datasheet` từng còn ghi cờ
   pre-inject sau khi inject đã cứu được nó)
2. **Bảng tóm tắt cờ** — có bỏ sót điều kiện mới thêm không? (dòng `TEXT_RECALL_LOW` từng
   thiếu quyền phủ quyết của "trang nội dung chết", tức đúng một nửa luật)
3. **Version + ghi chú caveat** — ngưỡng nào còn tạm thời thì phải nói rõ là tạm thời

Nếu có bản clone (repo public), quét cả hai — chúng lệch nhau rất nhanh.

---

## 8. Ghi caveat trung thực

Ngưỡng "đã verify" và ngưỡng "tối ưu" là hai chuyện khác nhau. Ghi rõ mức nào:

| Mức | Nghĩa |
|---|---|
| **Pin hành vi** | có unit test + regression; đổi là biết ngay |
| **Verify trên corpus** | không báo động giả trên N file / M lớp; ca thật vẫn bị bắt |
| **Hiệu chỉnh** | có phân bố đủ rộng, thấy khe, chọn điểm giữa khe |

`doc-parse` đạt hai mức đầu cho `0,90`, và ghi thẳng rằng corpus **không có ca nào trong
vùng 0,85–0,95** nên nó "đúng ở chỗ không gây hại, chưa phải điểm tối ưu đo được". Viết
như vậy tốn một câu và tiết kiệm cho người sau một đợt hiệu chỉnh nhầm tưởng đã xong.

---

## 9. Danh sách chống chỉ định

Những việc **không** làm, mỗi cái đã có ca thật đứng sau:

- Thêm luật chuẩn hoá theo phỏng đoán. Ba biến thể đơn vị được đề xuất (`kW h`, `A h`,
  `m m`) — quét 510 PDF cho ra **0 lần** cho hai cái đầu, và 14 lần của cái thứ ba đều là
  artifact của file diff mỗi ký tự một dòng.
- Hạ ngưỡng "cho có bắn". Nếu một guard chưa bao giờ kích hoạt, đó chưa phải bằng chứng
  nó thừa — hạ ngưỡng xuống sát giá trị đo được cao nhất là overfit vào corpus hiện tại.
- Sửa một cơ chế vá mà không dry-run trước.
- Bỏ file canh gác khỏi bộ fixture vì "nó luôn xanh".
- Để việc cập nhật doc sang vòng sau.
- Coi "chưa ai dùng" là lý do bỏ qua major bump.

---

## 10. Tự vấn trước khi chốt

Sáu câu, hỏi trước mỗi lần định chốt một ngưỡng hoặc một trục đo:

1. Tôi đang đo trực tiếp thứ mình quan tâm, hay đo một proxy của nó?
2. Nếu chỉ số này báo có vấn đề, tôi có in ra được **cái gì cụ thể** đang thiếu không?
3. Khe tôi thấy có tồn tại trên toàn tập, hay chỉ trong tập con đã bị lọc?
4. File canh gác có đổi hành vi không?
5. `None` ở đây được đọc theo cực nào, và có đúng không?
6. Tôi đang chỉnh một hằng số, hay đang đổi cái được đo? Nếu là vế sau — trình trước.

---

## Nguồn

Rút từ vòng phát triển của chính repo này. Số đo cụ thể và diễn biến từng vòng nằm ở
[`document-parsing-field-notes.md`](document-parsing-field-notes.md); bản ghi đo chi tiết
(corpus 12 file, bảng đo trước/sau mỗi thay đổi) giữ trong kho nội bộ nơi corpus sống.

## Câu hỏi chưa có lời đáp

1. Playbook này rút từ **một** vòng phát triển. Vòng thứ hai (skill khác, loại quyết định
   khác) sẽ cho biết phần nào là quy luật chung, phần nào chỉ đúng cho parser.
2. Chưa có bước nào tự động ép "đo trước khi chốt" — hiện phụ thuộc kỷ luật người review.
   Có đáng biến mục 10 thành checklist trong quy trình review không?
