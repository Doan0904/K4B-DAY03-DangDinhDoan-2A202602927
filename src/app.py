"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""

import json
import os
import re
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPAcademicServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS
)
from providers import LLMProviderError, get_llm_provider

load_dotenv()

def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list):
    """Ghi vết log Waterfall Trace Log ra file docs/trace_waterfall.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")


TEXT_TOOL_CALL_INSTRUCTION = (
    "Bạn vừa viết lời gọi Tool dưới dạng văn bản nên hệ thống KHÔNG thực thi hành động đó. "
    "Nếu cần thực hiện hành động, hãy gọi Tool qua function calling; "
    "nếu đã đủ dữ liệu, hãy đưa ra câu trả lời cuối cùng cho nhân viên."
)


def looks_like_text_tool_call(content: str, tool_names: list) -> bool:
    """Phát hiện LLM viết lời gọi Tool bằng văn bản (ví dụ 'Action: create_leave_request{...}') thay vì gọi Tool thật"""
    if re.search(r"^\s*Action\s*:", content, re.MULTILINE):
        return True
    return any(re.search(rf"{re.escape(name)}\s*[({{]", content) for name in tool_names)


def summarize_observations(history: list) -> str:
    """Tổng hợp câu trả lời dự phòng từ các Observation khi LLM không tự đưa ra kết luận"""
    messages = [
        item["observation"].get("message") or json.dumps(item["observation"], ensure_ascii=False)
        for item in history
        if item["type"] == "tool"
    ]
    return " ".join(messages) if messages else "Chưa thu thập được dữ liệu nào từ MCP Server."


def run_react_agent(user_query: str, provider, mcp_server: MCPAcademicServer) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server
    Trả về danh sách trace log của phiên thực thi.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    step = 0
    trace_logs = []
    # Các bước đã thực thi, nạp lại cho LLM dưới dạng Native Tool Calling (function_call -> function_response)
    history = []
    tools_list = mcp_server.list_tools()
    tool_names = [tool["name"] for tool in tools_list]

    while step < MAX_ITERATIONS:
        step += 1
        step_start_time = time.time()
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")

        # Gọi LLM với Native Tool Calling Specs, kèm lịch sử Tool Call & Observation của các bước trước
        try:
            llm_response = provider.generate_with_tools(
                user_query, tools_list, system_prompt=REACT_AGENT_SYSTEM_PROMPT, history=history
            )
        except LLMProviderError as e:
            # Giữ lại các bước đã chạy của câu hỏi này để thống kê quota chính xác
            e.partial_trace = trace_logs
            raise
        latency_ms = round((time.time() - step_start_time) * 1000, 2)

        thought = llm_response.get("thought", "Đang suy luận...")
        print(f"🧠 [Thought]: {thought}")

        # Trường hợp 1: LLM trả lời bằng văn bản -> Final Answer, dừng vòng lặp
        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")

            # Safeguard: LLM "viết" lời gọi Tool thay vì gọi Tool thật -> không coi là Final Answer
            if looks_like_text_tool_call(final_content, tool_names):
                print("⚠️ [SAFEGUARD]: LLM viết lời gọi Tool dưới dạng văn bản, hệ thống không thực thi hành động này.")
                if not any(item["type"] == "correction" for item in history):
                    print("🔁 [SAFEGUARD]: Nhắc LLM gọi Tool qua function calling ở lượt kế tiếp.")
                    trace_logs.append({
                        "step": step,
                        "query": user_query,
                        "action_type": "TEXT_TOOL_CALL_REJECTED",
                        "thought": thought,
                        "output": final_content,
                        "latency_ms": latency_ms
                    })
                    history.append({
                        "type": "correction",
                        "content": final_content,
                        "instruction": TEXT_TOOL_CALL_INSTRUCTION,
                        "provider_state": llm_response.get("provider_state")
                    })
                    continue
                final_content = f"Agent chưa hoàn tất được hành động tiếp theo qua Tool. {summarize_observations(history)}"

            print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_content,
                "latency_ms": latency_ms
            })
            return trace_logs

        # Trường hợp 2: LLM đề xuất gọi Tool (Action)
        if llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {})
            print(f"🛠️ [Action Proposed]: {tool_name}({arguments})")

            # Safeguard: chặn gọi lặp lại cùng Tool với cùng tham số (tránh vòng lặp vô tận)
            if any(item["type"] == "tool" and item["tool_name"] == tool_name and item["arguments"] == arguments for item in history):
                final_answer = summarize_observations(history)
                print("⚠️ [SAFEGUARD]: LLM đề xuất lặp lại Action đã thực thi. Dừng vòng lặp và tổng hợp kết quả.")
                print(f"🏁 [Final Answer]: {final_answer}")
                trace_logs.append({
                    "step": step,
                    "query": user_query,
                    "action_type": "FINAL_ANSWER",
                    "thought": "Phát hiện Action lặp lại, tổng hợp câu trả lời từ các Observation đã có.",
                    "output": final_answer,
                    "latency_ms": latency_ms
                })
                return trace_logs

            # Thực thi Tool qua MCP Server
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result", {})

            if not obs_data:
                print("👁️ [Observation từ MCP Server]: {}")
                print("⚠️ [CHÚ Ý]: MCP Server trả về kết quả rỗng! Học viên cần hoàn thành TODO 2.1 trong 'src/mcp_server.py'.")
            else:
                print(f"👁️ [Observation từ MCP Server]: {json.dumps(obs_data, ensure_ascii=False)}")

            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "thought": thought,
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "latency_ms": latency_ms
            })

            # Nạp Tool Call + Observation vào lịch sử để LLM suy luận tiếp ở lượt kế tiếp
            history.append({
                "type": "tool",
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "provider_state": llm_response.get("provider_state")
            })
            continue

        # Trường hợp 3: Phản hồi không đúng định dạng -> dừng an toàn
        final_answer = summarize_observations(history)
        print(f"⚠️ [CHÚ Ý]: LLM trả về định dạng không hỗ trợ: {llm_response}")
        trace_logs.append({
            "step": step,
            "query": user_query,
            "action_type": "FINAL_ANSWER",
            "thought": "Phản hồi LLM không hợp lệ, tổng hợp câu trả lời từ các Observation đã có.",
            "output": final_answer,
            "latency_ms": latency_ms
        })
        return trace_logs

    # Safeguard: hết số bước tối đa mà LLM vẫn chưa đưa ra Final Answer
    final_answer = f"Không thể hoàn thành trong {MAX_ITERATIONS} bước tối đa. {summarize_observations(history)}"
    print(f"\n⛔ [MAX ITERATIONS]: {final_answer}")
    trace_logs.append({
        "step": step,
        "query": user_query,
        "action_type": "MAX_ITERATIONS_REACHED",
        "thought": "Đã đạt giới hạn số bước ReAct, dừng vòng lặp để tránh lặp vô tận.",
        "output": final_answer,
        "latency_ms": 0.0
    })
    return trace_logs

def parse_selected_test_ids(argv: list) -> set:
    """Đọc danh sách Test Case từ tham số '--tc TC02,TC04'"""
    if "--tc" not in argv:
        return set()
    index = argv.index("--tc")
    if index + 1 >= len(argv):
        return set()
    return {tc_id.strip().upper() for tc_id in argv[index + 1].split(",") if tc_id.strip()}


def print_llm_error(error: Exception):
    """In lỗi LLM API kèm gợi ý xử lý"""
    print(f"\n⛔ [LLM API ERROR]: {error}")
    message = str(error)
    if "PerDay" in message:
        print("👉 Đã hết quota theo ngày của model này. Hãy chờ quota reset, đổi LLM_MODEL khác trong .env, hoặc đặt LLM_PROVIDER=mock để phát triển offline.")
    elif "NOT_FOUND" in message:
        print("👉 Model không khả dụng. Hãy kiểm tra lại LLM_MODEL trong file .env.")
    elif "503" in message or "UNAVAILABLE" in message:
        print("👉 Server Gemini vẫn quá tải sau nhiều lần thử lại. Hãy chạy lại sau vài phút hoặc tạm đổi LLM_MODEL khác.")


if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")

    provider = get_llm_provider()
    mcp_server = MCPAcademicServer()

    print(f"🔌 LLM Provider: {provider.__class__.__name__} (Model: {provider.model_name})")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")

    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")

    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent:")
        print("💡 Gợi ý câu hỏi thử nghiệm:")
        print("   - Câu hỏi chung: 'Nhân viên VinFast có bao nhiêu ngày phép năm?'")
        print("   - Tra cứu ngày phép: 'Nhân viên VF2026001 còn bao nhiêu ngày phép năm?'")
        print("   - Tạo đơn nghỉ phép: 'Tạo đơn nghỉ phép năm cho VF2026001 từ 20/10/2026 đến 21/10/2026 với lý do việc gia đình'")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc phiên trò chuyện.\n")
        while True:
            try:
                user_input = input("👤 Nhân viên hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                save_waterfall_trace(logs)
            except LLMProviderError as e:
                print_llm_error(e)
                print("🛑 Kết thúc phiên trò chuyện do lỗi LLM API.")
                break
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break
    elif "--all" in sys.argv or "--tc" in sys.argv:
        selected_ids = parse_selected_test_ids(sys.argv)
        if "--tc" in sys.argv and not selected_ids:
            print("⚠️ Thiếu mã Test Case. Ví dụ: python src/app.py --tc TC02,TC04")
            sys.exit(1)

        run_tests = [tc for tc in tests if not selected_ids or tc["id"].upper() in selected_ids]
        if selected_ids:
            unknown_ids = selected_ids - {tc["id"].upper() for tc in tests}
            if unknown_ids:
                print(f"⚠️ Không tìm thấy Test Case: {', '.join(sorted(unknown_ids))}")
            print(f"🎯 [SELECTED MODE] Chỉ chạy {len(run_tests)} Test Case: {', '.join(tc['id'] for tc in run_tests)}")
        else:
            print(f"🚀 [TEST SUITE MODE] Kiểm tra {len(run_tests)} Test Cases:")

        completed_count = 0
        todo_count = 0
        all_traces = []
        llm_error = None

        for tc in run_tests:
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")

            if tc["question"].strip().startswith("TODO"):
                print(f"⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print(f"   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế cho Test Case này!")
                todo_count += 1
            else:
                try:
                    logs = run_react_agent(tc["question"], provider, mcp_server)
                except LLMProviderError as e:
                    llm_error = e
                    all_traces.extend(getattr(e, "partial_trace", []))
                    break
                all_traces.extend(logs)
                completed_count += 1

        # Mỗi bản ghi trace (trừ MAX_ITERATIONS_REACHED) tương ứng đúng 1 lượt gọi LLM
        llm_calls = sum(1 for log in all_traces if log["action_type"] != "MAX_ITERATIONS_REACHED")
        tool_calls = sum(1 for log in all_traces if log["action_type"] == "TOOL_EXECUTION")

        print(f"\n==================================================")
        print(f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi {completed_count}/{len(run_tests)} Test Cases | {todo_count} Test Cases đang chờ điền câu hỏi (TODO)")
        print(f"🔢 [QUOTA]: {llm_calls} lượt gọi LLM ({provider.model_name}) | {tool_calls} lượt gọi Tool qua MCP Server")
        if llm_error:
            print_llm_error(llm_error)
            print("🛑 Đã dừng Test Suite để không tốn thêm quota. File 'docs/trace_waterfall.json' KHÔNG bị ghi đè.")
        elif selected_ids:
            print("ℹ️ Chế độ chạy chọn lọc (--tc) không ghi đè 'docs/trace_waterfall.json'. Chạy '--all' để lưu trace nộp bài.")
        elif all_traces:
            save_waterfall_trace(all_traces)
        print(f"💡 Để trò chuyện trực tiếp từng câu: Chạy 'python src/app.py --interactive'")
    else:
        # Chế độ mặc định khi chỉ gõ 'python src/app.py'
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG CHƯƠNG TRÌNH:")
        print("  1. Chat trực tiếp liên tục:   python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test Cases:    python src/app.py --all")
        print("  3. Chạy một vài Test Cases:    python src/app.py --tc TC02,TC04\n")

        sample_query = tests[1]["question"]
        print(f"--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra cứu số ngày phép) ---")
        try:
            logs = run_react_agent(sample_query, provider, mcp_server)
            save_waterfall_trace(logs)
        except LLMProviderError as e:
            print_llm_error(e)
        print("\n💡 Hãy thử ngay lệnh: python src/app.py --interactive để chat trực tiếp!")
