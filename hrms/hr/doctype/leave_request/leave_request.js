// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Leave Request", {
	setup(frm) {
		frm.trigger("setup_employees_replacement_row_restrictions");
	},
	onload(frm) {
		frm.trigger("reset_and_set_fields_for_new_leave_request");
		frm.trigger("apply_rejected_reason_requirements");
	},
	onload_post_render(frm) {
		frm.trigger("apply_read_only");
		// Grid rows may finish rendering after refresh on first load.
		frm.trigger("reset_and_set_fields_for_new_leave_request");
		frm.trigger("apply_employees_replacement_row_restrictions");
		frm.trigger("bind_employees_replacement_grid_interaction_handlers");
		frm.trigger("apply_employees_replacement_add_row_restrictions");
		frm.trigger("apply_manager_approver_restrictions");
		frm.trigger("apply_rejected_reason_requirements");
	},
	refresh(frm) {
		frm.trigger("apply_read_only");
		frm.trigger("reset_and_set_fields_for_new_leave_request");
		frm.trigger("setup_employees_replacement_row_restrictions");
		frm.trigger("apply_employees_replacement_row_restrictions");
		frm.trigger("bind_employees_replacement_grid_interaction_handlers");
		frm.trigger("apply_employees_replacement_add_row_restrictions");
		frm.trigger("apply_manager_approver_restrictions");
		frm.trigger("apply_rejected_reason_requirements");
	},
	before_save(frm) {
		// Intentionally do not reset/clear fields on save.
		// The new-doc reset is handled once during onload to avoid wiping user inputs.
	},
	validate(frm) {
		validate_rejected_reasons(frm);
	},

	manager_decision(frm) {
		frm.trigger("apply_rejected_reason_requirements");
	},
	manager_reason(frm) {
		frm.trigger("apply_rejected_reason_requirements");
	},
	hr_decision(frm) {
		frm.trigger("apply_rejected_reason_requirements");
	},
	hr_reason(frm) {
		frm.trigger("apply_rejected_reason_requirements");
	},

	apply_rejected_reason_requirements(frm) {
		apply_rejected_reason_requirements(frm);
	},

	reset_and_set_fields_for_new_leave_request(frm) {
		if (!frm?.is_new?.()) return;
		// Avoid repeatedly wiping while user is typing within the same session.
		if (frm.__leave_request_new_doc_reset_done) return;
		frm.__leave_request_new_doc_reset_done = true;

		const user = frappe.session.user;
		// Set employee to current user's employee if possible (for convenience, and to ensure correct employee mapping for row restrictions).
		if (!frm.doc.employee) {
			frappe.db
				.get_value("Employee", { user_id: user }, "name")
				.then((res) => {
					if (res?.message?.name) {
						frm.set_value("employee", res.message.name);
					}
				});
		}
		if (!frm.doc.posting_date) {
			frm.set_value("posting_date", frappe.datetime.get_today());
		}

		// Text Editor fields: force empty
		frm.set_value("description", "");
		frm.set_value("hr_reason", "");
		frm.set_value("manager_reason", "");

		frm.set_value("leave_type", "");
		frm.set_value("sub_leave_type", "");
		frm.set_value("total_leave_days", "");

		// Select fields: force default Pending
		frm.set_value("hr_decision", "Pending");
		frm.set_value("manager_decision", "Pending");
		frm.set_value("replacements_final_decision", "Pending");
		frm.set_value("final_status", "Pending");

		// Child table: clear
		try {
			frappe.model.clear_table(frm.doc, "employees_replacement");
			frappe.model.clear_table(frm.doc, "leave_dates");
			frappe.model.clear_table(frm.doc, "supporting_documents");
		} catch (e) {
			frm.doc.employees_replacement = [];
			frm.doc.leave_dates = [];
			frm.doc.supporting_documents = [];
			// ignore if tables don't exist yet (can happen if child doctypes are modified)
		}
		frm.refresh_field("employees_replacement");
		frm.refresh_field("leave_dates");
		frm.refresh_field("supporting_documents");
	},

	async setup_employees_replacement_row_restrictions(frm) {
		// Restrict editing replacement rows to the logged-in employee (unless privileged).
		// This is UI-only; server-side validation should still be relied on for security.
		if (frm.__employees_replacement_restrictions_setup) return;
		frm.__employees_replacement_restrictions_setup = true;

		frm.__leave_request_replacement_warned_rows = new Set();

		$(frm.wrapper)
			.off("grid-row-render.leave_request_employees_replacement")
			.on(
				"grid-row-render.leave_request_employees_replacement",
				(e, grid_row) => {
					if (!grid_row?.grid?.df) return;
					if (grid_row.grid.df.fieldname !== "employees_replacement") return;
					if (!should_apply_replacement_row_restrictions(frm)) return;

					if (frm.is_new?.()) {
						apply_row_restrictions_to_grid_row(grid_row, null, frm);
						return;
					}

					ensure_current_employee(frm).then((current_employee) => {
						apply_row_restrictions_to_grid_row(grid_row, current_employee, frm);
					});
				}
			);
	},

	bind_employees_replacement_grid_interaction_handlers(frm) {
		// Enforce at interaction-time for inline editable grid.
		// Must be bound after the grid wrapper exists (first load can be late).
		const grid_wrapper = frm.fields_dict?.employees_replacement?.grid?.wrapper;
		if (!grid_wrapper) return;
		if (frm.__leave_request_replacement_grid_handlers_bound) return;
		frm.__leave_request_replacement_grid_handlers_bound = true;

		$(grid_wrapper)
			.off("focusin.leave_request_employees_replacement")
			.off("mousedown.leave_request_employees_replacement")
			.off("click.leave_request_employees_replacement")
			.on(
				"focusin.leave_request_employees_replacement mousedown.leave_request_employees_replacement click.leave_request_employees_replacement",
				(e) => {
					if (!should_apply_replacement_row_restrictions(frm)) return;

					const $field_container = $(e.target).closest(
						"[data-fieldname='status'], [data-fieldname='reason']"
					);
					if (!$field_container.length) return;

					const fieldname = $field_container.attr("data-fieldname");
					if (!["status", "reason"].includes(fieldname)) return;

					const $grid_row_el = $(e.target).closest(".grid-row");
					const row_docname = $grid_row_el.attr("data-name");
					if (!row_docname) return;

					const grid = frm.fields_dict?.employees_replacement?.grid;
					const grid_row = grid?.get_row?.(row_docname);
					const row_doc = grid_row?.doc;
					if (!row_doc) return;

					if (frm.is_new?.()) {
						e.preventDefault();
						e.stopImmediatePropagation();
						try {
							$(e.target).blur();
						} catch (err) {
							// ignore
						}

						apply_row_restrictions_to_grid_row(grid_row, null, frm);

						if (!frm.__leave_request_replacement_warned_rows.has(row_docname)) {
							frm.__leave_request_replacement_warned_rows.add(row_docname);
							frappe.msgprint({
								message: __(
									"Status and Reason are locked while creating a new document."
								),
								indicator: "orange",
							});
						}
						return;
					}

					ensure_current_employee(frm).then((current_employee) => {
						const editable = can_edit_replacement_row(row_doc, current_employee, frm);
						if (editable) return;

						e.preventDefault();
						e.stopImmediatePropagation();
						try {
							$(e.target).blur();
						} catch (err) {
							// ignore
						}

						// Re-apply so inputs become disabled/read-only and cell becomes non-interactive.
						apply_row_restrictions_to_grid_row(grid_row, current_employee, frm);

						if (!frm.__leave_request_replacement_warned_rows.has(row_docname)) {
							frm.__leave_request_replacement_warned_rows.add(row_docname);
							frappe.msgprint({
								message: __(
									"You can only edit Status and Reason for your own replacement row."
								),
								indicator: "orange",
							});
						}
					});
				}
			);
	},

	async apply_employees_replacement_row_restrictions(frm) {
		if (!should_apply_replacement_row_restrictions(frm)) return;
		const grid = frm.fields_dict?.employees_replacement?.grid;
		if (!grid) return;

		const current_employee = frm.is_new?.() ? null : await ensure_current_employee(frm);
		// Apply to already-rendered rows (pagination will be covered by grid-row-render event).
		(grid.grid_rows || []).forEach((grid_row) =>
			apply_row_restrictions_to_grid_row(grid_row, current_employee, frm)
		);
	},

	apply_employees_replacement_add_row_restrictions(frm) {
		const grid = frm.fields_dict?.employees_replacement?.grid;
		if (!grid) return;

		const can_add = can_current_user_add_replacement_rows(frm);
		grid.cannot_add_rows = !can_add;
		if (grid.df) {
			grid.df.cannot_add_rows = can_add ? 0 : 1;
		}

		// Update toolbar visibility immediately.
		try {
			grid.setup_toolbar();
		} catch (e) {
			// ignore
		}
	},

	employees_replacement_add(frm) {
		// When a new row is added on an existing document, ensure Status/Reason are locked
		// until employee is set to the current user's employee.
		frm.trigger("apply_employees_replacement_row_restrictions");
	},

	async apply_manager_approver_restrictions(frm) {
		// UI helper: lock Manager fields unless current user is configured as Division Leave Approver.
		// Server-side validation in leave_request.py remains the source of truth.
		if (!frm || frm.is_new?.()) return;
		if (frappe.user.has_role("System Manager")) return;
		let state = frm.doc?.workflow_state;
		if (["Pending Manager", "Rejected Manager", "Approved Manager"].includes(state)) {

			const can_edit = await can_current_user_edit_manager_fields(frm);
			frm.set_df_property("manager_decision", "read_only", can_edit ? 0 : 1);
			frm.set_df_property("manager_reason", "read_only", can_edit ? 0 : 1);
			frm.refresh_field("manager_decision");
			frm.refresh_field("manager_reason");
		}
	},

	async apply_read_only(frm) {
		if (!frm || frm.is_new?.()) return;
		if (frappe.user.has_role("System Manager")) return;

		let state = frm.doc?.workflow_state;

		if (!state) return;

		switch (state) {
			case "Rejected Manager":
			case "Rejected HR":
				frm.set_read_only();
				frm.disable_save();
				break;

			case "Pending HR":
				setEditableFields(['hr_decision', 'hr_reason']);
				frm.set_df_property('hr_decision', 'options', ['Pending', 'Approved', 'Rejected']);
				break;

			case "Pending Manager":
				setEditableFields(['manager_decision', 'manager_reason']);
				break;

			case "Pending Replacement":
			case "Rejected Replacement":
				setEditableFields(['employees_replacement']);
				break;
		}

		function setEditableFields(editableFields) {
			const fields = frm.fields_dict || {};
			Object.keys(fields).forEach((fn) => {
				if (fn && !editableFields.includes(fn)) {
					frm.set_df_property(fn, 'read_only', 1);
				}
			});
		}
	},
});

