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
        self.validate_from_to_dates("assign_date", "due_date")

    def validate_maintask_data(self):
        self.created_by = frappe.db.get_value("Employee", {"user_id": self.owner}, "employee_name")


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
        # frappe.msgprint('In update MainTask')
        return
    frappe.flags.in_update = True
    print("update maintask called")

    previous_status = doc.flags.get("_previous_status")
    now_status = doc.status
    if previous_status != now_status:
        tasks = frappe.get_all("Tasks", filters={"maintask": doc.name}, pluck="name")
        for task_name in tasks:
            frappe.db.set_value("Tasks", task_name, "status", now_status)
            frappe.msgprint(f"Updated Tasks status to {now_status}")
            # task.save(ignore_permissions=True)

            subtasks = frappe.get_all("SubTask", filters={"tasks": task_name}, pluck="name")
            for subtask_name in subtasks:
                subtask_status = frappe.db.get_value("SubTask", subtask_name, "status")
                if subtask_status not in ("Done", "Close", "In Progress", "Pause"):
                    frappe.db.set_value("SubTask", subtask_name, "status", now_status)
                    frappe.msgprint(f"Updated SubTask status to {now_status}")
                    # subtask.save(ignore_permissions=True)

    frappe.flags.in_update = False


def permission_query_conditions(doc, ptype=None, user=None, debug=False):
    user_id = user or frappe.session.user

    roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")
    if "System Manager" in roles and user_id == "Administrator":
        return ""

    employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")

    conditions = [f"tabMainTask.owner = '{user_id}'"]
    if employee_id:

        parent_mteam = frappe.get_all(
            "MainTask Team",
            filters={"employee": employee_id},
            pluck="parent"
        )

        parent_assign_by = frappe.get_all(
            "MainTask Assign By",
            filters={"employee": employee_id},
            pluck="parent"
        )

        if parent_mteam:
            maintask_ids = "', '".join(parent_mteam)
            conditions.append(f"tabMainTask.name IN ('{maintask_ids}')")

        if parent_assign_by:
            assign_by_maintask_ids = "', '".join(parent_assign_by)
            conditions.append(f"tabMainTask.name IN ('{assign_by_maintask_ids}')")
            
    print("maintask query conditions:", conditions)
    return " OR ".join(conditions)


def has_permission(doc, ptype, user):
    print("permission maintask called")
    if user == "Administrator":
        return True

    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
    if not employee_id:
        return False

    parent_assign_by = frappe.get_all(
		"MainTask Assign By",
		filters={"employee": employee_id},
		pluck="parent"
	)
    
    parent_mteam = frappe.get_all(
		"MainTask Team",
		filters={"employee": employee_id},
		pluck="parent"
	)
 
    if ptype in ("read", None) and (doc.name in parent_mteam or doc.name in parent_assign_by):
        return True

    employee = frappe.get_doc("Employee", employee_id)

    if ptype == "delete":
        if doc.owner != user:
            frappe.throw(f"{employee.employee_name} is not the owner & not allowed to deleting {doc.maintask_name} maintask.",
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

    parent_assign_by = frappe.get_all(
		"MainTask Assign By",
		filters={"employee": employee_id},
		pluck="parent"
	)
    
    if doc.name in parent_assign_by:
        return "assign_by_maintask_leader"
    
    return "none"

@frappe.whitelist()
def get_task_template_list():
    return frappe.get_all("Tasks Template", fields=["name", "template_name"])

@frappe.whitelist()
def get_template_details(template_name):
    return frappe.get_all("Tasks Template Detail", filters={"parent": template_name}, fields=["task_name_template", "target_time_template", "unit_target_time_template", "status_template"])

@frappe.whitelist()
def create_tasks_from_template(maintask, values, count):
    import json
    print(f"create_tasks_from_template called with values: {values} and count: {count}")
    # values = frappe._dict(values)
    if isinstance(values, str):
        values = json.loads(values)
    for i in range(int(count)):
        task = frappe.new_doc("Tasks")
        task.maintask = maintask
        task.task_name = values[f"task_name_template_{i}"]
        task.target_time = values[f"target_time_template_{i}"]
        task.unit_target_time = values[f"unit_target_time_template_{i}"]
        task.status = values[f"status_template_{i}"]

        pic_list = frappe.parse_json(values[f"task_pic_{i}"])
        for emp in pic_list:
            if emp.get("employee"):
                task.append("task_pic", {"employee": emp.get("employee")})

        print(f"Task values: {task.as_dict()}")
        task.insert()
