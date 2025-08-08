# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
from datetime import datetime

from marshmallow.utils import pluck

import frappe
from frappe import _, scrub, throw
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime


class Evaluation(Document):
    def validate(self):
        print("validate eval called")
        self.validate_performance()
        self.validate_evaluation_data()

    def before_insert(self):
        subtask = frappe.get_doc("SubTask", self.subtask)
        if subtask.status == "Done":
            frappe.msgprint(
                f"SubTask '{subtask.subtask_name}' status updated to Close after the performance is evaluated."
            )

            frappe.db.set_value(
                "SubTask",
                self.subtask,
                {
                    "status": "Close",
                    "subtask_close_date": frappe.utils.getdate(now_datetime()),
                },
            )

    def validate_performance(self):
        if self.performance > 120:
            throw(_("Performance grade cannot be greater than 120."))

    def validate_evaluation_data(self):
        self.created_by = frappe.db.get_value(
            "Employee", {"user_id": self.owner}, "employee_name"
        )


def update_fields(doc, method):

    if frappe.flags.in_update:
        # frappe.msgprint(f"In update Evaluation")
        return
    frappe.flags.in_update = True

    print("update fields evaluation called")

    subtask = frappe.get_doc("SubTask", doc.subtask)
    tasks_doc = frappe.get_doc("Tasks", subtask.tasks)

    doc.pic_subtask = subtask.pic_subtask
    doc.tasks = subtask.tasks
    doc.maintask = tasks_doc.maintask
    doc.final_target_time = round(
        (subtask.target_time_minutes * doc.performance) / 100, 2
    )
    doc.save(ignore_permissions=True)

    all_subtasks = frappe.get_all(
        "SubTask",
        filters={"maintask": subtask.maintask},
        fields=["name", "target_time_minutes", "value"],
    )
    total_subtask = len(all_subtasks)

    evaluations = frappe.get_all(
        "Evaluation",
        filters={"maintask": tasks_doc.maintask},
        fields=["name", "subtask", "performance"],
    )
    evaluated_subtasks = len(evaluations)

    if total_subtask == evaluated_subtasks and total_subtask > 0:
        total_tvr = 0
        subtask_map = {s["name"]: s for s in all_subtasks}

        eval_tvr_map = {}

        for eval in evaluations:
            sub = subtask_map.get(eval["subtask"])
            if sub:
                eval_tvr = (
                    sub["target_time_minutes"] * int(sub["value"]) * eval["performance"]
                ) / 100
                eval_tvr_map[eval["name"]] = eval_tvr
                total_tvr += eval_tvr

        if total_tvr > 0:
            for eval in evaluations:
                eval_tvr = eval_tvr_map.get(eval["name"], 0)
                contribution = str(round((eval_tvr / total_tvr) * 100, 2)) + "%"
                frappe.db.set_value(
                    "Evaluation", eval.name, "contribution", contribution
                )

    frappe.flags.in_update = False


@frappe.whitelist()
def user_edit_evaluation(subtask):
    print("user edit evaluation called")

    if frappe.session.user == "Administrator":
        return "admin"

    doc = frappe.get_doc("SubTask", subtask)
    employee_id = frappe.get_value("Employee", {"user_id": frappe.session.user}, "name")

    maintask = frappe.get_doc("MainTask", doc.maintask)

    if not employee_id:
        return False

    if doc.owner == frappe.session.user:
        return "owner_evaluation"

    if doc.tasks:
        task_owner = frappe.get_value("Tasks", doc.tasks, "owner")
        parent_task_pic = frappe.get_all(
            "Task PIC", filters={"employee": employee_id}, pluck="parent"
        )
        if task_owner == frappe.session.user:
            return "task_owner"

        if doc.tasks in parent_task_pic:
            return "task_pics"

        if doc.pic_subtask == employee_id and frappe.session.user != maintask.owner:
            return "pic_subtask"

    return "none"


