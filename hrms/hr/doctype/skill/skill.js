// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Skill", {
	onload(frm) {
		// Auto-set Designation when creating a new Skill from within a Designation document's child table
		if (frm.is_new() && !frm.doc.designation) {
			// 1. Use route_options if explicitly passed
			if (frappe.route_options && frappe.route_options.designation) {
				frm.set_value("designation", frappe.route_options.designation);
				// clear so it doesn't leak to other new forms
				delete frappe.route_options.designation;
				return;
			}

			// 2. Fallback: infer from previous route (e.g., coming from a Designation form)
			const prev_route = frappe.get_prev_route && frappe.get_prev_route();
			// prev_route is typically ["Form", "Designation", "DES-0001"]
			if (prev_route && prev_route[1] === "Designation" && prev_route[2]) {
				frm.set_value("designation", prev_route[2]);
			}
		}
	}
});
