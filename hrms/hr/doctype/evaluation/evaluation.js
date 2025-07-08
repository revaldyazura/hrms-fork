// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Evaluation", {
	onload: function (frm) {
		// frm.set_query("subtask", function () {
		// 	return {filters: [["SubTask", "status", "=", "Open"]]};
		// });
		frm.set_query("subtask", function () {
			return {
				query: "hrms.hr.doctype.evaluation.evaluation.get_open_subtask_as_owner"
			};
		});
		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.evaluation.evaluation.user_edit_evaluation",
				args: {
					subtask: frm.doc.subtask
				},
				callback: function (r) {
					const readonly_fields = ["subtask", "performance"];
					if (r.message === "pic_subtask") {
						readonly_fields.forEach(field => {
							frm.set_df_property(field, "read_only", 1);
						});
					} else if (r.message === "none") {
						frm.set_read_only(true);
						frm.disable_save();
					}
				}
			});
		}
	},
	refresh(frm) {

	},
});