def has_permission(doc, ptype, user):
    print("has permission evaluation called")

    if frappe.session.user == "Administrator":
        return True

    if ptype in ("read", None):
        return True

    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
    if not employee_id:
        return False

    employee = frappe.get_doc("Employee", employee_id)
    tasks = frappe.get_doc("Tasks", doc.tasks)
    maintask = frappe.get_doc("MainTask", doc.maintask)

    parent_task_pic = frappe.get_all(
        "Task PIC", filters={"employee": employee_id}, pluck="parent"
    )

    parent_assign_by = frappe.get_all(
        "MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
    )

    if ptype == "delete":
        if (
            doc.pic_subtask == employee_id
            and doc.tasks not in parent_task_pic
            and maintask.owner != user
        ):
            frappe.throw(
                f"{employee.employee_name} is pic subtask only and not allowed to deleting {doc.subtask_name} evaluation.",
                frappe.PermissionError,
            )
            return False
        if doc.maintask in parent_assign_by:
            frappe.throw(
                f"{employee.employee_name} is assign by only and not allowed to deleting {doc.subtask_name} evaluation.",
                frappe.PermissionError,
            )
            return False
    elif doc.pic_subtask == employee_id and ptype != "delete":
        return True

    if doc.owner == frappe.session.user:
        return True

    if doc.tasks:
        owner_task = tasks.owner
        if owner_task == frappe.session.user or tasks in parent_task_pic:
            return True

    frappe.throw(
        f"{employee.employee_name} is not allowed to accessing {doc.subtask_name} evaluation.",
        frappe.PermissionError,
    )
    return False


def after_delete(doc, method):
    subtask = frappe.get_doc("SubTask", doc.subtask)
    if subtask.status == "Close":
        frappe.db.set_value(
            "SubTask", doc.subtask, {"status": "Done", "subtask_close_date": None}
        )
        # subtask.save(ignore_permissions=True)
        frappe.msgprint(
            f"SubTask '{subtask.subtask_name}' status updated to Done after deleting evaluation."
        )


@frappe.whitelist()
def get_done_subtask_as_owner(doctype, txt, searchfield, start, page_len, filters):
    user_id = frappe.session.user

    employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")

    subtasks = frappe.db.sql(
        """
        SELECT st.name, st.subtask_name
        FROM `tabSubTask` st
        JOIN `tabMainTask` mt ON st.maintask = mt.name
        WHERE (st.owner = %(user_id)s OR mt.owner = %(user_id)s OR mt.assigned_by = %(employee_id)s) AND st.status = 'Done'
        GROUP BY st.name
    """,
        {"user_id": f"{user_id}", "employee_id": f"{employee_id}"},
    )
    return subtasks


def permission_query_conditions(doc, ptype=None, user=None, debug=False):
    user_id = user or frappe.session.user

    roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")

    if "System Manager" in roles:
        return ""

    employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")

    parent_mteam = frappe.get_all(
        "MainTask Team", filters={"employee": employee_id}, pluck="parent"
    )

    parent_assign_by = frappe.get_all(
        "MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
    )

    if not employee_id:
        return "1=0"

    maintask_ids = "', '".join(parent_mteam)

    assign_by_maintask_ids = "', '".join(parent_assign_by)

    return f"""
        (`tabEvaluation`.`pic_subtask` = '{employee_id}'
        OR `tabEvaluation`.`owner` = '{user_id}'
        OR `tabEvaluation`.`maintask` IN (
            SELECT `name` FROM `tabMainTask` WHERE `owner` = '{user_id}' OR `assigned_by` = '{employee_id}' OR `name` IN ('{maintask_ids}')
        ) OR `tabEvaluation`.`tasks` IN (
            SELECT `name` FROM `tabTasks` WHERE `owner` = '{user_id}'
        )OR `tabEvaluation`.`maintask` IN (SELECT `name` FROM `tabMainTask` WHERE name IN ('{assign_by_maintask_ids}')))
    """
