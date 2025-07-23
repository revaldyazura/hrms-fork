// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("MainTask", {
	refresh(frm) {

	},
	onload: function (frm) {
		if (!frm.is_new()) {
			frappe.call(
				{
					method: "hrms.hr.doctype.maintask.maintask.user_edit_maintask",
					args: {
						maintask_name: frm.doc.name
					},
					callback: function (r) {
						if (r.message === "none") {
							frm.set_read_only(true);
							frm.disable_save();
						}
					}
				}
			)
		}
	}
});
frappe.ui.form.on('MainTask Team', {
  employee: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.employee) return;
	
	const is_duplicate = frm.doc.team.filter(r => r.employee === row.employee).length > 1;
  let employee_name = frappe.model.get_value(cdt, cdn, 'employee_name');
    if (is_duplicate) {
      frappe.msgprint(__('{0} has been choosen as team member', [employee_name || '']));
      frappe.model.set_value(cdt, cdn, 'employee', null);
      frappe.model.set_value(cdt, cdn, 'employee_name', null);
      return;
    }

    // Ambil data employee yang dipilih
    frappe.db.get_doc('Employee', row.employee).then(employee_doc => {
      const reports_to = employee_doc.reports_to;
	  console.log('reports_to', reports_to);
      if (!reports_to) return;

      // Cek apakah sudah ada di child table assign_by
      frappe.db.get_doc('Employee', reports_to).then(reports_to_doc => {
        const already_exists = frm.doc.assign_by.some(entry => entry.employee === reports_to);
        if (!already_exists) {
          frm.doc.assign_by = frm.doc.assign_by.filter(r => r.employee);
          frm.add_child('assign_by', {
            employee: reports_to,
            employee_name: reports_to_doc.employee_name
          });
          frm.refresh_field('assign_by');
        }
      });
    });
  }
});
frappe.ui.form.on('MainTask Assign By', {
  employee: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.employee) return;
	
	const is_duplicate = frm.doc.assign_by.filter(r => r.employee === row.employee).length > 1;
    if (is_duplicate) {
      frappe.msgprint(__('{0} has been choosen as assign by member', [frappe.model.get_value(cdt, cdn, 'employee_name') || '']));
      frappe.model.set_value(cdt, cdn, 'employee', null);
      frappe.model.set_value(cdt, cdn, 'employee_name', null);
      return;
    }
  }
});