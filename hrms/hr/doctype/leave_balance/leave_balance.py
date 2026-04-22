# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LeaveBalance(Document):
	def autoname(self):
		prefix = "LB"
		today = frappe.utils.getdate(frappe.utils.nowdate())
		year = today.year

		employee_join_date = frappe.db.get_value("Employee", self.employee, "date_of_joining")
		if not employee_join_date:
			frappe.throw("Employee Joining Date is not found")

		join_date = frappe.utils.getdate(employee_join_date)
		if not join_date:
			frappe.throw("Employee Joining Date is invalid")

		# Bucket by service anniversaries (not by calendar year difference):
		# - < 1 year since joining  -> 1
		# - < 2 years since joining -> 2
		# - >= 2 years since joining -> 3
		if today < frappe.utils.add_years(join_date, 1):
			suffix = "1"
		elif today < frappe.utils.add_years(join_date, 2):
			suffix = "2"
		else:
			suffix = "3"

		self.name = f"{prefix}-{year}-{self.employee}-{suffix}"