frappe.ui.form.on("Employee Replacement", {
	form_render(frm, cdt, cdn) {
		if (!should_apply_replacement_row_restrictions(frm)) return;
		const row = locals[cdt]?.[cdn];
		if (!row) return;

		if (frm.is_new?.()) {
			apply_row_restrictions_to_child_form(frm, row, null);
			return;
		}

		ensure_current_employee(frm).then((current_employee) => {
			apply_row_restrictions_to_child_form(frm, row, current_employee);
		});
	},
	status(frm, cdt, cdn) {
		// If status is set to Rejected, make Reason mandatory (for the row that the user can edit).
		const row = locals[cdt]?.[cdn];
		if (!row) return;

		const grid = frm.fields_dict?.employees_replacement?.grid;
		const grid_row = grid?.get_row?.(cdn);
		if (!grid_row) return;

		if (frm.is_new?.()) {
			set_replacement_row_reason_required(grid_row, false);
			return;
		}

		ensure_current_employee(frm).then((current_employee) => {
			const editable = can_edit_replacement_row(row, current_employee, frm);
			const reqd = editable && row.status === "Rejected";
			set_replacement_row_reason_required(grid_row, reqd);
		});
	},

	employee(frm, cdt, cdn) {
		// Re-evaluate Status/Reason lock when employee is set/changed.
		if (!should_apply_replacement_row_restrictions(frm)) return;
		const row = locals[cdt]?.[cdn];
		if (!row) return;

		if (frm.is_new?.()) {
			apply_row_restrictions_to_child_form(frm, row, null);
			return;
		}

		ensure_current_employee(frm).then((current_employee) => {
			apply_row_restrictions_to_child_form(frm, row, current_employee);
		});
	},
});

