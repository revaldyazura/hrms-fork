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
							const dialog = new frappe.ui.Dialog({
								title: "Evaluate SubTask",
								fields: [
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
										reqd: 1,
										description: "Grade of the selected subtask (1–120)"
									}
								],
								primary_action_label: "Submit",
								primary_action(values) {
									const perf = parseInt(values.performance);

									if (isNaN(perf) || perf < 0 || perf > 120) {
										frappe.msgprint({
											title: __("Invalid Input"),
											message: __("Performance must be a number between 0 and 120."),
											indicator: "red"
										});
										return;
									}

									frappe.call({
										method: "frappe.client.insert",
										args: {
											doc: {
												doctype: "Evaluation",
												subtask: values.subtask,
												performance: perf
											}
										},
										callback: function (r) {
											if (!r.exc) {
												frappe.msgprint("Evaluation submitted successfully.");
												dialog.hide();
											}
										}
									});
								}
							});

							dialog.show();

							// Tambahkan validasi real-time setelah dialog dirender
							setTimeout(() => {
								const input = dialog.fields_dict.performance.$wrapper.find("input");

								input.on("input", function () {
									let value = $(this).val();

									// Hapus karakter non-digit
									if (!/^\d*$/.test(value)) {
										frappe.msgprint({
											title: __("Invalid Input"),
											message: __("Only numeric values are allowed."),
											indicator: "red"
										});
										$(this).val(value.replace(/\D/g, ''));
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
							}, 100);
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
		frappe.after_ajax(() => {
			// Tunggu hingga field tersedia di DOM
			setTimeout(() => {
				const field_wrapper = frm.fields_dict["target_time"];
				if (!field_wrapper) return;

				const input = field_wrapper.$wrapper.find("input");

				input.on("input", function () {
					let value = $(this).val();

					// Cek apakah hanya angka
					if (!/^\d*$/.test(value)) {
						frappe.msgprint({
							title: __("Invalid Input"),
							message: __("Only numeric values are allowed in Target Time."),
							indicator: "red"
						});
						$(this).val(value.replace(/\D/g, ""));
					}
					if (value === "0") {
						frappe.msgprint({
							title: __("Invalid Value"),
							message: __("Target Time must be greater than 0."),
							indicator: "red"
						});
						$(this).val("1"); // Kosongkan input
						return;
					}
				});
			}, 300);
			setTimeout(() => {
				const field_wrapper = frm.fields_dict["subtask_name"];
				if (!field_wrapper) return;

				const input = field_wrapper.$wrapper.find("input");

				input.on("input", function () {
					const value = $(this).val();
					if (value.length === 140) {
						frappe.msgprint({
							title: __("Limit Reached"),
							message: __("You have reached the maximum of 140 characters for SubTask Title."),
							indicator: "yellow"
						});
						$(this).val(value.slice(0, 140)); // potong string agar tetap maksimal 140
					}
				});
			}, 300);
			// Delay sedikit agar field render dulu
		});
		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.subtask.subtask.user_edit_subtask",
				args: {
					subtask_name: frm.doc.name
				},
				callback: function (r) {
					const readonly_fields = ['subtask_name', 'target_time', 'unit_target_time', 'maintask', 'tasks', "pic_subtask", "value", "status", 'type'];
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
