import frappe

from frappe.utils import add_days, get_datetime, now_datetime

from hrms.hr.utils import calculate_working_hours_by_holiday_list


def _parse_statuses(status):
    if not status:
        return []

    # Support JSON array string from client
    if isinstance(status, str):
        status_str = status.strip()
        if not status_str:
            return []
        try:
            parsed = frappe.parse_json(status_str)
            if isinstance(parsed, (list, tuple, set)):
                return [str(s).strip() for s in parsed if str(s).strip()]
        except Exception:
            pass

        # Support comma/newline separated string
        parts = []
        for chunk in status_str.replace("\n", ",").split(","):
            v = chunk.strip()
            if v:
                parts.append(v)
        return parts

    if isinstance(status, (list, tuple, set)):
        return [str(s).strip() for s in status if str(s).strip()]

    return [str(status).strip()] if str(status).strip() else []


def _get_team_label(team: str) -> str:
    row = frappe.get_value("Team", team, ["team_name"], as_dict=True)
    return (row or {}).get("team_name") or team


def _calculate_working_hours(start_dt, end_dt, holiday_list_name: str = "Annual Holiday"):
    total_working_hours, total_holiday = calculate_working_hours_by_holiday_list(
        start_dt, end_dt, holiday_list_name=holiday_list_name
    )
    working_days = total_working_hours / 8 if total_working_hours else 0
    return {
        "working_days": working_days,
        "total_working_hours": total_working_hours,
        "total_holiday": total_holiday,
    }

@frappe.whitelist(allow_guest=True)
def get_subtasks_from_employee(employee_id, start_date=None, end_date=None):
    if not employee_id:
        frappe.throw("employee_id is required")

    # Accept None / empty string from client calls
    start_date = start_date or None
    end_date = end_date or None

    end_dt = get_datetime(end_date) if end_date else now_datetime()
    start_dt = get_datetime(start_date) if start_date else add_days(end_dt, -7)

    if start_dt > end_dt:
        frappe.throw("start_date must be less than or equal to end_date")

    subtasks = frappe.get_all(
        "SubTask",
        filters={
            "pic_subtask": employee_id,
            "subtask_open_date": ["between", [start_dt, end_dt]],
        },
        fields=["name", "subtask_name", "status", "subtask_open_date", "maintask_name", "tasks_name", "description", "target_time_minutes", "value", "priority", "subtask_start_date", "subtask_pause_date", "subtask_done_date", "subtask_close_date", "pic_subtask_name", "pic_subtask", "maintask", "tasks", "created_by", "submission_text", "attachment"],
        order_by="subtask_open_date desc, creation desc",
    )
    return subtasks


@frappe.whitelist(allow_guest=True)
def get_subtask_summary_total_hour_by_team(team, start_date=None, end_date=None, status=None):
    if not team:
        frappe.throw("team is required")

    # Accept None / empty string from client calls
    start_date = start_date or None
    end_date = end_date or None

    end_dt = get_datetime(end_date) if end_date else now_datetime()
    start_dt = get_datetime(start_date) if start_date else add_days(end_dt, -7)

    if start_dt > end_dt:
        frappe.throw("start_date must be less than or equal to end_date")

    team_label = _get_team_label(team)

    # Fetch employees in this team
    emp_filters = {"team": team}
    employees = []
    try:
        employees = frappe.get_all(
            "Employee",
            filters={**emp_filters, "status": "Active"},
            fields=["name", "employee_name", "team"],
            order_by="employee_name asc",
        )
        if not employees:
            employees = frappe.get_all(
                "Employee",
                filters=emp_filters,
                fields=["name", "employee_name", "team"],
                order_by="employee_name asc",
            )
    except Exception:
        employees = frappe.get_all(
            "Employee",
            filters=emp_filters,
            fields=["name", "employee_name", "team"],
            order_by="employee_name asc",
        )

    employees = employees or []
    emp_ids = [e.get("name") for e in employees if e.get("name")]
    if not emp_ids:
        return []

    # Working time meta (based on Holiday List 'Annual Holiday')
    working_meta = _calculate_working_hours(start_dt, end_dt, holiday_list_name="Annual Holiday")
    working_days = working_meta.get("working_days") or 0

    # Fetch subtasks in one query and aggregate in Python
    statuses = _parse_statuses(status)
    rows = frappe.get_all(
        "SubTask",
        filters={
            "pic_subtask": ["in", emp_ids],
            "subtask_open_date": ["between", [start_dt, end_dt]],
            **({"status": ["in", statuses]} if statuses else {}),
        },
        fields=["pic_subtask", "maintask", "tasks", "target_time_minutes"],
        order_by="pic_subtask asc",
    )

    summary_by_emp = {
        e.get("name"): {
            "employee_id": e.get("name"),
            "employee_name": e.get("employee_name") or "-",
            "team": team_label,
            "total_main_task": 0,
            "total_task": 0,
            "total_sub_task": 0,
            "total_hour": 0.0,
            "total_hour_avg_daily": 0.0,
            # internal
            "_maintask_set": set(),
            "_task_set": set(),
            "_total_minutes": 0,
        }
        for e in employees
        if e.get("name")
    }

    for r in rows or []:
        emp_id = r.get("pic_subtask")
        if not emp_id or emp_id not in summary_by_emp:
            continue

        summary = summary_by_emp[emp_id]
        summary["total_sub_task"] += 1
        mt = r.get("maintask")
        if mt:
            summary["_maintask_set"].add(mt)
        tk = r.get("tasks")
        if tk:
            summary["_task_set"].add(tk)
        minutes = r.get("target_time_minutes") or 0
        summary["_total_minutes"] += int(minutes)

    out = []
    for emp_id, summary in summary_by_emp.items():
        summary["total_main_task"] = len(summary.pop("_maintask_set"))
        summary["total_task"] = len(summary.pop("_task_set"))
        total_minutes = summary.pop("_total_minutes")
        total_hours = total_minutes / 60.0
        summary["total_minutes"] = total_minutes
        summary["total_hour"] = round(total_hours, 2)
        summary["total_hour_avg_daily"] = round((total_hours / working_days), 2) if working_days else 0.0
        out.append(summary)

    out.sort(key=lambda x: (x.get("total_hour_avg_daily", 0) or 0), reverse=True)
    return out