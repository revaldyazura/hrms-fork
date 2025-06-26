# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub, throw
from frappe.model.document import Document


class Tasks(Document):
    pass
    # def validate(self):
    #     self.validate_task_name()

    # def validate_task_name(self):
    #     pic_task_team = frappe.db.get_value("Employee", {"name": self.pic_task}, "team")
    #     prefix_task = self.task_name.split("-")[0].upper()

    #     if prefix_task != pic_task_team:
    #         throw(_("Please put the task name properly, as shown in description."))
    #     else:
    #         task_name_splitted = self.task_name.split("-")
    #         prefix = task_name_splitted[0].upper()
    #         task_name = "-".join([prefix] + task_name_splitted[1:])
    #         self.task_name = task_name
    #         self.created_by = frappe.db.get_value("Employee", {"user_id": self.owner}, "employee_name")


def before_save(doc, method):
    if doc.get('__islocal'):
        doc.flags._previous_status = None
    else:
        doc.flags._previous_status = frappe.db.get_value("Tasks", doc.name, "status")

def after_delete(doc, method):
    subtasks = frappe.get_all("SubTask", {"tasks": doc.name})
    for subtask in subtasks:
        if subtask.status != "Done":
            frappe.delete_doc("SubTask", subtask.name, ignore_permissions=True)

def update_fields(doc, method):
    if frappe.flags.in_update:
        frappe.msgprint(f"In update Tasks")
        return
    frappe.flags.in_update = True

    previous_status = doc.flags.get("_previous_status")
    now_status = doc.status
    if previous_status != now_status:
        subtasks = frappe.get_all("SubTask", filters={"tasks": doc.name}, pluck="name")
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

    parent_mteam = frappe.get_all(
        "MainTask Team",
        filters={"employee": employee_id},
        pluck="parent"
    )

    if not parent_mteam:
        return "1=0"

    if not employee_id:
        return "1=0"

    maintask_ids = "', '".join(parent_mteam)

    return f"(tabTasks.pic_task = '{employee_id}' OR tabTasks.owner = '{user_id}' OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE owner = '{user_id}' OR assigned_by = '{employee_id}') OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE name IN ('{maintask_ids}')))"


@frappe.whitelist()
def user_edit_tasks(task_name):
    if frappe.session.user == "Administrator":
        return "admin"

    doc = frappe.get_doc("Tasks", task_name)
    employee_id = frappe.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee_id:
        return "none"

    if doc.pic_task == employee_id:
        return "pic_task"

    if doc.maintask:
        owner_maintask = frappe.get_value("MainTask", doc.maintask, "owner")
        if owner_maintask == frappe.session.user:
            return "pic_maintask"

    return "none"


def has_permission(doc, ptype, user):
    if user == "Administrator":
        return True

    if ptype in ("read", None):
        return True

    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
    if not employee_id:
        return False

    employee = frappe.get_doc("Employee", employee_id)

    if ptype == "delete":
        if doc.pic_task == employee_id:
            frappe.throw(f"{employee.employee_name} is not allowed to deleting {doc.task_name} task.",
                         frappe.PermissionError)
            return False
        check_finished_subtask = frappe.get_all("SubTask", {"tasks": doc.name}, pluck="status")
        if "Done" in check_finished_subtask:
            frappe.throw(f"Sorry {employee.employee_name} one of the subtasks in this task is evaluated, you can't delete it.",
                         frappe.PermissionError)
            return False
    else:
        return True

    if doc.maintask:
        owner_maintask = frappe.get_value("MainTask", doc.maintask, "owner")
        if owner_maintask == frappe.session.user:
            return True

    frappe.throw(f"{employee.employee_name} is not allowed to acessing {doc.task_name} task.", frappe.PermissionError)
    return False


@frappe.whitelist()
def get_employees_by_role_and_team(doctype, txt, searchfield, start, page_len, filters):
    maintask = filters.get("maintask")
    if not maintask:
        return []
    employees = frappe.db.sql("""
        SELECT e.name, e.employee_name
        FROM `tabEmployee` e
        JOIN `tabUser` u ON u.name = e.user_id
        JOIN `tabHas Role` hr ON hr.parent = u.name
        JOIN `tabMainTask Team` mteam ON mteam.employee = e.name
        JOIN `tabMainTask` mt ON mt.name = mteam.parent
        WHERE mt.name = %(maintask)s
          AND e.status = 'Active'
          AND (e.name LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
        GROUP BY e.name
        ORDER BY e.employee_name
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        "maintask": maintask,
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })
    return employees


@frappe.whitelist()
def get_open_maintask_as_the_owner(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user

    conditions = ""
    if user != "Administrator":
        conditions = "WHERE mt.owner = %(user)s AND mt.status = 'Open'"

    maintasks = frappe.db.sql(f"""
        SELECT mt.name, mt.maintask_name
        FROM `tabMainTask` mt
       {conditions}
        GROUP BY mt.name
    """, {
        "user": f"{user}"
    })
    return maintasks
