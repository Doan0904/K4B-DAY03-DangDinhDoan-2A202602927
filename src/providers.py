"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.
"""

import os
import re
import sys
import json
import time
from datetime import date
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

MAX_API_RETRIES = 3
MAX_RETRY_WAIT_SECONDS = 60


class LLMProviderError(RuntimeError):
    """Lỗi khi gọi LLM API thật (hết quota, sai tên model, sai API key, mất kết nối...)"""


def get_retry_delay_seconds(error: Exception, attempt: int = 0) -> Optional[float]:
    """
    Trả về số giây nên chờ trước khi thử lại; None nếu không nên thử lại.
    - 429 theo phút: chờ đúng retryDelay Google trả về.
    - 429 theo ngày: không thử lại (phải chờ quota reset).
    - 503/500 (server quá tải hoặc lỗi tạm thời): chờ tăng dần 5s, 10s, 20s.
    """
    message = str(error)
    if "429" in message and "RESOURCE_EXHAUSTED" in message:
        if "PerDay" in message:
            return None
        match = re.search(r"retry in ([\d.]+)s", message)
        delay = float(match.group(1)) + 1 if match else 30.0
        return delay if delay <= MAX_RETRY_WAIT_SECONDS else None
    if re.search(r"\b(500|503)\b", message) or "UNAVAILABLE" in message:
        return min(5.0 * (2 ** attempt), MAX_RETRY_WAIT_SECONDS)
    return None


def call_with_retry(api_call, provider_name: str):
    """Gọi API, tự chờ và thử lại khi gặp lỗi tạm thời (giới hạn theo phút, server quá tải)"""
    for attempt in range(MAX_API_RETRIES + 1):
        try:
            return api_call()
        except Exception as e:
            delay = get_retry_delay_seconds(e, attempt)
            if delay is None or attempt == MAX_API_RETRIES:
                raise
            reason = "chạm giới hạn request theo phút" if "429" in str(e) else "server đang quá tải hoặc lỗi tạm thời"
            print(f"⏳ [{provider_name}]: {reason}, chờ {delay:.0f}s rồi thử lại ({attempt + 1}/{MAX_API_RETRIES})...")
            time.sleep(delay)

class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "", history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        history: các bước ReAct đã thực thi, mỗi phần tử là
          - {"type": "tool", "tool_name", "arguments", "observation", "provider_state"}
          - {"type": "correction", "content", "instruction", "provider_state"}
        provider_state là dữ liệu gốc do chính provider trả về ở lượt trước (ví dụ Content kèm thought signature của Gemini).
        """
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider mô phỏng Agent Nhân sự VinFast để chạy thử mà không tốn API Key"""
    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return f"[Mock Chatbot Response]: Xin chào! Tôi đã nhận được câu hỏi '{prompt}'. (Chế độ Chatbot không có Tool tra cứu dữ liệu thời gian thực)."

    @staticmethod
    def _text(content: str, thought: str) -> Dict[str, Any]:
        return {"type": "text", "content": f"[Mock Agent Response]: {content}", "thought": thought}

    @staticmethod
    def _parse_leave_request(query: str, employee_id: str) -> Dict[str, Any]:
        """Trích xuất tham số tạo đơn: '20/10/2026 ... 21/10/2026' hoặc 'ngày 25 và 26 tháng này'"""
        today = date.today()
        days = []
        try:
            full_dates = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", query)
            if full_dates:
                days = [date(int(y), int(m), int(d)) for d, m, y in full_dates]
            else:
                match = re.search(r"ngày\s+(\d{1,2})(?:\s*(?:và|đến|-)\s*(?:ngày\s+)?(\d{1,2}))?", query)
                if match:
                    days = [date(today.year, today.month, int(d)) for d in match.groups() if d]
        except ValueError:
            days = []
        start, end = (min(days), max(days)) if days else (today, today)

        if "ốm" in query:
            leave_type = "sick_leave"
        elif "không lương" in query:
            leave_type = "unpaid_leave"
        else:
            leave_type = "annual_leave"
        reason = re.search(r"lý do\s+(.+?)[.!?]*$", query)
        return {
            "employee_id": employee_id,
            "leave_type": leave_type,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reason": reason.group(1).strip() if reason else "việc cá nhân"
        }

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "", history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        # Đọc các bước Tool đã thực thi từ lịch sử do ReAct Loop nạp vào
        query = prompt.strip().lower()
        tool_steps = [item for item in (history or []) if item.get("type") == "tool"]
        called_tools = [item["tool_name"] for item in tool_steps]
        observations = [item["observation"] for item in tool_steps]

        # Observation báo lỗi (ví dụ NOT_FOUND) -> dừng lại và thông báo, không bịa dữ liệu
        for obs in observations:
            if obs.get("status") != "SUCCESS":
                return self._text(
                    obs.get("message") or "Không thể xử lý yêu cầu do công cụ trả về lỗi.",
                    f"Observation trả về trạng thái {obs.get('status')}, dừng lại và thông báo cho người dùng."
                )

        employee = re.search(r"vf\d+", query)
        if not employee:
            if "phép" in query or "nghỉ" in query:
                return self._text(
                    "Theo quy định của VinFast, nhân viên chính thức có 12 ngày phép năm hưởng nguyên lương. "
                    "Đơn nghỉ phép năm cần gửi trên hệ thống HR trước ít nhất 3 ngày làm việc và được Quản lý trực tiếp phê duyệt.",
                    "Câu hỏi chung về chính sách nghỉ phép, trả lời trực tiếp không cần gọi Tool."
                )
            return self._text(
                "Xin lỗi, tôi chỉ hỗ trợ tra cứu ngày phép, quyền lợi bảo hiểm và tạo đơn nghỉ phép. "
                "Với các vấn đề khác (ví dụ lương thưởng), vui lòng liên hệ Quản lý trực tiếp hoặc phòng Nhân sự.",
                "Câu hỏi nằm ngoài phạm vi công cụ và quy định hiện có, không suy đoán câu trả lời."
            )
        employee_id = employee.group().upper()

        # Mô phỏng lập kế hoạch: xác định các Tool cần gọi theo thứ tự
        plan = []
        if "còn" in query or "số ngày phép" in query or "kiểm tra" in query:
            plan.append(("check_leave_balance", {"employee_id": employee_id}))
        if "bảo hiểm" in query or "quyền lợi" in query:
            plan.append(("query_employee_benefits", {"employee_id": employee_id}))
        if "tạo" in query and "đơn" in query:
            plan.append(("create_leave_request", self._parse_leave_request(query, employee_id)))

        if not plan:
            return self._text(
                f"Bạn cần tra cứu ngày phép, quyền lợi bảo hiểm hay tạo đơn nghỉ phép cho mã nhân viên {employee_id}?",
                "Chưa xác định được nhu cầu cụ thể, hỏi lại người dùng."
            )

        for tool_name, arguments in plan:
            if tool_name in called_tools:
                continue
            if tool_name == "create_leave_request":
                balance = next((o["leave_balance"] for o in observations if "leave_balance" in o), None)
                days_requested = (date.fromisoformat(arguments["end_date"]) - date.fromisoformat(arguments["start_date"])).days + 1
                if balance and arguments["leave_type"] == "annual_leave" and balance["remaining"] < days_requested:
                    return self._text(
                        f"Nhân viên {employee_id} chỉ còn {balance['remaining']} ngày phép năm, không đủ cho {days_requested} ngày nghỉ. "
                        "Bạn có muốn đăng ký nghỉ không lương thay thế không?",
                        "Số ngày phép còn lại không đủ điều kiện, không tạo đơn phép năm."
                    )
            return {
                "type": "tool_call",
                "tool_name": tool_name,
                "arguments": arguments,
                "thought": f"Cần gọi tool {tool_name} để lấy dữ liệu cho mã nhân viên {employee_id}."
            }

        # Đã đủ Observation cho mọi bước trong kế hoạch -> tổng hợp Final Answer
        return self._text(
            " ".join(o.get("message", "") for o in observations),
            "Đã có đủ dữ liệu từ các Observation, tổng hợp câu trả lời cuối cùng."
        )


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-3.5-flash"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    @staticmethod
    def keep_first_function_call(content):
        """Chỉ giữ lời gọi Tool đầu tiên (ReAct Loop thực thi từng Tool một), bỏ các lời gọi song song còn lại"""
        from google.genai import types

        parts, seen_call = [], False
        for part in content.parts or []:
            if part.function_call:
                if seen_call:
                    continue
                seen_call = True
            parts.append(part)
        return types.Content(role=content.role or "model", parts=parts)

    @staticmethod
    def build_contents(prompt: str, history: Optional[List[Dict[str, Any]]] = None) -> list:
        """
        Dựng hội thoại Native Tool Calling cho Gemini:
        user prompt -> [model function_call -> user function_response]* -> ...
        Gửi lại nguyên nội dung model đã trả về (kèm thought signature) theo yêu cầu của Gemini 3.
        """
        from google.genai import types

        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        for item in history or []:
            # Chỉ dùng lại provider_state do chính Gemini trả về (Content kèm thought signature)
            model_turn = item.get("provider_state") if isinstance(item.get("provider_state"), types.Content) else None
            if item.get("type") == "tool":
                if model_turn is None:
                    model_turn = types.Content(role="model", parts=[
                        types.Part.from_function_call(name=item["tool_name"], args=item["arguments"])
                    ])
                observation = item["observation"] if isinstance(item["observation"], dict) else {"result": item["observation"]}
                contents.append(model_turn)
                contents.append(types.Content(role="user", parts=[
                    types.Part.from_function_response(name=item["tool_name"], response=observation)
                ]))
            elif item.get("type") == "correction":
                if model_turn is None:
                    model_turn = types.Content(role="model", parts=[types.Part.from_text(text=item["content"])])
                contents.append(model_turn)
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=item["instruction"])]))
        return contents

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "", history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                temperature=0.2
            )

            # Nạp lịch sử dưới dạng function_call / function_response thay vì ghép thành văn bản
            contents = self.build_contents(prompt, history)
            response = call_with_retry(
                lambda: client.models.generate_content(model=self.model_name, contents=contents, config=config),
                provider_name="Gemini"
            )
            model_turn = response.candidates[0].content if response.candidates else None

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if call.args else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought": f"Gemini quyết định gọi công cụ '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}",
                    "provider_state": self.keep_first_function_call(model_turn) if model_turn else None
                }
            return {
                "type": "text",
                "content": response.text or "",
                "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ).",
                "provider_state": model_turn
            }

        except Exception as e:
            raise LLMProviderError(f"Gemini API lỗi với model '{self.model_name}': {e}") from e

class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    @staticmethod
    def build_messages(prompt: str, system_prompt: str = "", history: Optional[List[Dict[str, Any]]] = None) -> list:
        """Dựng hội thoại Native Tool Calling cho OpenAI: user -> [assistant tool_calls -> tool]* -> ..."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for index, item in enumerate(history or []):
            if item.get("type") == "tool":
                provider_state = item.get("provider_state") if isinstance(item.get("provider_state"), dict) else {}
                call_id = provider_state.get("tool_call_id") or f"call_{index}"
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": call_id,
                        "type": "function",
                        "function": {"name": item["tool_name"], "arguments": json.dumps(item["arguments"], ensure_ascii=False)}
                    }]
                })
                messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(item["observation"], ensure_ascii=False)})
            elif item.get("type") == "correction":
                messages.append({"role": "assistant", "content": item["content"]})
                messages.append({"role": "user", "content": item["instruction"]})
        return messages

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "", history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            response = client.chat.completions.create(
                model=self.model_name,
                messages=self.build_messages(prompt, system_prompt, history),
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought": f"OpenAI quyết định gọi công cụ '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}",
                    "provider_state": {"tool_call_id": call.id}
                }
            return {
                "type": "text",
                "content": msg.content or "",
                "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi công cụ).",
                "provider_state": None
            }
        except Exception as e:
            raise LLMProviderError(f"OpenAI API lỗi với model '{self.model_name}': {e}") from e

def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key and key != "your_gemini_api_key_here":
            return GeminiProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key != "your_openai_api_key_here":
            return OpenAIProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
