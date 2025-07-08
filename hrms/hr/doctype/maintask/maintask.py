# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
import frappe
from frappe.utils import get_datetime
from frappe.model.document import Document
from frappe import _, throw
from frappe.utils import getdate, today


class MainTask(Document):
    def validate(self):
        print("validate maintask called")
        self.validate_date()
        self.validate_maintask_data()

    def validate_date(self):
        # if self.assign_date and getdate(self.assign_date) < getdate(today()):
        #     throw(_("Assign date cannot be later than today."))

        self.validate_from_to_dates("assign_date", "due_date")

    def validate_maintask_data(self):
        self.created_by = frappe.db.get_value("Employee", {"user_id": self.owner}, "employee_name")
        full_name = frappe.db.get_value("Employee", {"name": self.assigned_by}, "employee_name")
        self.assigned_by_name = full_name if full_name else ""


def before_save(doc, method):
    print("before save maintask called")
    if doc.get('__islocal'):
        doc.flags._previous_status = None
    else:
        doc.flags._previous_status = frappe.db.get_value("MainTask", doc.name, "status")

def after_delete(doc, method):
    print("after delete maintask called")
    subtasks = frappe.get_all("SubTask", {"maintask": doc.name})
    for subtask in subtasks:
        if subtask.status != "Done":
            frappe.delete_doc("SubTask", subtask.name, ignore_permissions=True)

def update_fields(doc, method):
    if frappe.flags.in_update:
        frappe.msgprint('In update MainTask')
        return
    frappe.flags.in_update = True
    print("update maintask called")

    previous_status = doc.flags.get("_previous_status")
    now_status = doc.status
    if previous_status != now_status:
        tasks = frappe.get_all("Tasks", filters={"maintask": doc.name}, pluck="name")
        for task_name in tasks:
            task = frappe.get_doc("Tasks", task_name)
            task.status = doc.status
            task.save(ignore_permissions=True)

            subtasks = frappe.get_all("SubTask", filters={"tasks": task.name}, pluck="name")
            for subtask_name in subtasks:
                subtask = frappe.get_doc("SubTask", subtask_name)
                if subtask.status != "Done":
                    subtask.status = doc.status
                    subtask.save(ignore_permissions=True)

    frappe.flags.in_update = False


def permission_query_conditions(doc, ptype=None, user=None, debug=False):
    user_id = user or frappe.session.user

    roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")
    if "System Manager" in roles:
        return ""

    employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")

    # employee = frappe.get_doc("Employee", employee_id)
    #
    # parent_mteam = frappe.get_all(
    #     "MainTask Team",
    #     filters={"employee": employee_id},
    #     pluck="parent"
    # )
    #
    # if not employee_id:
    #     return "1=0"
    #
    # if not parent_mteam:
    #     return "1=0"
    #
    # maintask_ids = "', '".join(parent_mteam)
    # query = f"(tabMainTask.assigned_by = '{employee_id}' OR tabMainTask.owner = '{user_id}' OR tabMainTask.name IN ('{maintask_ids}'))"
    #
    # return query
    conditions = [f"tabMainTask.owner = '{user_id}'"]
    if employee_id:
        conditions.append(f"tabMainTask.assigned_by = '{employee_id}'")

        parent_mteam = frappe.get_all(
            "MainTask Team",
            filters={"employee": employee_id},
            pluck="parent"
        )

        if parent_mteam:
            maintask_ids = "', '".join(parent_mteam)
            conditions.append(f"tabMainTask.name IN ('{maintask_ids}')")

    return " OR ".join(conditions)


@frappe.whitelist()
def user_edit_maintask(maintask_name):
    if frappe.session.user == "Administrator":
        return "admin"

    doc = frappe.get_doc("MainTask", maintask_name)
    employee_id = frappe.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee_id:
        return "none"

    if doc.owner == frappe.session.user:
        return "owner_maintask"

    return "none"


def has_permission(doc, ptype, user):
    print("permission maintask called")
    if user == "Administrator":
        return True

    if ptype in ("read", None):
        return True

    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
    if not employee_id:
        return False

    employee = frappe.get_doc("Employee", employee_id)

    if ptype == "delete":
        if doc.owner != user:
            frappe.throw(f"{employee.employee_name} is not allowed to deleting {doc.maintask_name} maintask.",
                         frappe.PermissionError)
            return False
        elif doc.owner == user:
            check_finished_subtask = frappe.get_all("SubTask", {"maintask": doc.name}, pluck="status")
            if "Done" in check_finished_subtask:
                frappe.throw(
                    f"Sorry {employee.employee_name} one of the subtasks in this maintask is evaluated, you can't delete it.",
                    frappe.PermissionError)
                return False
            return True
    elif doc.owner == user:
        return True

    frappe.throw(f"{employee.employee_name} is not allowed to acessing {doc.maintask_name} maintask.",
                 frappe.PermissionError)
    return False
