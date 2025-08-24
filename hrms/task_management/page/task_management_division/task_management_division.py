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


# === Tambahan: opsi untuk Select Team di toolbar ===
@frappe.whitelist()
def get_team_options():
    """Return list opsi Team: label=team_name (fallback name), value=name (docname)."""
    rows = frappe.get_all("Team", fields=["name", "team_name"])
    return [
        {"label": (r.get("team_name") or r.get("name")), "value": r.get("name")}
        for r in rows
        if r.get("name")
    ]



# === Helper filter berdasarkan Team ===
def _employee_and_user_ids_for_team(team_name: str):
    """Kembalikan (set_employee_id, set_user_id) untuk Employee.team == team_name."""
    if not team_name:
        return set(), set()
    emps = frappe.get_all(
        "Employee",
        filters={"team": team_name},
        fields=["name", "user_id"],
    )
    emp_ids = {e["name"] for e in emps}
    user_ids = {e["user_id"] for e in emps if e.get("user_id")}
    return emp_ids, user_ids


@frappe.whitelist()
def get_team_overview(team: str | None = None):
    STATUS_DONE = {"Done", "Close"}
    STATUS_ONGOING = {"Open", "In Progress"}
    PRIORITY_HIGH = "High"

    # scope maintask berbasis akses user (team/assign_by). SysMgr boleh lihat semua
    # maintask_ids = _maintasks_accessible_by_user()
    # if "System Manager" in frappe.get_roles():
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

    # filter dasar: hanya SubTask dari maintask yang boleh diakses
    subtask_filters_scope = {"maintask": ("in", list(maintask_ids))}

    # === Tambahan: filter TEAM (via Employee.team -> User owner)
    team = (team or "").strip() or None
    team_emp_ids, team_user_ids = set(), set()
    if team:
        team_emp_ids, team_user_ids = _employee_and_user_ids_for_team(team)
        # Jika tidak ada anggota team tsb, langsung kosongkan hasil
        if not team_emp_ids and not team_user_ids:
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
        # Karena SubTask tidak punya link langsung ke Employee, gunakan owner (User)
        subtask_filters_scope["pic_subtask"] = (
            "in",
            list(team_emp_ids) or ["__none__"],
        )

    # hitung quick metrics (ongoing/completed) dengan filter scope
    ongoing_tasks = frappe.db.count(
        "SubTask", {**subtask_filters_scope, "status": ("in", list(STATUS_ONGOING))}
    )
    completed_tasks = frappe.db.count(
        "SubTask", {**subtask_filters_scope, "status": ("in", list(STATUS_DONE))}
    )

    # ambil data rinci untuk agregasi chart
    subtasks = frappe.get_all(
        "SubTask",
        filters=subtask_filters_scope,
        fields=[
            "owner",
            "pic_subtask",
            "pic_subtask_name",
            "status",
            "priority",
            "value",
        ],
    )

    total = len(subtasks)
    completed = sum(1 for s in subtasks if (s.status or "").title() in STATUS_DONE)
    avg_completion_rate = round((completed / total) * 100, 1) if total else 0.0

    val_list = [float(s.value) for s in subtasks if s.get("value") is not None]
    avg_value = round(sum(val_list) / total, 2) if total and val_list else 0.0

    def display_name(s):
        # gunakan PIC SubTask Name jika ada, fallback ke owner
        return (s.get("pic_subtask_name") or s.get("owner") or "Unknown").strip()

    ongoing = defaultdict(int)
    highprio = defaultdict(int)
    value_sum = defaultdict(float)
    total_per = defaultdict(int)
    done_per = defaultdict(int)
    distinct_members = set()

    for s in subtasks:
        n = display_name(s)
        distinct_members.add(n)
        total_per[n] += 1

        st = (s.status or "").title()
        if st in STATUS_DONE:
            done_per[n] += 1
        if st in STATUS_ONGOING:
            ongoing[n] += 1
        if (s.priority or "").title() == PRIORITY_HIGH:
            highprio[n] += 1
        if s.get("value") is not None:
            try:
                value_sum[n] += float(s.value)
            except Exception:
                pass

    # rata2 value per member
    value_avg = {
        k: round(value_sum.get(k, 0.0) / total_per[k], 2)
        for k in total_per
        if total_per[k] > 0
    }
    # completion rate per member
    completion_rate = {
        k: round((done_per.get(k, 0) / total_per[k]) * 100, 1)
        for k in total_per
        if total_per[k] > 0
    }

    def to_chart(d):
        items = sorted(d.items(), key=lambda x: x[1], reverse=True)
        return {"labels": [k for k, _ in items], "values": [v for _, v in items]}

    # total_members:
    # - kalau ada filter team: jumlah member unik berdasarkan data agregasi (lebih akurat untuk scope)
    # - kalau tidak ada filter: tetap pakai perhitungan dari MainTask Team child table
    total_members = (
        len(distinct_members) if team else _distinct_team_members(maintask_ids)
    )

    return {
        "total_members": total_members,
        "ongoing_tasks": ongoing_tasks,
        "completed_tasks": completed_tasks,
        "avg_completion_rate": avg_completion_rate,
        "avg_value": avg_value,
        "ongoing_per_member": to_chart(ongoing),
        "value_per_member": to_chart(value_avg),
        "completion_rate_per_member": to_chart(completion_rate),
        "high_priority_per_member": to_chart(highprio),
    }
