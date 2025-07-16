# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub, throw
from frappe.model.document import Document


class Tasks(Document):

    def validate(self):
        print("validate task called")
        self.validate_task_name()

    def validate_task_name(self):
        maintask_name = frappe.db.get_value("MainTask", {"name": self.maintask}, "maintask_name")
        self.maintask_name = maintask_name if maintask_name else ""
        self.created_by = frappe.db.get_value("Employee", {"user_id": self.owner}, "employee_name")
        if self.unit_target_time == "Hours":
            self.target_time_minutes = self.target_time * 60
        else:
            self.target_time_minutes = self.target_time


def before_save(doc, method):
    print("before save tasks called")
    if doc.get('__islocal'):
        doc.flags._previous_status = None
    else:
        doc.flags._previous_status = frappe.db.get_value("Tasks", doc.name, "status")

def after_delete(doc, method):
    print("after delete tasks called")
    subtasks = frappe.get_all("SubTask", {"tasks": doc.name})
    for subtask in subtasks:
        if subtask.status != "Done":
            frappe.delete_doc("SubTask", subtask.name, ignore_permissions=True)

def update_fields(doc, method):
    if frappe.flags.in_update:
        # frappe.msgprint(f"In update Tasks")
        return
    frappe.flags.in_update = True

    print("update tasks called")

    previous_status = doc.flags.get("_previous_status")
    now_status = doc.status
    if previous_status != now_status:
        subtasks = frappe.get_all("SubTask", filters={"tasks": doc.name}, pluck="name")
        for subtask_name in subtasks:
            subtask = frappe.get_doc("SubTask", subtask_name)
            if subtask.status != "Done":
                frappe.db.set_value("SubTask", subtask_name, "status", doc.status)

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

    parent_assign_by = frappe.get_all(
        "MainTask Assign By",
        filters={"employee": employee_id},
        pluck="parent"
    )

    # if not parent_mteam:
    #     return "1=0"

    # if not parent_assign_by:
    #     return "1=0"

    if not employee_id:
        return "1=0"

    maintask_ids = "', '".join(parent_mteam)

    assign_by_maintask_ids = "', '".join(parent_assign_by)

    parent_task_pic = frappe.get_all(
        "Task PIC",
        filters={"employee": employee_id},
        pluck="parent"
    )

    task_ids = "', '".join(parent_task_pic) if parent_task_pic else ''

    return f"( tabTasks.owner = '{user_id}' OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE owner = '{user_id}' OR assigned_by = '{employee_id}') OR tabTasks.name IN ('{task_ids}') OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE name IN ('{maintask_ids}')) OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE name IN ('{assign_by_maintask_ids}')))"


@frappe.whitelist()
def user_edit_tasks(task_name):
    if frappe.session.user == "Administrator":
        return "admin"

    doc = frappe.get_doc("Tasks", task_name)
    employee_id = frappe.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee_id:
        return "none"

    parent_task_pic = frappe.get_all(
        "Task PIC",
        filters={"employee": employee_id},
        pluck="parent"
    )

    print(f'{type(parent_task_pic)} type, parent_task_pic value {parent_task_pic}')
    if doc.name in parent_task_pic:
        return "task_pics"

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
    maintask = frappe.get_doc("MainTask", doc.maintask)

    if ptype == "delete":
        if doc.owner == user:
            return True

        parent_task_pic = frappe.get_all(
            "Task PIC",
            filters={"employee": employee_id},
            pluck="parent"
        )

        parent_assign_by = frappe.get_all(
            "MainTask Assign By",
            filters={"employee": employee_id},
            pluck="parent"
        )

        print(f'{type(parent_task_pic)} type, parent_task_pic value {parent_task_pic}')
        if doc.name in parent_task_pic and maintask.owner != user and doc.maintask not in parent_assign_by:
            frappe.throw(
                f"{employee.employee_name} is the pic task only and not allowed to deleting {doc.task_name} task.",
                frappe.PermissionError)
            return False

        check_finished_subtask = frappe.get_all("SubTask", {"tasks": doc.name}, pluck="status")
        if "Done" in check_finished_subtask:
            frappe.throw(
                f"Sorry {employee.employee_name} one of the subtasks in this task is evaluated, you can't delete it.",
                frappe.PermissionError)
            return False
    else:
        return True

    if doc.maintask:
        if maintask.owner == frappe.session.user or employee_id == maintask.assigned_by:
            return True

    frappe.throw(f"{employee.employee_name} is not allowed to acessing {doc.task_name} task.", frappe.PermissionError)
    return False


@frappe.whitelist()
def get_employees_by_role_and_team(doctype, txt, searchfield, start, page_len, filters):
    maintask = filters.get("maintask")
    if not maintask:
        return []

    txt = txt or ""

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
                                  LIMIT %(page_len)s
                              OFFSET %(start)s
                              """, {
        "maintask": maintask,
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })

    return [(emp[0], emp[1]) for emp in employees]


@frappe.whitelist()
def get_open_maintask_as_the_owner(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user

    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    conditions = ""
    if user != "Administrator":
        conditions = """WHERE (mt.owner = %(user)s) 
        OR mt.name IN ( SELECT mt2.name FROM `tabMainTask` mt2 LEFT JOIN `tabMainTask Assign By` m_assign_by2 ON mt2.name = m_assign_by2.parent  WHERE m_assign_by2.employee = %(employee_id)s ) AND mt.status = 'Open'"""

    maintasks = frappe.db.sql(f"""
        SELECT mt.name, mt.maintask_name
        FROM `tabMainTask` mt
       {conditions}
        GROUP BY mt.name
    """, {
        "user": f"{user}",
        "employee_id": f"{employee_id}"
    })
    return maintasks
