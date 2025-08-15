import frappe
from collections import defaultdict

TEAM_CHILD = "MainTask Team"  # child table name
ASSIGN_BY_CHILD = "MainTask Assign By"  # child table name

# Sesuaikan nama field di child table berikut:
TEAM_EMPLOYEE_FIELD = "employee"  # Link ke Employee
ASSIGN_BY_EMPLOYEE_FIELD = "employee"  # Link ke Employee


def _get_employee_ids_of_current_user():
    """Ambil semua Employee milik user aktif (kalau 1:1 biasanya 1 record)."""
    user = frappe.session.user
    emps = frappe.get_all("Employee", filters={"user_id": user}, pluck="name")
    return set(emps)


def _maintasks_accessible_by_user():
    """Kembalikan set nama MainTask yg berisi user sebagai team atau assign_by."""
    emp_ids = _get_employee_ids_of_current_user()
    if not emp_ids:
        return set()  # kalau user belum terhubung ke Employee

    # Cari parent (MainTask) dari child table team
    team_rows = frappe.get_all(
        TEAM_CHILD,
        filters={TEAM_EMPLOYEE_FIELD: ("in", list(emp_ids))},
        fields=["parent"],
        distinct=True,
    )
    assign_rows = frappe.get_all(
        ASSIGN_BY_CHILD,
        filters={ASSIGN_BY_EMPLOYEE_FIELD: ("in", list(emp_ids))},
        fields=["parent"],
        distinct=True,
    )
    parents = {r["parent"] for r in team_rows} | {r["parent"] for r in assign_rows}
    return parents


def _distinct_team_members(maintask_ids):
    """Hitung anggota tim unik dari maintask terpilih (untuk metric Total Team Members)."""
    if not maintask_ids:
        return 0
    rows = frappe.get_all(
        TEAM_CHILD,
        filters={"parent": ("in", list(maintask_ids))},
        fields=[TEAM_EMPLOYEE_FIELD],
    )
    return len({r[TEAM_EMPLOYEE_FIELD] for r in rows if r.get(TEAM_EMPLOYEE_FIELD)})


@frappe.whitelist()
def get_team_overview():
    STATUS_DONE = {"Done", "Close"}
    STATUS_ONGOING = {"Open", "In Progress"}
    PRIORITY_HIGH = "High"

    maintask_ids = _maintasks_accessible_by_user()
    if "System Manager" in frappe.get_roles():
        maintask_ids = set(frappe.get_all("MainTask", pluck="name"))

    if not maintask_ids:

        return {
            "total_members": 0,
            "ongoing_tasks": 0,
            "completed_tasks": 0,
            "avg_completion_rate": 0.0,
            "avg_value": 0.0,
            "ongoing_per_member": {"labels": [], "values": []},
            "value_per_member": {"labels": [], "values": []},
            "completion_rate_per_member": {"labels": [], "values": []},
            "high_priority_per_member": {"labels": [], "values": []},
        }

    total_members = _distinct_team_members(maintask_ids)
    subtask_filters_scope = {"maintask": ("in", list(maintask_ids))}
    ongoing_tasks = frappe.db.count(
        "SubTask", {**subtask_filters_scope, "status": ("in", list(STATUS_ONGOING))}
    )
    completed_tasks = frappe.db.count(
        "SubTask", {**subtask_filters_scope, "status": ("in", list(STATUS_DONE))}
    )

    subtasks = frappe.get_all(
        "SubTask",
        filters=subtask_filters_scope,
        fields=["owner", "pic_subtask_name", "status", "priority", "value"],
    )

    total = len(subtasks)
    completed = sum(1 for s in subtasks if (s.status or "").title() in STATUS_DONE)
    avg_completion_rate = round((completed / total) * 100, 1) if total else 0.0

    comp_vals = [float(s.value) for s in subtasks if s.get("value") is not None]
    avg_value = round(sum(comp_vals) / total, 2) if total and comp_vals else 0.0

    def name(s):  # tampilkan PIC name jika ada
        return (s.get("pic_subtask_name") or s.get("owner") or "Unknown").strip()

    ongoing = defaultdict(int)
    highprio = defaultdict(int)
    comp_sum = defaultdict(float)
    total_per = defaultdict(int)
    done_per = defaultdict(int)

    for s in subtasks:
        n = name(s)
        total_per[n] += 1
        if (s.status or "").title() in STATUS_DONE:
            done_per[n] += 1
        if (s.status or "").title() in STATUS_ONGOING:
            ongoing[n] += 1
        if (s.priority or "").title() == PRIORITY_HIGH:
            highprio[n] += 1
        if s.get("value") is not None:
            try:
                comp_sum[n] += float(s.value)
            except:
                pass

    completion_rate = {
        k: round((done_per.get(k, 0) / total_per[k]) * 100, 1)
        for k in total_per
        if total_per[k] > 0
    }
    comp_avg = {
        k: round(comp_sum.get(k, 0.0) / total_per[k], 2)
        for k in total_per
        if total_per[k] > 0
    }

    def to_chart(d):
        items = sorted(d.items(), key=lambda x: x[1], reverse=True)
        return {"labels": [k for k, _ in items], "values": [v for _, v in items]}

    return {
        "total_members": total_members,
        "ongoing_tasks": ongoing_tasks,
        "completed_tasks": completed_tasks,
        "avg_completion_rate": avg_completion_rate,
        "avg_value": avg_value,
        "ongoing_per_member": to_chart(ongoing),
        "value_per_member": to_chart(comp_avg),
        "completion_rate_per_member": to_chart(completion_rate),
        "high_priority_per_member": to_chart(highprio),
    }
