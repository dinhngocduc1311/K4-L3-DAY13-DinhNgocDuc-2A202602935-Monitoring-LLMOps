# Alert và runbook

Các alert dưới đây dựa trên triệu chứng/SLO quan sát được từ `data/logs.jsonl`. Mọi điều tra đi theo Metrics → Logs → Traces và thông báo vào Slack `#day13-llmops-alerts`.

## Alert 1

- **Tên:** `high_user_latency`
- **Severity:** critical
- **Duration:** 5 phút
- **Kênh thông báo:** Slack `#day13-llmops-alerts`
- **SLI/SLO liên quan:** P95 latency của `response_sent`; SLO request thành công trong 3000 ms.
- **Điều kiện và thời gian duy trì:** `latency_p95_ms > 3000` liên tục 5 phút.
- **Ảnh hưởng tới người dùng:** Câu trả lời chậm dù API vẫn có thể trả HTTP 200.
- **Ba bước kiểm tra đầu tiên:**
  1. Khoanh time range và xác nhận P50/P95/P99, TTFT cùng traffic trên dashboard.
  2. Lọc `response_sent` có latency cao, lấy `correlation_id` và kiểm tra error/tool metadata.
  3. Mở trace cùng ID, so sánh thời lượng `retrieval` với `fake-llm-generation` để tìm bottleneck.
- **Mitigation tạm thời:** Giảm concurrency/rate, chuyển sang dependency lành mạnh hoặc rollback thay đổi gần nhất được trace chứng minh liên quan.
- **Owner:** `ai-api-oncall`

## Alert 2

- **Tên:** `elevated_errors_or_retrieval_failures`
- **Severity:** critical
- **Duration:** 5 phút
- **Kênh thông báo:** Slack `#day13-llmops-alerts`
- **SLI/SLO liên quan:** Error rate tối đa 2% và retrieval success tối thiểu 90%.
- **Điều kiện và thời gian duy trì:** `error_rate_pct > 2` hoặc `retrieval_success_rate_pct < 90` liên tục 5 phút.
- **Ảnh hưởng tới người dùng:** Request thất bại hoặc câu trả lời thiếu context cần thiết.
- **Ba bước kiểm tra đầu tiên:**
  1. Xác nhận error breakdown và retrieval success trên dashboard, tránh kết luận từ một request đơn lẻ.
  2. Lọc `request_failed`, lấy `error_type`, `tool_success=false` và `correlation_id` đại diện.
  3. Mở trace cùng ID, kiểm tra trạng thái/latency của child retrieval trước generation.
- **Mitigation tạm thời:** Bật fallback không retrieval nếu an toàn, giảm tải hoặc chuyển sang vector store dự phòng; không retry vô hạn.
- **Owner:** `ai-api-oncall`

## Alert 3

- **Tên:** `quality_regression`
- **Severity:** warning
- **Duration:** 15 phút
- **Kênh thông báo:** Slack `#day13-llmops-alerts`
- **SLI/SLO liên quan:** Quality proxy trung bình tối thiểu 0.75.
- **Điều kiện và thời gian duy trì:** `quality_score_avg < 0.75` liên tục 15 phút.
- **Ảnh hưởng tới người dùng:** API vẫn thành công nhưng câu trả lời kém liên quan hoặc thiếu context.
- **Ba bước kiểm tra đầu tiên:**
  1. So sánh quality theo prompt version/feature và kiểm tra retrieval success, token output, error rate.
  2. Lấy `correlation_id` của các response có quality thấp và đối chiếu structured log.
  3. Mở trace để kiểm tra prompt name/version/label, doc count và generation metadata.
- **Mitigation tạm thời:** Rollback label `production` về prompt version tốt gần nhất; chỉ thay retrieval/model khi trace chứng minh nguyên nhân.
- **Owner:** `llm-quality-oncall`
