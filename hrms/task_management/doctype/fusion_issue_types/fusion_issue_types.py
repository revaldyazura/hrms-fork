# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import json
import uuid
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime, getdate
from frappe.exceptions import DuplicateEntryError


class FusionIssueTypes(Document):
	def autoname(self):
		if self.maintask:
			issue = frappe.get_value("Fusion Issue Types", {"maintask": self.maintask}, "issue")
			if issue == self.issue:
				raise frappe.throw(f"Issue Type '{self.issue}' already exists for the selected Main Task")
			hash = frappe.generate_hash(length=4)
			base = f"{self.issue}-{self.maintask}"
			self.name = base
