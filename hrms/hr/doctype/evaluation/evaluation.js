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
