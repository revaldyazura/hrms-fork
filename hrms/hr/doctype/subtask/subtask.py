# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, throw
from frappe.model.document import Document


class SubTask(Document):
    def validate(self):
        self.validate_subtask_name()

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

def on_update(doc, method):
    if frappe.flags.in_update:
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


