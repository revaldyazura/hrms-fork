# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub, throw
from frappe.model.document import Document


class Tasks(Document):
    def validate(self):
        self.validate_task_name()
        self.validate_target_time()

    def validate_target_time(self):
        maintask = frappe.get_doc("MainTask", self.maintask)
        tasks_target_time = frappe.get_all("Tasks", filters={"maintask": maintask, "name": ["!=", self.name]}, fields=["target_time"])
        calculated_target_time = 0
        print(tasks_target_time)
        for t in tasks_target_time:
            print(f'loop t = {t}')
            calculated_target_time += t.get("target_time") or 0
        calculated_target_time += self.target_time
        print(f'calculated tasks time {calculated_target_time}')
        print(f'total time {maintask.total_time}')
        if calculated_target_time > maintask.total_time:
            throw(
                _("Total all tasks target time exceeds the maintask timeframe (assign - due date), please adjust it again okay?"))

    def validate_task_name(self):
        maintask = frappe.get_doc("MainTask", self.maintask)
        team = maintask.team
        prefix_task = self.task_name.split("-")[0].upper()
        if prefix_task != team:
            throw(_("Please put the task name properly, as shown in description."))
    # def validate_task_name(self):
    #         team = frappe.get_all("Team", fields=["id"])
    #         team_ids = [t.id for t in team]
    #         prefix_task = self.task_name.split("-")[0].upper()
    #         if prefix_task not in team_ids:
    #             throw(_("Please put the task name properly, as shown in description."))


def update_fields(doc, method):
    if frappe.flags.in_update:
        frappe.msgprint(f"in tasks update_field")
        return
    frappe.flags.in_update = True

    maintask = frappe.get_doc("MainTask", doc.maintask)
    tasks = frappe.get_all("Tasks", filters={"maintask": doc.maintask}, fields=["status"])
    statuses = [t.status for t in tasks]
    task_name_splitted = doc.task_name.split("-")
    prefix = task_name_splitted[0].upper()
    task_name = "-".join([prefix] + task_name_splitted[1:])
    doc.task_name = task_name
    doc.save(ignore_permissions=True)

    original_status = maintask.status

    if all(s == "Done" for s in statuses):
        if maintask.status != "Done":
            maintask.status = "Done"
    elif all(s == "Hold" for s in statuses):
        if maintask.status != "Hold":
            maintask.status = "Hold"
    elif all(s == "Cancel" for s in statuses):
        if maintask.status != "Cancel":
            maintask.status = "Cancel"
    else:
        maintask.status = "Open"

    if maintask.status != original_status:
        maintask.save(ignore_permissions=True)
        frappe.msgprint(f"MainTask '{maintask.maintask_name}' status updated to {maintask.status} based on Tasks.")


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

    return f"(tabTasks.pic_task = '{employee_id}' OR tabTasks.owner = '{user_id}' OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE owner = '{user_id}' OR assigned_by = '{employee_id}'))"


@frappe.whitelist()
def get_employees_by_user_role(doctype, txt, searchfield, start, page_len, filters):
    employees = frappe.db.sql("""
        SELECT e.name, e.employee_name
        FROM `tabEmployee` e
        JOIN `tabUser` u ON u.name = e.user_id
        JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE hr.role IN ("Leader", "Manager", "HR Manager")
        AND e.status = 'Active'
        AND (e.name LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
        GROUP BY e.name
        ORDER BY e.employee_name
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })
    return employees


@frappe.whitelist()
def get_maintask_as_the_owner(doctype, txt, searchfield, start, page_len, filters):
    user_id = frappe.session.user
    # employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    maintasks = frappe.db.sql("""
        SELECT mt.name, mt.maintask_name
        FROM `tabMainTask` mt
        WHERE mt.owner = %(user_id)s
        GROUP BY mt.name
    """, {
        "user_id": f"{user_id}"
    })
    return maintasks
