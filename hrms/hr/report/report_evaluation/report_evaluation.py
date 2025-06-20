# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = []

    user = frappe.session.user

    conditions = ""
    if user != "Administrator":
        conditions = "WHERE mt.owner = %(user)s OR mt.assigned_by = %(employee_id)s"

    data = frappe.db.sql(f"""
            SELECT
                mt.maintask_name AS main_task,
                mt.assign_date,
                mt.due_date,
                t.task_name AS task,
                t.pic_task_name,
                st.name AS st_name,
                st.subtask_name AS sub_task,
                st.pic_subtask_name,
                st.target_time AS subtask_target_time,
                st.value AS value_subtask,
                ev.performance AS performance,
                ev.final_target_time AS final_target_time,
                ev.contribution AS contribution
             FROM `tabEvaluation` ev
            LEFT JOIN `tabSubTask` st ON st.name = ev.subtask
            LEFT JOIN `tabTasks` t ON t.name = ev.tasks
            LEFT JOIN `tabMainTask` mt ON ev.maintask = mt.name
            {conditions}
            GROUP BY  st.name
            ORDER BY  st.name
        """, {"user": user}, as_dict=True)

    for tsm in data:
        tsm["total_subtask"] = frappe.db.count("SubTask", filters={"name": tsm["st_name"]}) if tsm.get("st_name") else 0
        tsm["evaluated_subtask"] = frappe.db.count("Evaluation", filters={"subtask": tsm["st_name"]}) if tsm.get(
            "st_name") else 0

    print(f"table data \n{data}")
    chart = get_chart_data(data)
    report_summary = get_report_summary(data)

    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"label": _("Main Task"), "fieldname": "main_task", "fieldtype": "Data", "width": 200},
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
    labels = []
    performance = []
    final_target_time = []
    contribution = []

    for eval in data:
        labels.append(eval["main_task"])
        performance.append(eval.get("performance", 0))
        final_target_time.append(eval.get("final_target_time", 0))

    return {
        "data": {
            "labels": labels[:30],
            "datasets": [
                {"name": _("Performance"), "values": performance[:30]},
                {"name": _("Final Target Time"), "values": final_target_time[:30]},
            ],
        },
        "type": "bar",
        "colors": ["#4caf50", "#2196f3", "#ffc107"],
        "barOptions": {"stacked": False},
    }


def get_report_summary(data):
    if not data:
        return None

    avg_performance = sum(e.get("performance", 0) for e in data) / len(data)
    avg_target_time = sum(e.get("final_target_time", 0) for e in data) / len(data)

    return [
        {
            "value": sum(e.get("total_subtask", 0) for e in data),
            "indicator": "Red",
            "label": _("Total Subtask"),
            "datatype": "Int",
        },
        {
            "value": sum(e.get("evaluated_subtask", 0) for e in data),
            "indicator": "Black" if avg_performance >= 70 else "Red",
            "label": _("Evaluated SubTask"),
            "datatype": "Int",
        },
        {
            "value": round(avg_performance, 2),
            "indicator": "Green" if avg_performance >= 70 else "Red",
            "label": _("Avg Performance"),
            "datatype": "Percent",
        },
        {
            "value": round(avg_target_time, 2),
            "indicator": "Blue",
            "label": _("Avg Final Target Time"),
            "datatype": "Float",
        },
        # {
        #     "value": round(avg_contribution, 2),
        #     "indicator": "Orange" if avg_contribution < 50 else "Green",
        #     "label": _("Avg Contribution"),
        #     "datatype": "Percent",
        # },
    ]
