"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND
Mã nguồn chứa danh sách Tool Schemas (JSON Schema) và Execution Layer phục vụ cho MCP Server.
"""

import json
from datetime import datetime
from typing import Dict, Any

# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA (TASK 1.2)
# ==============================================================================

TOOLS_SCHEMA = [
    # Tool 1: Đã được định nghĩa mẫu sẵn cho Học viên tham khảo
    {
        "name": "academic_query",
        "description": "Tra cứu hồ sơ và thông tin học vụ của sinh viên VinUni bằng mã sinh viên.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần tra cứu (ví dụ: 'SV2026001')"
                }
            },
            "required": ["student_id"]
        }
    },

    # --------------------------------------------------------------------------
    # TODO 1.2: HỌC VIÊN HOÀN THIỆN TOOL SCHEMA CHO 'schedule_appointment'
    # 🎯 YÊU CẦU THIẾT KẾ SCHEMA (JSON SCHEMA STANDARD):
    # 1. Tool dùng để đặt lịch hẹn tư vấn học vụ với Cố vấn học tập VinUni.
    # 2. Thiết kế các tham số (properties) để LLM trích xuất:
    #    - student_id (string): Mã sinh viên cần đặt lịch (ví dụ: 'SV2026001')
    #    - datetime_str (string): Thời gian hẹn (ví dụ: '14:00 15/09/2026')
    #    - advisor_name (string): Tên cố vấn học tập
    # 3. Khai báo danh sách các trường bắt buộc (required).
    # --------------------------------------------------------------------------
    {
        "name": "schedule_appointment",
        "description": "Đặt lịch hẹn tư vấn học vụ với Cố vấn học tập VinUni.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần đặt lịch hẹn (ví dụ: 'SV2026001')"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời gian hẹn theo định dạng 'HH:MM DD/MM/YYYY' (ví dụ: '14:00 15/09/2026')"
                },
                "advisor_name": {
                    "type": "string",
                    "description": "Họ tên đầy đủ kèm học hàm/học vị của Cố vấn học tập (ví dụ: 'PGS.TS Nguyễn Văn A'). Nếu người dùng không nêu, hãy tra cứu bằng academic_query trước."
                }
            },
            "required": ["student_id", "datetime_str", "advisor_name"]
        }
    },

    # --------------------------------------------------------------------------
    # TOOLS CHO ĐỀ TÀI: TRỢ LÝ NHÂN SỰ VINFAST (HR ASSISTANT)
    # --------------------------------------------------------------------------
    {
        "name": "check_leave_balance",
        "description": "Tra cứu số ngày phép năm (tổng, đã dùng, còn lại) của nhân viên VinFast bằng mã nhân viên. Dùng khi cần biết nhân viên còn đủ ngày phép hay không.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "Mã nhân viên VinFast cần tra cứu (ví dụ: 'VF2026001')"
                }
            },
            "required": ["employee_id"]
        }
    },
    {
        "name": "query_employee_benefits",
        "description": "Tra cứu quyền lợi phúc lợi của nhân viên VinFast: gói bảo hiểm sức khỏe Vinmec, bảo hiểm xã hội, chế độ nghỉ ốm và thai sản.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "Mã nhân viên VinFast cần tra cứu (ví dụ: 'VF2026001')"
                }
            },
            "required": ["employee_id"]
        }
    },
    {
        "name": "create_leave_request",
        "description": "Tạo đơn xin nghỉ phép cho nhân viên VinFast và gửi lên hệ thống HR để Quản lý trực tiếp phê duyệt.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "Mã nhân viên VinFast tạo đơn (ví dụ: 'VF2026001')"
                },
                "leave_type": {
                    "type": "string",
                    "enum": ["annual_leave", "sick_leave", "unpaid_leave"],
                    "description": "Loại nghỉ: 'annual_leave' (phép năm), 'sick_leave' (nghỉ ốm), 'unpaid_leave' (nghỉ không lương)"
                },
                "start_date": {
                    "type": "string",
                    "description": "Ngày bắt đầu nghỉ, định dạng YYYY-MM-DD (ví dụ: '2026-10-20')"
                },
                "end_date": {
                    "type": "string",
                    "description": "Ngày kết thúc nghỉ (tính cả ngày này), định dạng YYYY-MM-DD (ví dụ: '2026-10-21')"
                },
                "reason": {
                    "type": "string",
                    "description": "Lý do xin nghỉ (ví dụ: 'giải quyết việc gia đình')"
                }
            },
            "required": ["employee_id", "leave_type", "start_date", "end_date", "reason"]
        }
    }
]

# ==============================================================================
# 2. MÔ PHỎNG DỮ LIỆU & HÀM THỰC THI TOOL (EXECUTION LAYER)
# ==============================================================================

MOCK_DATABASE = {
    "SV2026001": {
        "full_name": "Nguyễn Văn An",
        "class": "AI-K4",
        "gpa": 3.85,
        "email": "an.nv@vinuni.edu.vn",
        "status": "Đang học",
        "advisor": "PGS.TS Nguyễn Văn A"
    },
    "SV2026002": {
        "full_name": "Trần Thị Bình",
        "class": "AI-K4",
        "gpa": 3.60,
        "email": "binh.tt@vinuni.edu.vn",
        "status": "Đang học",
        "advisor": "TS. Lê Thị B"
    }
}


def execute_academic_query(student_id: str) -> str:
    """Thực thi tra cứu học vụ theo mã sinh viên"""
    student = MOCK_DATABASE.get(student_id.strip().upper())
    if student:
        return json.dumps({
            "status": "SUCCESS",
            "student_id": student_id,
            "data": student
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy dữ liệu sinh viên có mã '{student_id}'"
        }, ensure_ascii=False)


def execute_schedule_appointment(student_id: str, datetime_str: str, advisor_name: str = "PGS.TS Nguyễn Văn A") -> str:
    """Thực thi đặt lịch hẹn tư vấn học vụ"""
    return json.dumps({
        "status": "SUCCESS",
        "booking_id": f"BK-{student_id}-99",
        "student_id": student_id,
        "datetime": datetime_str,
        "advisor": advisor_name,
        "message": f"Đặt lịch thành công cho sinh viên {student_id} với {advisor_name} vào lúc {datetime_str}."
    }, ensure_ascii=False)


# ------------------------------------------------------------------------------
# DỮ LIỆU NHÂN SỰ GIẢ LẬP & HÀM THỰC THI (ĐỀ TÀI HR VINFAST)
# ------------------------------------------------------------------------------

HEALTH_INSURANCE_PACKAGES = {
    "VinFast Care Gold": {
        "provider": "Vinmec",
        "inpatient_limit_vnd": 200000000,
        "outpatient_limit_vnd": 20000000,
        "coverage": [
            "Khám và điều trị nội trú, ngoại trú tại hệ thống Vinmec",
            "Khám sức khỏe định kỳ 1 lần/năm",
            "Nha khoa cơ bản"
        ]
    },
    "VinFast Care Silver": {
        "provider": "Vinmec",
        "inpatient_limit_vnd": 100000000,
        "outpatient_limit_vnd": 10000000,
        "coverage": [
            "Khám và điều trị nội trú, ngoại trú tại hệ thống Vinmec",
            "Khám sức khỏe định kỳ 1 lần/năm"
        ]
    }
}

COMMON_BENEFITS = {
    "social_insurance": "Đóng BHXH, BHYT, BHTN đầy đủ theo quy định pháp luật.",
    "sick_leave": "Hưởng chế độ ốm đau theo Luật BHXH, cần nộp giấy xác nhận của cơ sở y tế.",
    "maternity_leave": "Nghỉ thai sản 6 tháng theo Luật BHXH, cần nộp giấy chứng sinh hoặc giấy xác nhận của cơ sở y tế."
}

MOCK_EMPLOYEES = {
    "VF2026001": {
        "full_name": "Lê Hoàng Nam",
        "department": "Khối Phần mềm & AI",
        "position": "Kỹ sư AI",
        "annual_leave_total": 12,
        "annual_leave_used": 4,
        "health_insurance_package": "VinFast Care Gold"
    },
    "VF2026002": {
        "full_name": "Nguyễn Thu Hà",
        "department": "Khối Sản xuất",
        "position": "Kỹ sư Chất lượng",
        "annual_leave_total": 12,
        "annual_leave_used": 11,
        "health_insurance_package": "VinFast Care Silver"
    }
}

LEAVE_TYPES = {
    "annual_leave": "nghỉ phép năm",
    "sick_leave": "nghỉ ốm",
    "unpaid_leave": "nghỉ không lương"
}


def _employee_not_found(employee_id: str) -> str:
    return json.dumps({
        "status": "NOT_FOUND",
        "message": f"Không tìm thấy hồ sơ nhân sự có mã nhân viên '{employee_id}'."
    }, ensure_ascii=False)


def _invalid_input(message: str) -> str:
    return json.dumps({"status": "INVALID_INPUT", "message": message}, ensure_ascii=False)


def execute_check_leave_balance(employee_id: str) -> str:
    """Thực thi tra cứu số ngày phép năm còn lại của nhân viên"""
    emp_id = employee_id.strip().upper()
    employee = MOCK_EMPLOYEES.get(emp_id)
    if not employee:
        return _employee_not_found(employee_id)

    total = employee["annual_leave_total"]
    used = employee["annual_leave_used"]
    remaining = total - used
    return json.dumps({
        "status": "SUCCESS",
        "employee_id": emp_id,
        "full_name": employee["full_name"],
        "leave_balance": {"total": total, "used": used, "remaining": remaining},
        "message": f"Nhân viên {employee['full_name']} ({emp_id}) còn {remaining}/{total} ngày phép năm."
    }, ensure_ascii=False)


def execute_query_employee_benefits(employee_id: str) -> str:
    """Thực thi tra cứu quyền lợi bảo hiểm & phúc lợi của nhân viên"""
    emp_id = employee_id.strip().upper()
    employee = MOCK_EMPLOYEES.get(emp_id)
    if not employee:
        return _employee_not_found(employee_id)

    package_name = employee["health_insurance_package"]
    return json.dumps({
        "status": "SUCCESS",
        "employee_id": emp_id,
        "full_name": employee["full_name"],
        "benefits": {
            "health_insurance": {"package": package_name, **HEALTH_INSURANCE_PACKAGES[package_name]},
            **COMMON_BENEFITS
        },
        "message": f"Nhân viên {employee['full_name']} ({emp_id}) được hưởng gói bảo hiểm sức khỏe {package_name} tại Vinmec."
    }, ensure_ascii=False)


def execute_create_leave_request(employee_id: str, leave_type: str, start_date: str, end_date: str, reason: str) -> str:
    """Thực thi tạo đơn xin nghỉ phép (trạng thái chờ phê duyệt)"""
    emp_id = employee_id.strip().upper()
    employee = MOCK_EMPLOYEES.get(emp_id)
    if not employee:
        return _employee_not_found(employee_id)

    if leave_type not in LEAVE_TYPES:
        return _invalid_input(f"Loại nghỉ '{leave_type}' không hợp lệ. Chỉ chấp nhận: {', '.join(LEAVE_TYPES)}.")

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return _invalid_input("Ngày nghỉ phải theo định dạng YYYY-MM-DD.")
    if end < start:
        return _invalid_input("Ngày kết thúc không được trước ngày bắt đầu.")

    days_requested = (end - start).days + 1
    remaining = employee["annual_leave_total"] - employee["annual_leave_used"]
    if leave_type == "annual_leave" and days_requested > remaining:
        return json.dumps({
            "status": "INSUFFICIENT_BALANCE",
            "employee_id": emp_id,
            "days_requested": days_requested,
            "remaining": remaining,
            "message": f"Nhân viên {employee['full_name']} chỉ còn {remaining} ngày phép năm, không đủ cho {days_requested} ngày nghỉ. Có thể đăng ký 'unpaid_leave' (nghỉ không lương)."
        }, ensure_ascii=False)

    request_id = f"LR-{emp_id}-{start:%Y%m%d}"
    return json.dumps({
        "status": "SUCCESS",
        "request_id": request_id,
        "approval_status": "PENDING_APPROVAL",
        "employee_id": emp_id,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "days_requested": days_requested,
        "reason": reason,
        "message": (
            f"Đã tạo đơn {LEAVE_TYPES[leave_type]} {days_requested} ngày "
            f"({start:%d/%m/%Y} - {end:%d/%m/%Y}) cho nhân viên {employee['full_name']} ({emp_id}), "
            f"mã đơn {request_id}, đang chờ Quản lý trực tiếp phê duyệt."
        )
    }, ensure_ascii=False)


# Router gọi tool thực tế
TOOL_ROUTER = {
    "academic_query": execute_academic_query,
    "schedule_appointment": execute_schedule_appointment,
    "check_leave_balance": execute_check_leave_balance,
    "query_employee_benefits": execute_query_employee_benefits,
    "create_leave_request": execute_create_leave_request
}

def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool"""
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({"status": "EXECUTION_ERROR", "error": str(e)}, ensure_ascii=False)
    return json.dumps({"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại!"}, ensure_ascii=False)
