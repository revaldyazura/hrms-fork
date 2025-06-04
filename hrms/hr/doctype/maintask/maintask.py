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
        self.validate_date()

    def validate_date(self):
        # if self.assign_date and getdate(self.assign_date) < getdate(today()):
        #     throw(_("Assign date cannot be later than today."))

        self.validate_from_to_dates("assign_date", "due_date")


def update_fields(doc, method):
    if frappe.flags.in_update:
        frappe.msgprint('in update maintask update_fields')
        return
    frappe.flags.in_update = True
    assign_date = get_datetime(doc.assign_date).date()
    due_date = get_datetime(doc.due_date).date()

    number_of_working_days = 0
    current_date = assign_date

    while current_date <= due_date:
        if current_date.weekday() < 5:  # 0 = Monday, ..., 4 = Friday
            number_of_working_days += 1
        current_date += timedelta(days=1)

    doc.total_time = number_of_working_days * 480
    print(f'total time {doc.total_time}')
    doc.save(ignore_permissions=True)
    frappe.flags.in_update = False

def permission_query_conditions(doc, ptype=None, user=None, debug=False):
    user_id = user or frappe.session.user

    print(f'{user_id} is the user')

    roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")
    print(f'{roles} is user roles')
    if "System Manager" in roles:
        return ""

    employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")
    # pic_tasks = frappe.get_all("Tasks", filters={"maintask": doc.name}, pluck="pic_task")
    print((f'employee id: {employee_id}'))
    if not employee_id:
        return "1=0"

    return f"(tabMainTask.assigned_by = '{employee_id}' OR tabMainTask.owner = '{user_id}')"
