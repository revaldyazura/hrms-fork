// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tasks", {
	refresh(frm) {

	},
	onload: function (frm) {

		frm.set_query("maintask", function () {
			return {
				query: "hrms.hr.doctype.tasks.tasks.get_open_maintask_as_the_owner"
			};
		});
		frm.set_query("pic_task", function () {
			if (!frm.doc.maintask) {
				frappe.msgprint("Choose the main task field first.");
				return {};
			}
			return {
				query: "hrms.hr.doctype.tasks.tasks.get_employees_by_role_and_team",
				filters: {
					maintask: frm.doc.maintask
				}
			};
		});
		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.tasks.tasks.user_edit_tasks",
				args: {
					task_name: frm.doc.name
				},
				callback: function (r) {
					const readonly_fields = ['target_time', 'maintask', "pic_task"];
					if (r.message === "pic_task") {
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
});
