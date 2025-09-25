// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tasks", {
  refresh(frm) {
    let workspace = 'Task Management';
            
        frappe.breadcrumbs.all[frappe.get_route_str()] = {
            workspace: workspace,
            doctype: frm.doctype,
            type: 'Form'
        };
        frappe.breadcrumbs.update();
        
    if (!frm.is_new()) {
      frappe.call({
        method: "hrms.hr.doctype.tasks.tasks.user_edit_tasks",
        args: {
          task_name: frm.doc.name
        },
        callback: function (r) {
          const readonly_fields = ['target_time', 'maintask', "pic_task", "unit_target_time"];
          if (r.message === "pic_task" || r.message === "task_pics") {
            readonly_fields.forEach(field => {
              frm.set_df_property(field, "read_only", 1);
            });
          } else if (r.message === "none") {
            frm.set_read_only(true);
            frm.disable_save();
          }
        }
      });
      frm.add_custom_button('Generate SubTask from Template', () => {
        frappe.call({
          method: 'hrms.hr.doctype.tasks.tasks.get_subtask_template_list',
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
                method: 'hrms.hr.doctype.tasks.tasks.get_template_details',
                args: { template_name: values.template },
                callback: (res) => {
                  let subtask = res.message;
                  show_subtask_dialog(frm, subtask);
                }
              });
            }, 'Select Template');
          }
        });
      });
    }
  },
  onload: function (frm) {

    frm.set_query("maintask", function () {
      return {
        query: "hrms.hr.doctype.tasks.tasks.get_open_maintask_as_the_owner"
      };
    });
    frm.set_query("pic_task", function () {
      if (!frm.doc.maintask) {
        frappe.msgprint("Choose the main task field first.");
        return {};
      }
      return {
        query: "hrms.hr.doctype.tasks.tasks.get_employees_by_role_and_team",
        filters: {
          maintask: frm.doc.maintask
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
      }, 300); // Delay sedikit agar field render dulu
    });
    frm.fields_dict["task_pic"].grid.get_field("employee").get_query = function (doc, cdt, cdn) {
      if (!frm.doc.maintask) {
        frappe.msgprint("Choose the main task field first.");
        return {};
      }
      return {
        query: "hrms.hr.doctype.tasks.tasks.get_employees_by_role_and_team",
        filters: {
          maintask: frm.doc.maintask
        }
      };
    };

  },
});

function show_subtask_dialog(frm, subtask) {
  // Ambil MainTask dari field parent
  const main_task_name = frm.doc.maintask;

  if (!main_task_name) {
    frappe.msgprint("MainTask Not Found.");
    return;
  }

  // Ambil daftar employee dari MainTask.team
  frappe.call({
    method: 'frappe.client.get',
    args: {
      doctype: 'MainTask',
      name: main_task_name
    },
    callback: function (r) {
      if (!r.message) {
        frappe.msgprint("Failed to get MainTask Data.");
        return;
      }

      const team_employees = (r.message.team || []).map(row => row.employee);

      // Lanjut ke dialog setelah data team tersedia
      let fields = [];

      subtask.forEach((subtask, i) => {
        fields.push(
          {
            fieldname: `section_${i}`, fieldtype: 'Section Break', label: `SubTask ${i + 1}: ${subtask.subtask_name_template}`
          },
          {
            fieldname: `subtask_name_template_${i}`, label: 'SubTask Name', fieldtype: 'Data', default: `${subtask.subtask_name_template}`, reqd: 1
          },
          {
            fieldname: `value_template_${i}`, label: 'Value SubTask', fieldtype: 'Select', options: ['1', '2', '3'], default: subtask.value_template
          },
          {
            fieldname: `description_template_${i}`, label: 'Description', fieldtype: 'Text Editor', default: subtask.description_template
          },
          {
            fieldname: `target_time_template_${i}`, label: 'Target Time', fieldtype: 'Int', default: subtask.target_time_template
          },
          {
            fieldname: `unit_target_time_template_${i}`, label: 'Unit Target Time', fieldtype: 'Select', options: ['Hours', 'Minutes'], default: subtask.unit_target_time_template
          },
          {
            fieldname: `status_template_${i}`, label: 'Status', fieldtype: 'Select', options: ['Open'], default: subtask.status_template
          },
          {
            fieldname: `priority_template_${i}`, label: 'Priority', fieldtype: 'Select', 
            options: ['Low', 'Medium', 'High'], default: subtask.priority_template
          },
          {
            fieldname: `pic_subtask_template_${i}`, label: 'PIC SubTask', fieldtype: 'Link', options: 'Employee', reqd: 1
          },
          {
            fieldname: `subtask_type_${i}`,
            label: 'SubTask Type',
            fieldtype: 'Table',
            cannot_add_rows: 0,
            fields: [
              {
                fieldname: 'type', label: 'Type', fieldtype: 'Link', options: 'SubTask Types', in_list_view: 1, reqd: 1
              }
            ]
          }
        );
      });

      let dialog = new frappe.ui.Dialog({
        title: 'Generate SubTask from Template',
        fields: fields,
        size: 'extra-large',
        primary_action_label: 'Generate',
        primary_action(values) {
          frappe.call({
            method: 'hrms.hr.doctype.tasks.tasks.create_subtask_from_template',
            args: {
              tasks: frm.doc.name,
              values: values,
              count: subtask.length
            },
            callback: () => {
              frappe.msgprint('SubTask generated successfully');
              frm.reload_doc();
              dialog.hide();
            }
          });
        }
      });

      // Atur get_query untuk setiap PIC field
      subtask.forEach((subtask, i) => {
        const fieldname = `pic_subtask_template_${i}`;
        const field = dialog.get_field(fieldname);

        if (field) {
          field.get_query = () => {
            return {
              filters: [['Employee', 'name', 'in', team_employees]]
            };
          };
        }
      });

      dialog.show();
      subtask.forEach((sub, i) => {
        const table_field = dialog.fields_dict[`subtask_type_${i}`];
        if (table_field) {
          // Isi dengan 1 row default dari type_template
          table_field.df.data = [{
            type: sub.type_template || ''
          }];
          table_field.refresh();
        }
      });
    }
  });
}



frappe.ui.form.on('Task PIC', {
  employee: function (frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.employee) return;

    const is_duplicate = frm.doc.task_pic.filter(r => r.employee === row.employee).length > 1;
    if (is_duplicate) {
      frappe.msgprint(__('{0} has been choosen as PIC Task member', [frappe.model.get_value(cdt, cdn, 'employee_name') || '']));
      frappe.model.set_value(cdt, cdn, 'employee', null);
      frappe.model.set_value(cdt, cdn, 'employee_name', null);
      return;
    }
  }
});