function should_apply_replacement_row_restrictions(frm) {
	if (!frm) return false;

	// Keep common approval/admin roles unblocked.
	if (
		frappe.user.has_role("System Manager")
	) {
		return false;
	}

	return true;
}

function ensure_current_employee(frm) {
	if (frm.__leave_request_current_employee_promise)
		return frm.__leave_request_current_employee_promise;

	frm.__leave_request_current_employee_promise = (async () => {
		// Try user defaults first (fast path)
		let employee =
			frappe.defaults.get_user_default("Employee") ||
			frappe.defaults.get_user_default("employee");
		if (employee) return employee;

		// Fallback to lookup by user_id
		const res = await frappe.db.get_value(
			"Employee",
			{ user_id: frappe.session.user },
			"name"
		);
		return res?.message?.name || null;
	})();

	return frm.__leave_request_current_employee_promise;
}

function can_current_user_add_replacement_rows(frm) {
	// Allow while creating a new doc (the creator is the current user).
	if (!frm || frm.is_new?.()) return true;

	const owner = frm.doc?.owner;
	if (!owner) return true;
	return owner === frappe.session.user;
}

function can_edit_replacement_row(row_doc, current_employee, frm) {
	// While creating a new doc, lock status & reason regardless of employee mapping.
	if (frm?.is_new?.()) return false;

	// If we can't resolve employee mapping, don't block editing.
	if (!current_employee) return true;
	// On existing docs, lock until employee is set.
	if (!row_doc?.employee) return false;
	return row_doc.employee === current_employee;
}

