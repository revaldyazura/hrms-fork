import frappe
from collections import defaultdict

TEAM_CHILD = "MainTask Team"  # child table name
ASSIGN_BY_CHILD = "MainTask Assign By"  # child table name

# Sesuaikan nama field di child table berikut:
TEAM_EMPLOYEE_FIELD = "employee"  # Link ke Employee
ASSIGN_BY_EMPLOYEE_FIELD = "employee"  # Link ke Employee

# === New: overview by Employee (for individual page filter) ===
@frappe.whitelist()
def get_employee_overview(
    employee: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Aggregate SubTask metrics for a single Employee (pic_subtask).

    Returns metrics and per-MainTask charts:
    - ongoing_tasks, completed_tasks, high_priority_tasks
    - avg_completion_rate (overall), avg_value (overall)
    - ongoing_per_maintask, value_per_maintask, completion_rate_per_maintask, high_priority_per_maintask
    """
    STATUS_DONE = {"Done", "Close"}
    STATUS_ONGOING = {"Open", "In Progress"}
    PRIORITY_HIGH = "High"

    # if no employee provided, return empty dataset
    employee = (employee or "").strip() or None
    if not employee:
        return {
            "ongoing_tasks": 0,
            "completed_tasks": 0,
            "high_priority_tasks": 0,
            "avg_completion_rate": 0.0,
            "avg_value": 0.0,
            "ongoing_per_maintask": {"labels": [], "values": []},
            "value_per_maintask": {"labels": [], "values": []},
            "completion_rate_per_maintask": {"labels": [], "values": []},
            "high_priority_per_maintask": {"labels": [], "values": []},
        }

    subtask_filters = {"pic_subtask": employee}

    # Apply date filters on subtask_open_date if provided
    start_date = (start_date or "").strip() or None
    end_date = (end_date or "").strip() or None
    if start_date and end_date:
        # Only apply date filter when both dates are provided
        subtask_filters["subtask_open_date"] = ("between", [start_date, end_date])

    # quick counts
    ongoing_tasks = frappe.db.count(
        "SubTask", {**subtask_filters, "status": ("in", list(STATUS_ONGOING))}
    )
    completed_tasks = frappe.db.count(
        "SubTask", {**subtask_filters, "status": ("in", list(STATUS_DONE))}
    )
    high_priority_tasks = frappe.db.count(
        "SubTask", {**subtask_filters, "priority": PRIORITY_HIGH}
    )

    # detailed records for aggregation per MainTask
    subtasks = frappe.get_all(
        "SubTask",
        filters=subtask_filters,
        fields=[
            "maintask",
            "maintask_name",
            "tasks_name",
            "status",
            "priority",
            "value",
            "subtask_name",
            "subtask_open_date",
            "subtask_done_date",
        ],
    )

    total = len(subtasks)
    done = 0
    val_list = []

    from collections import defaultdict

    ongoing_mt = defaultdict(int)
    highprio_mt = defaultdict(int)
    value_sum_mt = defaultdict(float)
    total_per_mt = defaultdict(int)
    done_per_mt = defaultdict(int)

    def mt_label(row):
        return (row.get("maintask_name") or row.get("maintask") or "Unknown").strip()

    for s in subtasks:
        lbl = mt_label(s)
        total_per_mt[lbl] += 1

        st = (s.get("status") or "").strip()
        if st in STATUS_DONE:
            done += 1
            done_per_mt[lbl] += 1
        if st in STATUS_ONGOING:
            ongoing_mt[lbl] += 1

        if (s.get("priority") or "").strip() == PRIORITY_HIGH:
            highprio_mt[lbl] += 1

        if s.get("value") is not None:
            try:
                v = float(s.get("value"))
                val_list.append(v)
                value_sum_mt[lbl] += v
            except Exception:
                pass

    avg_completion_rate = round((done / total) * 100, 1) if total else 0.0
    avg_value = round(sum(val_list) / total, 2) if (total and val_list) else 0.0

    value_avg_mt = {
        k: round(value_sum_mt.get(k, 0.0) / total_per_mt[k], 2)
        for k in total_per_mt
        if total_per_mt[k] > 0
    }
    completion_rate_mt = {
        k: round((done_per_mt.get(k, 0) / total_per_mt[k]) * 100, 1)
        for k in total_per_mt
        if total_per_mt[k] > 0
    }

    def to_chart(d):
        items = sorted(d.items(), key=lambda x: x[1], reverse=True)
        return {"labels": [k for k, _ in items], "values": [v for _, v in items]}

    # build simple table rows for UI
    current_rows = [
        {
            "maintask_name": s.get("maintask_name"),
            "tasks_name": s.get("tasks_name"),
            "subtask_name": s.get("subtask_name"),
            "priority": s.get("priority"),
            "status": s.get("status"),
            "open_date": s.get("subtask_open_date"),
            "done_date": s.get("subtask_done_date"),
        }
        for s in subtasks
    ]

    return {
        "ongoing_tasks": ongoing_tasks,
        "completed_tasks": completed_tasks,
        "high_priority_tasks": high_priority_tasks,
        "avg_completion_rate": avg_completion_rate,
        "avg_value": avg_value,
        "ongoing_per_maintask": to_chart(ongoing_mt),
        "value_per_maintask": to_chart(value_avg_mt),
        "completion_rate_per_maintask": to_chart(completion_rate_mt),
        "high_priority_per_maintask": to_chart(highprio_mt),
        "current_subtasks": current_rows,
    }
