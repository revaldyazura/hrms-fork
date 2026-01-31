import frappe
from frappe import _

def get_team_members_map():
    team_data = frappe.db.sql("""
        SELECT
            mteam.parent AS main_task,
            GROUP_CONCAT(emp.employee_name SEPARATOR ', ') AS members
        FROM `tabMainTask Team` mteam
        LEFT JOIN `tabEmployee` emp ON mteam.employee = emp.name
        GROUP BY mteam.parent
    """, as_dict=True)

    return {row["main_task"]: row["members"] for row in team_data}

def get_assign_by_map():
    assign_by_data = frappe.db.sql("""
        SELECT
            m_assign_by.parent AS main_task,
            GROUP_CONCAT(emp.employee_name SEPARATOR ', ') AS assign_by_members
        FROM `tabMainTask Assign By` m_assign_by
        LEFT JOIN `tabEmployee` emp ON m_assign_by.employee = emp.name
        GROUP BY m_assign_by.parent
    """, as_dict=True)

    return {row["main_task"]: row["assign_by_members"] for row in assign_by_data}

def execute(filters=None):
    columns = get_columns()
    data = []

    user = frappe.session.user
    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    conditions = ""
    if user != "Administrator":
        if filters.get("status"):
            conditions = """
                WHERE (
                    mt.owner = %(user)s
                    OR mt.assigned_by = %(employee_id)s
                    OR mt.name IN (
                        SELECT mt2.name FROM `tabMainTask` mt2
                        LEFT JOIN `tabMainTask Team` mteam2 ON mt2.name = mteam2.parent
                        WHERE mt2.owner = %(user)s OR mteam2.employee = %(employee_id)s
                    )
                    OR mt.name IN (
                        SELECT mt2.name FROM `tabMainTask` mt2
                        LEFT JOIN `tabMainTask Assign By` m_assign_by2 ON mt2.name = m_assign_by2.parent
                        WHERE m_assign_by2.employee = %(employee_id)s
                    )
                ) AND st.status = %(status)s
                """
        else:
            conditions = """
                WHERE (
                    mt.owner = %(user)s
                    OR mt.name IN (
                        SELECT mt2.name FROM `tabMainTask` mt2
                        LEFT JOIN `tabMainTask Team` mteam2 ON mt2.name = mteam2.parent
                        WHERE mt2.owner = %(user)s OR mteam2.employee = %(employee_id)s
                    )
                    OR mt.name IN (
                        SELECT mt2.name FROM `tabMainTask` mt2
                        LEFT JOIN `tabMainTask Assign By` m_assign_by2 ON mt2.name = m_assign_by2.parent
                        WHERE m_assign_by2.employee = %(employee_id)s
                    )
                )
                """
    else:
        if filters.get("status"):
            conditions = """
                WHERE st.status = %(status)s
                """

    query = f"""
            SELECT
            mt.name AS mt_name,
                mt.maintask_name AS maintask_name,
                mt.assign_date,
                mt.due_date,
                mt.status AS mt_status,
                t.task_name AS task,
                t.target_time_minutes as target_time,
                emp.user_id AS pic_task_user_id,
                emp.employee_name AS pic_task_name,
                st.owner AS sub_task_owner,
                st.name AS st_name,
                st.subtask_name AS sub_task,
                st.pic_subtask_name,
                st.target_time_minutes AS subtask_target_time,
                st.value AS value_subtask,
                st.status AS sub_task_status
            FROM `tabMainTask` mt
            LEFT JOIN `tabTasks` t ON t.maintask = mt.name
            LEFT JOIN `tabTask PIC` tp ON tp.parent = t.name
            LEFT JOIN `tabEmployee` emp ON tp.employee = emp.name
            LEFT JOIN `tabSubTask` st ON st.tasks = t.name AND st.owner = emp.user_id
            {conditions}
            ORDER BY mt.name, t.name, tp.employee, st.name
        """

    data = frappe.db.sql(query, {
        "user": user,
        "employee_id": employee_id,
        "status": filters.get("status")
    },
                         as_dict=True)

    team_map = get_team_members_map()
    assign_by_map = get_assign_by_map()

    for row in data:
        row["assign_by_members"] = assign_by_map.get(row["mt_name"], "")
        row["team_members"] = team_map.get(row["mt_name"], "")

    processed_mt = set()
    summ_data = []
    for tsm in data:
        if tsm.mt_name in processed_mt:
            continue

        processed_mt.add(tsm.mt_name)
        summ_data.append(
            {
                "maintask_name": tsm.maintask_name,
                "total_maintask": frappe.db.count("MainTask", filters={"name": tsm.mt_name}),
                "completed_maintask": frappe.db.count(
                    "MainTask", filters={"name": tsm.mt_name, "status": "Done"}
                ),
                "open_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Open"}
                ),
                "in_progress_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "In Progress"}
                ),
                "pause_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Pause"}
                ),
                "completed_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Done"}
                ),
                "close_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Close"}
                ),
                "cancel_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Cancel"}
                ),
                "total_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name}
                )
            }
        )
    # print(f'data {data}\n summ data {summ_data}')

    chart = get_chart_data(summ_data)
    report_summary = get_report_summary(summ_data, data)

    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"label": _("Main Task"), "fieldname": "maintask_name", "fieldtype": "Data", "width": 200},
        # {"label": _("Assigned By"), "fieldname": "assigned_by", "fieldtype": "Data", "width": 150},
        {"label": _("Assigned By"), "fieldname": "assign_by_members", "fieldtype": "Data", "width": 200},
        {"label": _("Team Members"), "fieldname": "team_members", "fieldtype": "Data", "width": 200},
        {"label": _("Assign Date"), "fieldname": "assign_date", "fieldtype": "Date", "width": 120},
        {"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 120},
        {"label": _("Task"), "fieldname": "task", "fieldtype": "Data", "width": 200},
        {"label": _("Target Time (Task)"), "fieldname": "target_time", "fieldtype": "Int", "width": 100},
        {"label": _("PIC Task"), "fieldname": "pic_task_name", "fieldtype": "Data", "width": 150},
        {"label": _("Sub Task"), "fieldname": "sub_task", "fieldtype": "Data", "width": 200},
        {"label": _("PIC Sub Task"), "fieldname": "pic_subtask_name", "fieldtype": "Data", "width": 150},
        {"label": _("Target Time (SubTask)"), "fieldname": "subtask_target_time", "fieldtype": "Int", "width": 100},
        {"label": _("Value Sub Task"), "fieldname": "value_subtask", "fieldtype": "Int", "width": 50},
        {"label": _("Sub Task Status"), "fieldname": "sub_task_status", "fieldtype": "Select", "width": 100},
    ]