function apply_row_restrictions_to_grid_row(grid_row, current_employee, frm) {
	const editable = can_edit_replacement_row(grid_row?.doc, current_employee, frm);
	set_replacement_row_fields_editable(grid_row, editable);
	set_replacement_row_reason_required(
		grid_row,
		Boolean(editable && grid_row?.doc?.status === "Rejected")
	);
}

function apply_row_restrictions_to_child_form(frm, row_doc, current_employee) {
	const grid = frm.fields_dict?.employees_replacement?.grid;
	if (!grid || !row_doc?.name) return;
	const grid_row = grid.get_row(row_doc.name);
	if (!grid_row) return;

	const editable = can_edit_replacement_row(row_doc, current_employee, frm);
	set_replacement_row_fields_editable(grid_row, editable);
}

function set_replacement_row_fields_editable(grid_row, editable) {
	if (!grid_row) return;
	// Only lock down these fields as requested.
	["status", "reason"].forEach((fieldname) => {
		try {
			grid_row.toggle_editable(fieldname, editable);

			// Hard-disable interaction in inline grid cell (covers editable_grid quirks).
			const column = grid_row.columns?.[fieldname];
			if (column) {
				column.css("pointer-events", editable ? "" : "none");
			}

			// Ensure inline grid input becomes non-interactive immediately.
			grid_row.refresh_field(fieldname);
			const field = grid_row.on_grid_fields_dict?.[fieldname];
			if (field?.$input) {
				field.$input.prop("disabled", !editable);
			}
		} catch (e) {
			// Ignore missing fields in case the child doctype changes.
		}
	});
}

function set_replacement_row_reason_required(grid_row, reqd) {
	if (!grid_row) return;
	try {
		grid_row.toggle_reqd("reason", reqd);
		grid_row.refresh_field("reason");
	} catch (e) {
		// ignore
	}
}

function apply_rejected_reason_requirements(frm) {
	if (!frm) return;

	const managerRejected = frm.doc?.manager_decision === "Rejected";
	const hrRejected = frm.doc?.hr_decision === "Rejected";

	frm.set_df_property("manager_reason", "reqd", managerRejected ? 1 : 0);
	frm.set_df_property("hr_reason", "reqd", hrRejected ? 1 : 0);
	frm.refresh_field("manager_reason");
	frm.refresh_field("hr_reason");
}

function validate_rejected_reasons(frm) {
	if (!frm) return;

	// Parent fields
	if (frm.doc?.manager_decision === "Rejected" && !frm.doc?.manager_reason) {
		frappe.throw(__("Manager Reason is mandatory when Manager Decision is Rejected."));
	}
	if (frm.doc?.hr_decision === "Rejected" && !frm.doc?.hr_reason) {
		frappe.throw(__("HR Reason is mandatory when HR Decision is Rejected."));
	}

	// Child table rows
	const rows = frm.doc?.employees_replacement || [];
	for (const row of rows) {
		if (row?.status === "Rejected" && !row?.reason) {
			frappe.throw(
				__(
					"Reason is mandatory for Employee Replacement rows with Status Rejected (Employee: {0}).",
					[row.employee || row.employee_name || row.idx]
				)
			);
		}
	}
}

async function can_current_user_edit_manager_fields(frm) {
	if (!frm?.doc?.employee) return false;

	try {
		const res = await frappe.call({
			method:
				"hrms.hr.doctype.leave_request.leave_request.is_current_user_division_leave_approver",
			args: { employee: frm.doc.employee },
		});
		return Boolean(res?.message);
	} catch (e) {
		// Fail closed in UI (server will enforce anyway).
		return false;
	}
}
