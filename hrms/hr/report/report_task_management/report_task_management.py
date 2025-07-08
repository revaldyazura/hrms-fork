import frappe
from frappe import _


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
                ) AND st.status = %(status)s
                """
        else:
            conditions = """
                WHERE (
                    mt.owner = %(user)s
                    OR mt.assigned_by = %(employee_id)s
                    OR mt.name IN (
                        SELECT mt2.name FROM `tabMainTask` mt2
                        LEFT JOIN `tabMainTask Team` mteam2 ON mt2.name = mteam2.parent
                        WHERE mt2.owner = %(user)s OR mteam2.employee = %(employee_id)s
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
                mt.assigned_by_name AS assigned_by,
                GROUP_CONCAT(emp.employee_name SEPARATOR ', ') AS team_members,
                mt.assign_date,
                mt.due_date,
                mt.status AS mt_status,
                t.task_name AS task,
                t.target_time,
                t.pic_task_name,
                st.name AS st_name,
                st.subtask_name AS sub_task,
                st.pic_subtask_name,
                st.target_time AS subtask_target_time,
                st.value AS value_subtask,
                st.status AS sub_task_status
            FROM `tabMainTask` mt
            LEFT JOIN `tabMainTask Team` mteam ON mt.name = mteam.parent
            LEFT JOIN `tabEmployee` emp ON mteam.employee = emp.name
            LEFT JOIN `tabTasks` t ON t.maintask = mt.name
            LEFT JOIN `tabSubTask` st ON st.tasks = t.name
            {conditions}
            GROUP BY mt.name, t.name, st.name
            ORDER BY mt.name, t.name, st.name
        """
    # print(f'query summary task is {query}')
    data = frappe.db.sql(query, {
        "user": user,
        "employee_id": employee_id,
        "status": filters.get("status")
    },
                         as_dict=True)

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
                "completed_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Done"}
                ),
                "open_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Open"}
                ),
                "hold_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Hold"}
                ),
                "cancel_subtask": frappe.db.count(
                    "SubTask", filters={"maintask": tsm.mt_name, "status": "Cancel"}
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
        {"label": _("Assigned By"), "fieldname": "assigned_by", "fieldtype": "Data", "width": 150},
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
    hold = []
    cancel = []

    for tsm in data:
        # if tsm.mt_name in idx_mt:
        #     pass
        # else:
        #     idx_mt.append(tsm.mt_name)
        labels.append(tsm["maintask_name"])
        open.append(tsm["open_subtask"])
        completed.append(tsm["completed_subtask"])
        hold.append(tsm["hold_subtask"])
        cancel.append(tsm["cancel_subtask"])

    return {
        "data": {
            "labels": labels[:30],
            "datasets": [
                {"name": _("Open"), "values": open[:30]},
                {"name": _("Done"), "values": completed[:30]},
                {"name": _("Hold"), "values": hold[:30]},
                {"name": _("Cancel"), "values": cancel[:30]},
            ],
        },
        "type": "bar",
        "colors": ["#0000FF", "#008000", "#FFD580", "#FF0000"],
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
        {
            "value": avg_completion,
            "indicator": "Green" if avg_completion > 50 else "Red",
            "label": _("Average SubTask Completion"),
            "datatype": "Percent",
        },
        {
            "value": total,
            "indicator": "Blue",
            "label": _("Total MainTask"),
            "datatype": "Int",
        },
        {
            "value": completed_maintask,
            "indicator": "Green",
            "label": _("Completed MainTask"),
            "datatype": "Int",
        },
    ]
