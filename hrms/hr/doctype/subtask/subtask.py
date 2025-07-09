# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, throw
from frappe.model.document import Document
from datetime import datetime


class SubTask(Document):
    def validate(self):
        print("validate subtask called")
        self.validate_subtask_name()

    def validate_subtask_name(self):
        self.maintask_name = frappe.db.get_value("MainTask", {"name": self.maintask}, "maintask_name")
        self.tasks_name = frappe.db.get_value("Tasks", {"name": self.tasks}, "task_name")
        self.pic_subtask_name = frappe.db.get_value("Employee", {"name": self.pic_subtask}, "employee_name")
        self.created_by = frappe.db.get_value("Employee", {"user_id": self.owner}, "employee_name")
        if self.status == "Open":
            self.subtask_open_date = datetime.strptime(self.creation, "%Y-%m-%d %H:%M:%S.%f").date() if isinstance(
                self.creation, str) else self.creation.date()
        if self.unit_target_time == "Hours":
            self.target_time_minutes = self.target_time * 60
        else:
            self.target_time_minutes = self.target_time

    # def validate_pic_subtask_name(self)
    #     self.

    # self.validate_evaluated_subtask()

    # def validate_evaluated_subtask(self):
    #     evaluation = frappe.db.get_value("Evaluation", {"subtask": self.name}, "subtask")
    #     if evaluation:
    #         employee_name = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "employee_name")
    #         throw(_(f"Sorry {employee_name} this subtask is evaluated, you can't edit it."))


def update_fields(doc, method):
    if frappe.flags.in_update:
        frappe.msgprint(f"In update SubTask")
        return
    frappe.flags.in_update = True
    print("update fields subtask called")
    task = frappe.get_doc("Tasks", doc.tasks)
    maintask = frappe.get_doc("MainTask", task.maintask)
    doc.maintask = maintask.name
    if doc.status == 'Done':
        doc.subtask_done_date = datetime.strptime(doc.modified, "%Y-%m-%d %H:%M:%S.%f").date() if isinstance(
            doc.modified, str) else doc.modified.date()
    elif doc.status == 'Open':
        doc.subtask_done_date = None
    doc.save(ignore_permissions=True)

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

    return f"""
        (`tabSubTask`.`pic_subtask` = '{employee_id}'
        OR `tabSubTask`.`owner` = '{user_id}'
        OR `tabSubTask`.`tasks` IN (
            SELECT `name` FROM `tabTasks` WHERE `owner` = '{user_id}'
        ) OR `tabSubTask`.`maintask` IN (SELECT `name` FROM `tabMainTask` WHERE `assigned_by` = '{employee_id}' OR `owner` = '{user_id}') OR `tabSubTask`.`maintask` IN (SELECT `name` FROM `tabMainTask` WHERE name IN ('{maintask_ids}')))
    """


@frappe.whitelist()
def user_edit_subtask(subtask_name):
    if frappe.session.user == "Administrator":
        return "admin"

    doc = frappe.get_doc("SubTask", subtask_name)
    employee_id = frappe.get_value("Employee", {"user_id": frappe.session.user}, "name")

    if not employee_id:
        return "none"

    if doc.tasks:
        tasks = frappe.get_doc("Tasks", doc.tasks)
        pic_task = tasks.pic_task
        owner_task = tasks.owner

        parent_task_pic = frappe.get_all(
            "Task PIC",
            filters={"employee": employee_id},
            pluck="parent"
        )

        print(f'{type(parent_task_pic)} type, parent_task_pic value {parent_task_pic}')
        if tasks.name in parent_task_pic:
            return "task_pics"

        if doc.pic_subtask == employee_id and pic_task != employee_id:
            return "pic_subtask"
        if pic_task == employee_id:
            return "pic_task"
        if owner_task == frappe.session.user:
            return "owner_task"

    return "none"


def has_permission(doc, ptype, user):
    print("has permission subtask called")

    if user == "Administrator":
        return True

    if ptype in ("read", None):
        return True

    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
    if not employee_id:
        return False

    employee = frappe.get_doc("Employee", employee_id)
    tasks = frappe.get_doc("Tasks", doc.tasks)
    pic_task = tasks.pic_task

    parent_task_pic = frappe.get_all(
        "Task PIC",
        filters={"employee": employee_id},
        pluck="parent"
    )
    if ptype == "delete":
        maintask = frappe.get_doc("MainTask", doc.maintask)
        if doc.pic_subtask == employee_id and pic_task != employee_id and doc.tasks not in parent_task_pic and employee_id != maintask.assigned_by and maintask.owner != user:
            frappe.throw(f"{employee.employee_name} is not allowed to deleting {doc.subtask_name} subtask.",
                         frappe.PermissionError)
            return False
        check_evaluated = frappe.get_value("Evaluation", {"subtask": doc.name}, "subtask")
        if check_evaluated:
            frappe.throw(_(f"Sorry {employee.employee_name} this subtask is evaluated, you can't delete it.",
                           frappe.PermissionError))
            return False
    elif doc.pic_subtask == employee_id and ptype != "delete":
        return True

    if doc.tasks:
        owner_task = tasks.owner
        print(f'doc tasks {doc.tasks}, parent_task_pic {parent_task_pic}')
        if pic_task == employee_id or owner_task == frappe.session.user or doc.tasks in parent_task_pic:
            return True

    frappe.throw(f"{employee.employee_name} is not allowed to accessing {doc.subtask_name} subtask.",
                 frappe.PermissionError)
    return False


@frappe.whitelist()
def get_employees_by_team(doctype, txt, searchfield, start, page_len, filters):
    tasks = filters.get("tasks")
    if not tasks:
        return []
    task_doc = frappe.get_doc("Tasks", tasks)
    maintask = task_doc.maintask

    employees = frappe.db.sql("""
                              SELECT e.name, e.employee_name
                              FROM `tabEmployee` e
                                       JOIN `tabUser` u ON u.name = e.user_id
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
    return employees


@frappe.whitelist()
def get_task_with_same_pic(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user
    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    conditions = ""
    if user != "Administrator":
        conditions = "WHERE tp.employee = %(employee_id)s AND t.status = 'Open' AND (t.name LIKE %(txt)s OR t.task_name LIKE %(txt)s)"

    tasks = frappe.db.sql(f"""
        SELECT t.name, t.task_name
        FROM `tabTasks` t
        JOIN `tabTask PIC` tp ON tp.parent = t.name
        {conditions}
        GROUP BY t.name
        ORDER BY t.name
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        "employee_id": employee_id,
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    })
    return tasks
