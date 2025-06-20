# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    return get_columns(), get_data(filters)


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
        {"label": _("Contribution"), "fieldname": "contribution", "fieldtype": "Data", "width": 100},
        {"label": _("Sub Task Status"), "fieldname": "sub_task_status", "fieldtype": "Data", "width": 100},
    ]


def get_data(filters):
    user = frappe.session.user

    conditions = ""
    if user != "Administrator":
        conditions = "WHERE mt.owner = %(user)s OR mt.assigned_by = %(employee_id)s OR mt.name IN (SELECT mt2.name FROM `tabMainTask` mt2 LEFT JOIN `tabMainTask Team` mteam2 ON mt2.name = mteam2.parent WHERE mt2.owner = %(user)s OR %(employee_id)s OR mteam2.employee = %(employee_id)s)"

    return frappe.db.sql(f"""
        SELECT
            mt.maintask_name AS main_task,
            mt.assign_date,
            mt.due_date,
            t.task_name AS task,
            t.pic_task_name,
            st.subtask_name AS sub_task,
            st.pic_subtask_name,
            st.target_time AS subtask_target_time,
            st.value AS value_subtask,
            ev.performance AS performance,
            ev.final_target_time AS final_target_time,
            ev.contribution AS contribution,
            st.status AS sub_task_status
        FROM `tabMainTask` mt
        LEFT JOIN `tabTasks` t ON t.maintask = mt.name
        LEFT JOIN `tabSubTask` st ON st.tasks = t.name
        LEFT JOIN `tabEvaluation` ev ON ev.subtask = st.name
        {conditions}
        GROUP BY mt.name, t.name, st.name
        ORDER BY mt.name, t.name, st.name
    """, {"user": user}, as_dict=True)
