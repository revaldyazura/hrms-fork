// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tasks", {
	refresh(frm) {

	},
	onload: function (frm) {
		frm.set_query("pic_task", function () {
			return {
				query: "hrms.hr.doctype.tasks.tasks.get_employees_by_user_role"
			};
		});
		frm.set_query("maintask", function () {
			return {
				query: "hrms.hr.doctype.tasks.tasks.get_maintask_as_the_owner"
			};
		});
	},
});