def get_chart_data(data):
    idx_mt = []
    labels = []
    total = []
    completed = []
    open = []
    in_progress = []
    pause = []
    close = []
    cancel = []

    for tsm in data:
        
        labels.append(tsm["maintask_name"])
        open.append(tsm["open_subtask"])
        in_progress.append(tsm["in_progress_subtask"])
        pause.append(tsm["pause_subtask"])
        completed.append(tsm["completed_subtask"])
        close.append(tsm["close_subtask"])
        cancel.append(tsm["cancel_subtask"])
        total.append(tsm["total_subtask"])

    return {
        "data": {
            "labels": labels[:30],
            "datasets": [
                {"name": _("Open"), "values": open[:30]},
                {"name": _("In Progress"), "values": in_progress[:30]},
                {"name": _("Pause"), "values": pause[:30]},
                {"name": _("Done"), "values": completed[:30]},
                {"name": _("Close"), "values": close[:30]},
                {"name": _("Cancel"), "values": cancel[:30]},
                {"name": _("Total"), "values": total[:30]}
            ],
        },
        "type": "bar",
        "colors": ["#4B4B61","#0000FF","#FFD580", "#008000",  "#5A0363",  "#FF0000", "#808080"],
        "barOptions": {"stacked": True},
    }


def get_report_summary(summ_data, data):
    if not data:
        return None

    avg_completion = sum(1 for item in data if item.get("sub_task_status") == "Done" ) / len(data) * 100
    total = sum([tsm["total_maintask"] for tsm in summ_data])
    # total = len(set(tsm.mt_name for tsm in data))
    completed_maintask = sum([tsm["completed_maintask"] for tsm in summ_data])

    return [
        # {
        #     "value": avg_completion,
        #     "indicator": "Green" if avg_completion > 50 else "Red",
        #     "label": _("Average SubTask Completion"),
        #     "datatype": "Percent",
        # },
        {
            "value": total,
            "indicator": "Blue",
            "label": _("Total MainTask"),
            "datatype": "Int",
        },
        # {
        #     "value": completed_maintask,
        #     "indicator": "Green",
        #     "label": _("Completed MainTask"),
        #     "datatype": "Int",
        # },
    ]
