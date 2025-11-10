# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname

class Skill(Document):
	def autoname(self):
		if self.designation and self.skill_name:
			base = f"{self.skill_name} ({self.designation})"
			self.name = base
		else:
			if not self.skill_name:
				frappe.throw("Skill Name is required to autoname the Skill record")
			if not self.designation:
				frappe.throw("Designation is required to autoname the Skill record")
