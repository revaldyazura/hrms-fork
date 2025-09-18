// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("MainTask", {
  refresh: function (frm) {
     let workspace = 'Task Management';
            
        frappe.breadcrumbs.all[frappe.get_route_str()] = {
            workspace: workspace,
            doctype: frm.doctype,
            type: 'Form'
        };
        frappe.breadcrumbs.update();
        
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
      frm.add_custom_button('Generate Tasks from Template', () => {
        frappe.call({
          method: 'hrms.hr.doctype.maintask.maintask.get_task_template_list',
          callback: (r) => {
            let options = r.message.map(d => ({ label: d.template_name, value: d.name }));
            frappe.prompt([
              {
                fieldtype: 'Select',
                label: 'Choose Template',
                fieldname: 'template',
                options: options,
                reqd: 1
              }
            ], values => {
              frappe.call({
                method: 'hrms.hr.doctype.maintask.maintask.get_template_details',
                args: { template_name: values.template },
                callback: (res) => {
                  let tasks = res.message;
                  show_task_dialog(frm, tasks);
                }
              });
            }, 'Select Template');
          }
        });
      });
    }
  },
  onload: function (frm) {

  }
});

function show_task_dialog(frm, tasks) {
  let fields = [];

  tasks.forEach((task, i) => {
    fields.push({
      fieldname: `section_${i}`,
      fieldtype: 'Section Break',
      label: `Task ${i + 1}: ${task.task_name_template}`
    });
    fields.push({
      fieldname: `task_name_template_${i}`,
      label: 'Task Title',
      fieldtype: 'Data',
      default: `${task.task_name_template}`,
      reqd: 1
    });
    fields.push({
      fieldname: `target_time_template_${i}`,
      label: 'Target Time',
      fieldtype: 'Int',
      default: task.target_time_template
    });
    fields.push({
      fieldname: `unit_target_time_template_${i}`,
      label: 'Unit Target Time',
      fieldtype: 'Select',
      options: ['Hours', 'Minutes'],
      default: task.unit_target_time_template
    });
    fields.push({
      fieldname: `status_template_${i}`,
      label: 'Status',
      fieldtype: 'Select',
      options: ['Open'],
      default: task.status_template
    });
    fields.push({
      fieldname: `task_pic_${i}`,
      label: 'Task PICs',
      fieldtype: 'Table',
      cannot_add_rows: 0,
      fields: [
        {
          fieldname: 'employee',
          label: 'Employee',
          fieldtype: 'Link',
          options: 'Employee',
          ignore_user_permissions: 1,
          in_list_view: 1,
          reqd: 1,
      get_query: () => {
        // Ambil daftar employee dari child table team di MainTask
        let allowed_employees = (frm.doc.team || []).map(row => row.employee);
        return {
          filters: [
            ['name', 'in', allowed_employees]
          ]
        };
      }
        }
      ]
    });


  });

  let dialog = new frappe.ui.Dialog({
    title: 'Generate Tasks from Template',
    fields: fields,
    size: 'extra-large',
    primary_action_label: 'Generate',
    primary_action(values) {
      frappe.call({
        method: 'hrms.hr.doctype.maintask.maintask.create_tasks_from_template',
        args: {
          maintask: frm.doc.name,
          values: values,
          count: tasks.length
        },
        callback: () => {
          frappe.msgprint('Tasks generated successfully');
          frm.reload_doc();
          dialog.hide();
        }
      });
    }
  });

  dialog.show();
}

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