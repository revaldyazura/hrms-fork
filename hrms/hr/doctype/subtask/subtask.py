# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, throw
from frappe.model.document import Document


class SubTask(Document):
    def validate(self):
        self.validate_subtask_name()
        self.validate_target_time()

    def validate_target_time(self):
        tasks = frappe.get_doc("Tasks", self.tasks)
        subtask_target_time = frappe.get_all("SubTask", filters={"tasks": tasks, "name": ["!=", self.name]}, fields=["target_time"])
        calculated_target_time = 0
        print(subtask_target_time)
        for t in subtask_target_time:
            print(f'loop t = {t}')
            calculated_target_time += t.get("target_time") or 0
        calculated_target_time += self.target_time
        print(f'calculated tasks time {calculated_target_time}')
        print(f'task target time {tasks.target_time}')
        if calculated_target_time > tasks.target_time:
            throw(
                _("Total all subtasks target time exceeds the task target time, please adjust it again okay?"))
    def validate_subtask_name(self):
        task = frappe.get_doc("Tasks", self.tasks)
        maintask = frappe.get_doc("MainTask", task.maintask)
        team = maintask.team
        prefix_subtask = self.subtask_name.split("-")[0].upper()
        if prefix_subtask != team:
            throw(_("Please put the subtask name properly, as shown in description."))
    # def validate_subtask_name(self):
    #         team = frappe.get_all("Team", fields=["id"])
    #         team_ids = [t.id for t in team]
    #         prefix_subtask = self.subtask_name.split("-")[0].upper()
    #         if prefix_subtask not in team_ids:
    #             throw(_("Please put the subtask name properly, as shown in description."))


def update_fields(doc, method):
    if frappe.flags.in_update:
        frappe.msgprint(f"in update (subtask update_field)")
        return
    frappe.flags.in_update = True

    task = frappe.get_doc("Tasks", doc.tasks)
    subtasks = frappe.get_all("SubTask", filters={"tasks": doc.tasks}, fields=["status"])
    maintask = frappe.get_doc("MainTask", task.maintask)
    statuses = [s.status for s in subtasks]

    subtask_name_splitted = doc.subtask_name.split("-")
    prefix = subtask_name_splitted[0].upper()
    subtask_name = "-".join([prefix] + subtask_name_splitted[1:])
    doc.subtask_name = subtask_name
    doc.maintask = maintask
    doc.save(ignore_permissions=True)

    frappe.flags.in_update = False

    original_status = task.status

    if all(s == "Done" for s in statuses):
        if task.status != "Done":
            task.status = "Done"
    elif all(s == "Hold" for s in statuses):
        if task.status != "Hold":
            task.status = "Hold"
    elif all(s == "Cancel" for s in statuses):
        if task.status != "Cancel":
            task.status = "Cancel"
    else:
        task.status = "Open"

    if task.status != original_status:
        task.save(ignore_permissions=True)
        frappe.msgprint(f"Task '{task.task_name}' status updated to {task.status} based on Subtasks.")


def permission_query_conditions(doc, ptype=None, user=None, debug=False):
    user_id = user or frappe.session.user

    print(f'{user_id} is the user')

    roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")
    print(f'{roles} is user roles')
    if "System Manager" in roles:
        return ""

    employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")
    print((f'employee id: {employee_id}'))
    if not employee_id:
        return "1=0"

    return  f"""
        (`tabSubTask`.`pic_subtask` = '{employee_id}'
        OR `tabSubTask`.`owner` = '{user_id}'
        OR `tabSubTask`.`tasks` IN (
            SELECT `name` FROM `tabTasks` WHERE `owner` = '{user_id}'
        ) OR `tabSubTask`.`maintask` IN (SELECT `name` FROM `tabMainTask` WHERE `assigned_by` = '{employee_id}'))
    """

@frappe.whitelist()
def get_task_with_same_pic(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user
    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    tasks = frappe.db.sql("""
        SELECT t.name, t.task_name, t.pic_task
        FROM `tabTasks` t
        WHERE t.pic_task = %(employee_id)s
        GROUP BY t.name
    """, {
        "employee_id": f"{employee_id}"
    })
    return tasks
