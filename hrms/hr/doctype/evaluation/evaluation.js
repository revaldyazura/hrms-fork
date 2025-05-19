// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Evaluation", {
	onload: function (frm) {
		frm.set_query("subtask", function () {
			return {filters: [["SubTask", "status", "=", "Open"]]};
		});
	},
	refresh(frm) {

	},
});
