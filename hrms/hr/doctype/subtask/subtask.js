// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("SubTask", {
	refresh(frm) {
		frm.fields_dict['status'].$input.on('change', function () {
			var selectedOption = $(this).val();
			if (selectedOption === 'Cancel') {
				$(this).css('color', 'red');
			} else if (selectedOption === 'Done') {
				$(this).css('color', 'green');
			}
		});
	},
	onload: function (frm) {
		frm.set_query("tasks", function () {
			return {
				query: "hrms.hr.doctype.subtask.subtask.get_task_with_same_pic"
			};
		});
		frm.set_query("pic_subtask", function () {
			if (!frm.doc.tasks) {
				frappe.msgprint("Choose the task field first.");
				return {};
			}
			return {
				query: "hrms.hr.doctype.subtask.subtask.get_employees_by_team",
				filters: {
					tasks: frm.doc.tasks
				}
			};
		});
		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.subtask.subtask.user_edit_subtask",
				args: {
					subtask_name: frm.doc.name
				},
				callback: function (r) {
					const readonly_fields = ['task_name', 'target_time', 'maintask', 'tasks', "pic_subtask", "value", "status"];
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

});
