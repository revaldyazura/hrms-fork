# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class PipelineRecruitment(Document):
    def validate_employee_name(self):
         self.employee_name = frappe.db.get_value("Employee", {"name": self.naming_series}, "employee_name")
         self.team_name = frappe.db.get_value("Employee", {"name": self.team}, "employee_name")

	
@frappe.whitelist()
def get_hr_user_and_manager_employees():
    hr_roles = ["HR User"]
    users = frappe.db.sql("""
        SELECT DISTINCT parent
        FROM `tabHas Role`
        WHERE role IN %(roles)s
    """, {"roles": tuple(hr_roles)}, as_dict=True)
    user_ids = [u.parent for u in users if u.parent and u.parent not in ["Guest", "Administrator"]]

    employees = frappe.get_all(
        "Employee",
        filters={"user_id": ["in", user_ids], "status": "Active"},
        fields=["name", "employee_name"]
    )
    return [e.name for e in employees]

@frappe.whitelist()
def get_hr_interviewer_emails():
    hr_roles = ["HR User"]
    users = frappe.db.sql("""
        SELECT DISTINCT parent
        FROM `tabHas Role`
        WHERE role IN %(roles)s
    """, {"roles": tuple(hr_roles)}, as_dict=True)
    user_ids = [u.parent for u in users if u.parent and u.parent not in ["Guest", "Administrator"]]

    emails = frappe.db.get_all(
        "User",
        filters={"name": ["in", user_ids], "enabled": 1},
        fields=["email", "full_name"]
    )
    return [
        {"value": e.email, "label": f"{e.full_name} ({e.email})"} for e in emails if e.email
    ]

@frappe.whitelist()
def get_hr_user_recruiters():
    users = frappe.get_all("Has Role", filters={"role": "HR User"}, fields=["parent"])
    user_ids = [u.parent for u in users]

    recruiters = frappe.get_all("Employee", filters={"owner": ["in", user_ids]}, fields=["name"])
    return [r.name for r in recruiters]