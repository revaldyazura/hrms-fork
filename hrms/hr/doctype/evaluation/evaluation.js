// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Evaluation", {
	onload: function (frm) {
		// frm.set_query("subtask", function () {
		// 	return {filters: [["SubTask", "status", "=", "Open"]]};
		// });
		frm.set_query("subtask", function () {
			return {
				query: "hrms.hr.doctype.evaluation.evaluation.get_done_subtask_as_evaluator"
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
		if (frm.is_new()) {
			frm.add_custom_button(__('Bulk Evaluation'), () => {
				frappe.set_route('evaluate-subtasks');
			}, __('Actions'));
		}
		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.evaluation.evaluation.user_edit_evaluation",
				args: {
					subtask: frm.doc.subtask
				},
				callback: function (r) {
					frm.set_df_property('subtask', 'read_only', 1);
					const readonly_fields = ["performance"];
					const msg = r.message;
					const hasFlag = (flag) => {
						if (!msg && msg !== 0) return false;
						if (Array.isArray(msg)) return msg.indexOf(flag) !== -1;
						return String(msg).includes(flag);
					};

					if (hasFlag("none")) {
						frm.set_read_only(true);
						frm.disable_save();
						return;
					}

					// Determine whether the current user should be allowed to edit `performance`.
					// Allow edit when user has higher hierarchy or relevant ownership/assignment flags.
					const allowEdit = hasFlag("owner_evaluation") || hasFlag("owner_maintask") || hasFlag("admin") || hasFlag("assign_by_maintask") || hasFlag("assign_by_maintask_supervisor") || hasFlag("assign_by_maintask_manager");

					if (!allowEdit || hasFlag("pic_subtask_only")) {
						readonly_fields.forEach(field => {
							frm.set_df_property(field, "read_only", 1);
						});
					} else {
						// ensure editable for allowed roles
						readonly_fields.forEach(field => {
							frm.set_df_property(field, "read_only", 0);
						});
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

		// Add the Bulk Evaluation shortcut in a reliable hook.
		// `onload` runs once; `refresh` runs on every load/reload and after saves.
		const bulk_label = __('Bulk Evaluation');
		if (!frm.custom_buttons || !frm.custom_buttons[bulk_label]) {
			frm.add_custom_button(bulk_label, () => {
				frappe.set_route('evaluate-subtasks');
			}, __('Actions'));
		}

	},
});
