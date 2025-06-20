// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("MainTask", {
	refresh(frm) {

	},
	onload: function (frm) {
		if (!frm.is_new()) {
			frappe.call(
				{
					method: "hrms.hr.doctype.maintask.maintask.user_edit_maintask",
					args: {
						maintask_name: frm.doc.name
					},
					callback: function (r) {
						if (r.message === "none") {
							frm.set_read_only(true);
							frm.disable_save();
						}
					}
				}
			)
		}
	}
});
