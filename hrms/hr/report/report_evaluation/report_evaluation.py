# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from collections import defaultdict


# def get_assign_by_map():
#     assign_by_data = frappe.db.sql("""
#                                    SELECT m_assign_by.parent                             AS main_task,
#                                           GROUP_CONCAT(emp.employee_name SEPARATOR ', ') AS assign_by_members
#                                    FROM `tabMainTask Assign By` m_assign_by
#                                             LEFT JOIN `tabEmployee` emp ON m_assign_by.employee = emp.name
#                                    GROUP BY m_assign_by.parent
#                                    """, as_dict=True)
#
#     return {row["main_task"]: row["assign_by_members"] for row in assign_by_data}


def execute(filters=None):
    columns = get_columns()

    user = frappe.session.user
    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    conditions = ""
    if user != "Administrator":
        conditions = """WHERE (mt.owner = %(user)s OR
        mt.name IN (SELECT mt2.name FROM `tabMainTask` mt2 LEFT JOIN `tabMainTask Team` mteam2 ON mt2.name = mteam2.parent WHERE mt2.owner = %(user)s OR %(employee_id)s OR
        mteam2.employee = %(employee_id)s)) OR
        mt.name IN ( SELECT mt2.name FROM `tabMainTask` mt2 LEFT JOIN `tabMainTask Assign By` m_assign_by2 ON mt2.name = m_assign_by2.parent  WHERE m_assign_by2.employee = %(employee_id)s ) AND st.status = 'Done'"""
        if filters.get("maintask"):
            conditions += " AND mt.name = %(maintask)s"

    query = f"""
                SELECT
                mt.name AS mt_name,
                    mt.maintask_name AS maintask_name,
                    mt.assign_date,
                    mt.due_date,
                    mt.status AS mt_status,
                    t.name AS t_name,
                    t.task_name AS task,
                    emp_tp.user_id AS pic_task_user_id,
                    emp_tp.employee_name AS pic_task_name,
                    st.owner AS sub_task_owner,
                    st.subtask_name AS sub_task,
                    st.pic_subtask_name,
                    st.target_time AS subtask_target_time,
                    st.value AS value_subtask,
                    ev.performance AS performance,
                    ev.final_target_time AS final_target_time,
                    ev.contribution AS contribution
                FROM `tabMainTask` mt
                LEFT JOIN `tabMainTask Team` mteam ON mt.name = mteam.parent
                LEFT JOIN `tabTasks` t ON t.maintask = mt.name
                LEFT JOIN `tabTask PIC` tp ON tp.parent = t.name
                LEFT JOIN `tabEmployee` emp_tp ON tp.employee = emp_tp.name
                LEFT JOIN `tabSubTask` st ON st.tasks = t.name
                LEFT JOIN `tabEvaluation` ev ON ev.subtask = st.name
                {conditions}
                ORDER BY mt.name, t.name, tp.employee, st.name
            """
    data = frappe.db.sql(query, {"user": user, "employee_id": employee_id,
                                 "maintask": filters.get("maintask")}, as_dict=True)

    # assign_by_map = get_assign_by_map()
    #
    # for row in data:
    #     row["assign_by_members"] = assign_by_map.get(row["mt_name"], "")

    chart = get_chart_data(data)
    report_summary = get_report_summary(data)

    return columns, data, None, chart, report_summary


def get_filters():
    return [
        {
            "fieldname": "mt_name",
            "label": "Main Task",
            "fieldtype": "Link",
            "options": "MainTask",
            "reqd": 0
        }
    ]


def get_columns():
    return [
        {"label": _("Main Task"), "fieldname": "maintask_name", "fieldtype": "Data", "width": 200},
        {"label": _("Assign Date"), "fieldname": "assign_date", "fieldtype": "Date", "width": 120},
        {"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 120},
        {"label": _("Task"), "fieldname": "task", "fieldtype": "Data", "width": 200},
        {"label": _("PIC Task"), "fieldname": "pic_task_name", "fieldtype": "Data", "width": 150},
        {"label": _("Sub Task"), "fieldname": "sub_task", "fieldtype": "Data", "width": 200},
        {"label": _("PIC Sub Task"), "fieldname": "pic_subtask_name", "fieldtype": "Data", "width": 150},
        {"label": _("Target Time (SubTask)"), "fieldname": "subtask_target_time", "fieldtype": "Int", "width": 100},
        {"label": _("Value Sub Task"), "fieldname": "value_subtask", "fieldtype": "Int", "width": 50},
        {"label": _("Performance"), "fieldname": "performance", "fieldtype": "Int", "width": 100},
        {"label": _("Final Target Time"), "fieldname": "final_target_time", "fieldtype": "Float", "width": 100},
        {"label": _("Contribution"), "fieldname": "contribution", "fieldtype": "Data", "width": 100}
    ]


def get_chart_data(data):
    contribution_map = defaultdict(dict)
    labels_set = set()

    for row in data:
        maintask = row.get("maintask_name")
        pic = row.get("pic_subtask_name")
        contribution = row.get("contribution")

        if not maintask or not pic:
            continue

        labels_set.add(maintask)

        # Handle jika kontribusi disimpan dalam format string "12.5%"
        try:
            if isinstance(contribution, str) and "%" in contribution:
                contribution = float(contribution.replace("%", ""))
            else:
                contribution = float(contribution or 0)
        except:
            contribution = 0

        # Tambahkan kontribusi PIC untuk maintask ini
        if pic in contribution_map:
            contribution_map[pic][maintask] = contribution_map[pic].get(maintask, 0) + contribution
        else:
            contribution_map[pic] = {maintask: contribution}

    labels = sorted(list(labels_set))[:30]  # Limit maksimum 30 MainTask
    datasets = []

    for pic, contribs in contribution_map.items():
        dataset_values = [contribs.get(label, 0) for label in labels]

        datasets.append({
            "name": pic,
            "values": dataset_values
        })

    return {
        "data": {
            "labels": labels,
            "datasets": datasets
        },
        "type": "bar",
        "colors": ["#5e64ff", "#ff5858", "#00ca00", "#ffa00a", "#743ee2", "#3f8efc", "#fa8231", "#f7b731"][
                  :len(datasets)],
        "barOptions": {
            "stacked": False
        }
    }


def get_report_summary(data):
    if not data:
        return None

    for row in data:
        contribution = row.get("contribution")
        try:
            if isinstance(contribution, str) and "%" in contribution:
                contribution = float(contribution.replace("%", ""))
                row["contribution"] = contribution
            else:
                contribution = float(contribution or 0)
                row["contribution"] = contribution
        except:
            contribution = 0
            row["contribution"] = contribution

    avg_performance = sum(e.get("performance", 0) for e in data if e.get("performance")) / len(data)
    avg_target_time = sum(e.get("final_target_time", 0) for e in data if e.get("final_target_time")) / len(data)
    avg_contribution = sum(e.get("contribution", 0) for e in data if e.get("contribution")) / len(data)

    return [
        {
            "value": round(avg_performance, 2),
            "indicator": "Green" if avg_performance >= 70 else "Red",
            "label": _("Avg Performance"),
            "datatype": "Float",
        },
        {
            "value": round(avg_target_time, 2),
            "indicator": "Blue",
            "label": _("Avg Final Target Time"),
            "datatype": "Float",
        }
    ]
