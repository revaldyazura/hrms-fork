// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Evaluation", {
	onload: function (frm) {
		// frm.set_query("subtask", function () {
		// 	return {filters: [["SubTask", "status", "=", "Open"]]};
		// });
		frm.set_query("subtask", function () {
			return {
				query: "hrms.hr.doctype.evaluation.evaluation.get_done_subtask_as_owner"
			};
		});
		frappe.after_ajax(() => {
			// Tunggu hingga field tersedia di DOM
			setTimeout(() => {
				const field_wrapper = frm.fields_dict["performance"];
				if (!field_wrapper) return;

				const input = field_wrapper.$wrapper.find("input");

				input.on("input", function () {
					let value = $(this).val();

					// Cek apakah hanya angka
					if (!/^\d*$/.test(value)) {
						frappe.msgprint({
							title: __("Invalid Input"),
							message: __("Only numeric values are allowed in Performance."),
							indicator: "red"
						});
						$(this).val(value.replace(/\D/g, ""));
					}
					if (value === "0") {
						frappe.msgprint({
							title: __("Invalid Value"),
							message: __("Performance must be greater than 0."),
							indicator: "red"
						});
						$(this).val("1"); // Kosongkan input
						return;
					}

					// Batas maksimum
					const numericValue = parseInt($(this).val() || "0");
					if (numericValue > 120) {
						frappe.msgprint("Maximum allowed value is 120.");
						$(this).val("120");
					}
				});
			}, 300); // Delay sedikit agar field render dulu
		});
		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.evaluation.evaluation.user_edit_evaluation",
				args: {
					subtask: frm.doc.subtask
				},
				callback: function (r) {
					const readonly_fields = ["subtask", "performance"];
					if (r.message.includes("pic_subtask") && !r.message.includes("owner_subtask") && !r.message.includes("task_pics") && !r.message.includes("owner_task")) {
						readonly_fields.forEach(field => {
							frm.set_df_property(field, "read_only", 1);
						});
					} else if (r.message.includes("none")) {
						frm.set_read_only(true);
						frm.disable_save();
					}
				}
			});
		}
	},
	refresh(frm) {
		
		let workspace = 'Task Management';
            
        frappe.breadcrumbs.all[frappe.get_route_str()] = {
            workspace: workspace,
            doctype: frm.doctype,
            type: 'Form'
        };
        frappe.breadcrumbs.update();
		
	},
});
