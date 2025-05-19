# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _, throw
from frappe.utils import getdate, today


class MainTask(Document):
    def validate(self):
        self.validate_date()

    def validate_date(self):
        if self.assign_date and getdate(self.assign_date) < getdate(today()):
            throw(_("Assign date cannot be later than today."))

        self.validate_from_to_dates("assign_date", "due_date")

