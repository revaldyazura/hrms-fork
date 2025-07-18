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
		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.subtask.subtask.check_if_evaluator",
				args: {
					subtask: frm.doc.name
				},
				callback: function (r) {
					if (r.message === true) {
						frm.add_custom_button("Evaluate This SubTask", () => {
							frappe.prompt([
								{
									label: "SubTask",
									fieldname: "subtask",
									fieldtype: "Read Only",
									default: frm.doc.name
								},
								{
									label: "SubTask Title",
									fieldname: "subtask_name",
									fieldtype: "Read Only",
									default: frm.doc.subtask_name
								},
								{
									label: "PIC SubTask Name",
									fieldname: "pic_subtask_name",
									fieldtype: "Read Only",
									default: frm.doc.pic_subtask_name
								},
								{
									label: "Performance",
									fieldname: "performance",
									fieldtype: "Int",
									reqd: 1
								}
							], (values) => {
								frappe.call({
									method: "frappe.client.insert",
									args: {
										doc: {
											doctype: "Evaluation",
											subtask: values.subtask,
											performance: values.performance
										}
									},
									callback: function (r) {
										if (!r.exc) {
											frappe.msgprint("Evaluation submitted successfully.");
										}
									}
								});
							}, "Evaluate SubTask");
						});
					}
				}
			})

		}
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
