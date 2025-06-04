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
	onload: function(frm) {
		frm.set_query("tasks", function () {
			return {
				query: "hrms.hr.doctype.subtask.subtask.get_task_with_same_pic"
			};
		});
	}
});
