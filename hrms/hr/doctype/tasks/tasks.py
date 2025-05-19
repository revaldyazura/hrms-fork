# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
from html5lib.treeadapters.sax import prefix

import frappe
from frappe import _, scrub, throw
from frappe.model.document import Document


class Tasks(Document):
    def validate(self):
        self.validate_task_name()

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

def on_update(doc, method):
    if frappe.flags.in_update:
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
