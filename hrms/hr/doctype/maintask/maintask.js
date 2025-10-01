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
            const readonly_fields = ['maintask_name', 'description', "status", "assign_date", "due_date", "assign_by", "priority"];
            if (r.message === "none") {
              frm.set_read_only(true);
              frm.disable_save();
            } else if (r.message === "assign_by_maintask_leader") {
              readonly_fields.forEach(field => {
                frm.set_df_property(field, "read_only", 1);
              });
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
      frm.add_custom_button('Show Tasks of This MainTask', function () {
        if (!frm.doc.name) return;

        const make_dialog = () => {
          const dlg = new frappe.ui.Dialog({
            title: __('Tasks of {0}', [frm.doc.maintask_name]),
            size: 'large', // baseline; we'll override with custom CSS to reach ~85% viewport
            fields: [
              { fieldname: 'results_section', fieldtype: 'Section Break' },
              { fieldname: 'tasks_html', fieldtype: 'HTML' },
              { fieldname: 'pagination_html', fieldtype: 'HTML' },
              { fieldname: 'bottom_actions', fieldtype: 'HTML' }
            ],
            primary_action_label: __('Close'),
            primary_action() { dlg.hide(); }
          });

          // Tag wrapper & inject improved styling for full-width table
          dlg.$wrapper.addClass('wide-tasks-dialog');
          if (!document.getElementById('req-dialog-style-fixed')) {
            const style = document.createElement('style');
            style.id = 'req-dialog-style-fixed';
            style.textContent = `
                        .wide-tasks-dialog .modal-dialog { max-width:85vw; width:85vw; }
                        .wide-tasks-dialog .modal-content { width:100%; }
                        .wide-tasks-dialog .modal-body { max-height:72vh; overflow:auto; padding: 8px 14px 12px; }
                        .wide-tasks-dialog .form-layout, 
                        .wide-tasks-dialog .form-page, 
                        .wide-tasks-dialog .form-section, 
                        .wide-tasks-dialog .section-body { width:100% !important; max-width:100% !important; margin:0; padding:0; }
                        .wide-tasks-dialog .form-column { width:100% !important; max-width:100% !important; flex:0 0 100%; padding:0; }
                        .wide-tasks-dialog .frappe-control { margin-bottom:6px; }
                        .wide-tasks-dialog .frappe-control[data-fieldname="tasks_html"],
                        .wide-tasks-dialog .frappe-control[data-fieldname="pagination_html"],
                        .wide-tasks-dialog .frappe-control[data-fieldname="bottom_actions"] { width:100% !important; margin:0; padding:0; }
                        .wide-tasks-dialog .req-table-wrapper { width:100%; }
                        .wide-tasks-dialog .req-table { width:100%; table-layout:auto; }
                        .wide-tasks-dialog .req-table th { white-space:nowrap; text-align:center; vertical-align:middle; }
                        .wide-tasks-dialog .req-table td { white-space:nowrap; }
                        .wide-tasks-dialog .req-table td.desc-cell { white-space:normal; line-height:1.3; }
                        .wide-tasks-dialog .req-table td.wrap-cell { white-space:normal; line-height:1.3; word-break:break-word; }
                        .wide-tasks-dialog .req-table td.text-center { text-align:center; }
                        .wide-tasks-dialog .tech-val-icon { display:inline-block; width:18px; font-weight:600; color: var(--green, #2e7d32); }
                        .wide-tasks-dialog .tech-val-icon.off { color:#bbb; }
                        @media (max-width: 1200px) {
                            .wide-tasks-dialog .req-table th, .wide-tasks-dialog .req-table td { white-space:normal; }
                        }
                    `;
            document.head.appendChild(style);
          }
          // Force any existing form columns (after render) to 100%
          setTimeout(() => {
            dlg.$wrapper.find('.form-column').css({ width: '100%', maxWidth: '100%', flex: '0 0 100%' });
          }, 0);

          const state = { page: 1, page_size: 20 };

          const columns = [
            { key: 'name', label: 'ID' },
            { key: 'task_name', label: 'Tasks Title' },
            { key: 'description', label: 'Description' },
            { key: 'target_time', label: 'Target Time' },
            { key: 'unit_target_time', label: 'Unit Target Time' },
            { key: 'task_pic_names', label: 'Task PICs' },
            { key: 'created_by', label: 'Created By' },
            { key: 'status', label: 'Status' },
            { key: 'actions', label: 'Actions' }
          ];

          function esc(v) {
            if (v == null) return '';
            return String(v)
              .replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;');
          }

          function fetch_and_render() {
            frappe.call({
              method: 'hrms.hr.doctype.maintask.maintask.get_tasks',
              args: {
                maintask_id: frm.doc.name,
                page: state.page,
                page_size: state.page_size
              },
              callback: r => {
                const payload = r.message || { rows: [], total: 0 };
                render_table(payload.rows, payload.total);
                render_pagination(payload.total);
              }
            });
          }

          function truncate(str, n = 60) {
            if (!str) return '';
            return str.length > n ? str.slice(0, n) + '…' : str;
          }

          function row_class(row) {
            if (row.status === 'Done') return 'success';
            if (row.status === 'Cancel') return 'danger';
            return '';
          }

          function render_table(rows, total) {
            let html = '';
            if (!rows.length) {
              html = `<div class="text-muted" style="padding:12px">${__('No tasks found.')}</div>`;
            } else {
              html += '<div class="req-table-wrapper" style="max-height:420px; overflow:auto;">';
              html += '<table class="table table-bordered table-compact req-table" style="margin:0">';
              html += '<thead><tr>' + columns.map(c => `<th>${esc(c.label)}</th>`).join('') + '</tr></thead>';
              html += '<tbody>';
              rows.forEach(row => {
                html += `<tr class="req-row ${row_class(row)}" data-name="${esc(row.name)}"` +
                  ` data-task_name="${esc(row.task_name || '')}" data-description="${esc(row.description || '')}"` +
                  ` data-target_time="${esc(row.target_time || '')}" data-unit_target_time="${esc(row.unit_target_time || '')}"` +
                  ` data-status="${esc(row.status || '')}" data-created_by="${esc(row.created_by || '')}">`
                // ` data-change_description="${esc(row.change_description||'')}">`; 
                columns.forEach(c => {
                  if (c.key === 'name') {
                    // Use a clickable link that triggers frappe.set_route for reliable navigation in desk SPA
                    // html += `<td><a href="/app/tasks/${esc(row.name)}" class="req-link" data-doctype="Tasks" data-name="${esc(row.name)}">${esc(row.name)}</a></td>`;
                    html += `<td class="wrap-cell" title="${esc(row.name)}">${esc(row.name)}</td>`;
                  } else if (c.key === 'description') {
                    const full = row.description || '';
                    html += `<td class="desc-cell" title="${esc(full)}">${esc(full)}</td>`;
                  } else if (c.key === 'task_pic_names') {
                    const full_pics = row.task_pic_names || '';
                    html += `<td class="desc-cell" title="${esc(full_pics)}">${esc(full_pics)}</td>`;
                  }else if (c.key === 'actions') {
                    html += `<td class="action-cell" style="min-width:70px;">
                                        <button class="btn btn-xs btn-primary open-req" data-name="${esc(row.name)}">${__('View')}</button>
                                    </td>`;
                  } else {
                    html += `<td>${esc(row[c.key] || '')}</td>`;
                  }
                });
                html += '</tr>';
              });
              html += '</tbody></table></div>';
              html += `<div class="mt-2 small text-muted">${__('Total')}: ${total}</div>`;
            }
            dlg.fields_dict.tasks_html.$wrapper.html(html);
            bind_row_events();
          }

          function render_pagination(total) {
            const total_pages = Math.max(1, Math.ceil(total / state.page_size));
            if (state.page > total_pages) state.page = total_pages;
            let html = '<div class="d-flex align-items-center gap" style="margin-top:8px;">';
            html += `<button class="btn btn-xs btn-default pag-btn" data-dir="prev" ${state.page <= 1 ? 'disabled' : ''}>${__('Prev')}</button>`;
            html += `<span style="padding:0 8px">${__('Page')} ${state.page} / ${total_pages}</span>`;
            html += `<button class="btn btn-xs btn-default pag-btn" data-dir="next" ${state.page >= total_pages ? 'disabled' : ''}>${__('Next')}</button>`;
            html += '</div>';
            dlg.fields_dict.pagination_html.$wrapper.html(html);
            dlg.fields_dict.pagination_html.$wrapper.find('.pag-btn').on('click', function () {
              const dir = $(this).data('dir');
              if (dir === 'prev' && state.page > 1) { state.page -= 1; }
              if (dir === 'next') { state.page += 1; }
              fetch_and_render();
            });
          }

          function bind_row_events() {
            // Open button
            dlg.$wrapper.find('.open-req').off('click').on('click', function () {
              const docname = $(this).data('name');
              frappe.set_route('Form', 'Tasks', docname);
            });
          }

          dlg.show();
          fetch_and_render();
        };

        make_dialog();
      })
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