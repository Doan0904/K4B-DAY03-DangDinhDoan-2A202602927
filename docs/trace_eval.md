# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Đặng Đỉnh Đoàn 
> **Mã Sinh Viên / Mã Học viên:** 2A202602927  
> **Chủ đề Lựa chọn:** Trợ lý Nhân sự VinFast (HR Assistant): Tra cứu ngày phép còn lại, chính sách bảo hiểm và tạo đơn xin nghỉ phép.

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | 4/ 5 | Hệ thống phải xử lý chuỗi logic phức tạp: Tiếp cận yêu cầu -> Phân tích điều kiện chính sách VinFast -> Tính toán số ngày phép hợp lệ -> Đối chiếu với quy chế phê duyệt trước khi tạo đơn xin nghỉ |
| **2. Tool Interaction** | 5/ 5 | Bắt buộc tính hợp đa nguồn: Tra cứu số dư phép qua DB/ HRIS API, tra cứu quy chế bảo hiểm qua Vector DB/RAG xong gọi MCP Sever/API nội bộ để push đơn tạo yêu cầu nghỉ phép vào hệ thống. |
| **3. Dynamic Decision** | 4/ 5 | Luồng thực thi thay đổi linh hoạt theo ngữ cảnh: Nếu số ngày phép còn đủ $\rightarrow$ tiến hành tạo đơn; nếu thiếu $\rightarrow$ chuyển hướng đề xuất nghỉ không lương; nếu hỏi chính sách đặc thù (ốm đau/thai sản) $\rightarrow$ yêu cầu bổ sung chứng từ liên quan. |
| **4. Long Horizon Goal** | 3/ 5 |Luồng thực thi thay đổi linh hoạt theo ngữ cảnh: Nếu số ngày phép còn đủ $\rightarrow$ tiến hành tạo đơn; nếu thiếu $\rightarrow$ chuyển hướng đề xuất nghỉ không lương; nếu hỏi chính sách đặc thù (ốm đau/thai sản) $\rightarrow$ yêu cầu bổ sung chứng từ liên quan.|
| **TỔNG ĐIỂM AGENTIC FIT** | **16/ 20** | *Bài toán rất phù hợp để triển khai Agentic System nhờ sự kết hợp chặt chẽ giữa Tool Calling, RAG chính sách và ra quyết định có điều kiện.* |

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

Dán 1 đoạn trích xuất log tiêu biểu từ file `docs/trace_waterfall.json` sinh ra từ phản hồi LLM API thật:

```json
[
  {
    "step": 1,
    "query": "Tôi là nhân viên VF2026001. Hãy kiểm tra xem tôi còn bao nhiêu ngày phép năm, nếu còn đủ ít nhất 2 ngày thì tạo luôn đơn xin nghỉ phép ngày 25 và 26 tháng này giúp tôi nhé.",
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini quyết định gọi công cụ 'check_leave_balance' với tham số: {\"employee_id\": \"VF2026001\"}",
    "tool_name": "check_leave_balance",
    "arguments": {
      "employee_id": "VF2026001"
    },
    "observation": {
      "status": "SUCCESS",
      "employee_id": "VF2026001",
      "full_name": "Lê Hoàng Nam",
      "leave_balance": {
        "total": 12,
        "used": 4,
        "remaining": 8
      },
      "message": "Nhân viên Lê Hoàng Nam (VF2026001) còn 8/12 ngày phép năm."
    },
    "latency_ms": 26905.59
  },
  {
    "step": 2,
    "query": "Tôi là nhân viên VF2026001. Hãy kiểm tra xem tôi còn bao nhiêu ngày phép năm, nếu còn đủ ít nhất 2 ngày thì tạo luôn đơn xin nghỉ phép ngày 25 và 26 tháng này giúp tôi nhé.",
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini quyết định gọi công cụ 'create_leave_request' với tham số: {\"start_date\": \"2026-09-25\", \"employee_id\": \"VF2026001\", \"reason\": \"Nghỉ phép cá nhân\", \"end_date\": \"2026-09-26\", \"leave_type\": \"annual_leave\"}",
    "tool_name": "create_leave_request",
    "arguments": {
      "start_date": "2026-09-25",
      "employee_id": "VF2026001",
      "reason": "Nghỉ phép cá nhân",
      "end_date": "2026-09-26",
      "leave_type": "annual_leave"
    },
    "observation": {
      "status": "SUCCESS",
      "request_id": "LR-VF2026001-20260925",
      "approval_status": "PENDING_APPROVAL",
      "employee_id": "VF2026001",
      "leave_type": "annual_leave",
      "start_date": "2026-09-25",
      "end_date": "2026-09-26",
      "days_requested": 2,
      "reason": "Nghỉ phép cá nhân",
      "message": "Đã tạo đơn nghỉ phép năm 2 ngày (25/09/2026 - 26/09/2026) cho nhân viên Lê Hoàng Nam (VF2026001), mã đơn LR-VF2026001-20260925, đang chờ Quản lý trực tiếp phê duyệt."
    },
    "latency_ms": 2869.24
  },
  {
    "step": 3,
    "query": "Tôi là nhân viên VF2026001. Hãy kiểm tra xem tôi còn bao nhiêu ngày phép năm, nếu còn đủ ít nhất 2 ngày thì tạo luôn đơn xin nghỉ phép ngày 25 và 26 tháng này giúp tôi nhé.",
    "action_type": "FINAL_ANSWER",
    "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ).",
    "output": "Chào anh **Lê Hoàng Nam (VF2026001)**,\n\nDưới đây là thông tin tra cứu và kết quả tạo đơn xin nghỉ phép của anh:\n\n### 1. Thông tin ngày phép năm:\n* **Tổng số ngày phép:** 12 ngày\n* **Số ngày đã sử dụng:** 4 ngày\n* **Số ngày phép còn lại:** **8 ngày** (Đủ điều kiện nghỉ phép 2 ngày)\n\n---\n\n### 2. Thông tin đơn xin nghỉ phép đã tạo:\n* **Mã đơn:** `LR-VF2026001-20260925`\n* **Loại nghỉ:** Nghỉ phép năm (*annual leave*)\n* **Thời gian nghỉ:** Từ ngày **25/09/2026** đến ngày **26/09/2026** (Tổng cộng: 2 ngày)\n* **Lý do:** Nghỉ phép cá nhân\n* **Trạng thái:** Đang chờ Quản lý trực tiếp phê duyệt (*PENDING_APPROVAL*)\n\nĐơn đã được gửi thành công lên hệ thống HR. Quản lý trực tiếp của anh sẽ xem xét và phê duyệt theo quy định.",
    "latency_ms": 50259.24
  }
]
```

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã điền API Key thật trong `.env` và xác nhận Agent chạy mượt mà trên LLM API thật (Gemini/OpenAI).
- **Tổng số Test Cases đã chạy thành công:** 5 / 5 test cases.
- **Số lượt gọi Tool qua MCP Server chính xác:** 6 lượt (TC02: `check_leave_balance`; TC03: `create_leave_request`; TC04: `check_leave_balance` → `create_leave_request`; TC05: `check_leave_balance` → `query_employee_benefits`, cả hai trả về `NOT_FOUND` đúng kỳ vọng).
- **Kết quả đẩy Repo nộp bài:** [x] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
