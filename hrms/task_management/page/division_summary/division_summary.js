frappe.pages['division-summary'].on_page_load = async function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Division Summary',
        single_column: true
    });

    const css = `
  .dst {
    background: #ffffff;
    padding: 16px 18px 28px;
    color: #222;
  }
  .dst h3, .dst h4 {
    color: #333;
    margin: 0 0 10px;
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(5, minmax(160px, 1fr));
    gap: 12px;
  }
  .card {
    background: #f9f9f9;
    border: 1px solid #ddd;
    border-radius: 14px;
    padding: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,.08);
  }
  .metric .label {
    font-size: 12px;
    opacity: 0.7;
    color: #555;
  }
  .metric .value {
    font-size: 28px;
    font-weight: 600;
    margin-top: 6px;
    color: #222;
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-top: 8px;
  }
  .chart {
    height: 320px;
    display: flex;
    flex-direction: column;
  }
  .chart .title {
    font-size: 12px;
    opacity: 0.7;
    margin-bottom: 6px;
    color: #555;
  }
  /* simple pill styling */
  .pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    line-height: 1.6;
    white-space: nowrap;
  }
  /* table styles */
  .dst table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .dst thead th { text-transform: uppercase; font-size: 11px; letter-spacing: .3px; text-align: center; }
  .dst th, .dst td { border-bottom: 1px solid #eee; padding: 8px 10px; }
  .dst th { color: #333; font-weight: 700; background: #fafafa; }
  .dst td { text-align: center; }
  .dst .empty { color: #888; padding: 8px 10px; }
  .dst .pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 600; line-height: 1.6; }
    .dst .table-pager { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px; }
    .dst .page-info { font-size: 12px; color: #666; }
    .dst .page-size-control { display: flex; align-items: center; gap: 6px; color: #666; font-size: 13px; }
    .dst .page-size-control select { padding: 4px 6px; border-radius: 6px; border: 1px solid #ddd; background: #fff; }
`;
    $('<style>').text(css).appendTo($(wrapper));

    $(page.body).append(`
    <div class="dst">
      <h3 id="team_title">🧩 TEAM OVERVIEW</h3>
      <div class="card">
        <div id="div_table_wrapper"></div>
      </div>
    </div>
  `);

    const TEAM_MAP = new Map();

    const teamField = page.add_field({
        label: 'Team',
        fieldtype: 'Select',
        fieldname: 'team_filter',
        options: [],
        default: '-- All Teams --',
        onchange: () => {
            updateTeamHeaderFromField();
            const selectedLabel = teamField.get_value();
            // update picField team filter dynamically
            try {
                picField.df.filters = picField.df.filters || {};
                picField.df.filters.team = TEAM_MAP.get(selectedLabel) || null;
                if (typeof picField.refresh === 'function') picField.refresh();
                // clear pic selection when team changes
                if (typeof picField.set_value === 'function') picField.set_value(null);
            } catch (e) { console.warn('failed to update picField filters', e); }

            const teamDocname = TEAM_MAP.get(selectedLabel) || null;
            load_data(teamDocname, picField.get_value() ,getStatusValue());
        }
    });

    const picField = page.add_field({
        label: 'PIC SubTask',
        fieldtype: 'Link',
        options: 'Employee',
        fieldname: 'pic_filter',
        // apply only the status filter here; team filter is set dynamically
        filters: {
            status: 'Active'
        },
        onchange: () => {
            const selectedLabel = teamField.get_value();
            const teamDocname = TEAM_MAP.get(selectedLabel) || null;
            const picValue = picField.get_value() || null;
            load_data(teamDocname, picValue, getStatusValue());
        }
    });

    const statusField = page.add_field({
        label: "Status",
        fieldtype: "Select",
        fieldname: "status_filter",
        options: ["-- All Statuses --", "Open", "In Progress", "Done", "Pause", "Cancel", "Close"].join("\n"),
        // default to "In Progress" per requirement
        default: "In Progress",
        onchange: () => {
            const selectedLabel = teamField.get_value();
            const teamDocname = TEAM_MAP.get(selectedLabel) || null;
            load_data(teamDocname, picField.get_value() , getStatusValue());
        },
    });

    // Date range filters (default empty means no date filtering)
    const startDateField = page.add_field({
        label: "Start Date",
        fieldtype: "Datetime",
        fieldname: "start_date_filter",
        onchange: () => validateDateAndReload(),
    });
    const endDateField = page.add_field({
        label: "End Date",
        fieldtype: "Datetime",
        fieldname: "end_date_filter",
        onchange: () => validateDateAndReload(),
    });

    page.add_inner_button("Clear Dates", () => {
		// Reset field values
		startDateField?.set_value?.(null);
		endDateField?.set_value?.(null);
		// If employee is selected, refresh without date filters
		const team = teamField.get_value();
		if (team) {
			const teamDocname = TEAM_MAP.get(team) || null;
            load_data(teamDocname, picField.get_value() , getStatusValue());
		}
	});

    await init_team_filter(teamField);
    updateTeamHeaderFromField();

    function getStatusValue() {
        const v = statusField?.get_value?.() || null;
        if (!v || v === '-- All Statuses --') return null;
        return v;
    }

    async function init_team_filter(ctrl) {
        const { message } = await frappe.call({
            method: 'hrms.task_management.page.division_summary.division_summary.get_team_options'
        });
        const pairs = message || [];

        TEAM_MAP.clear();
        TEAM_MAP.set('-- All Teams --', null);
        const optionLabels = ['-- All Teams --'];
        pairs.forEach(({ label, value }) => {
            if (!label || !value) return;
            TEAM_MAP.set(label, value);
            optionLabels.push(label);
        });

        ctrl.df.options = optionLabels.join('\n');
        ctrl.refresh();

        const userTeamValue = await get_current_user_team();
        let defaultLabel = '-- All Teams --';
        for (const [label, val] of TEAM_MAP.entries()) {
            if (val === userTeamValue) {
                defaultLabel = label;
                break;
            }
        }
        ctrl.set_value(defaultLabel);
        updateTeamHeaderFromField();

        // ensure picField's team filter follows the selected/default team
        try {
            picField.df.filters = picField.df.filters || {};
            picField.df.filters.team = TEAM_MAP.get(defaultLabel) || null;
            if (typeof picField.refresh === 'function') picField.refresh();
        } catch (e) { console.warn('failed to initialize picField filters', e); }

        // ensure status default is "In Progress"
        if (statusField && statusField.get_value() !== 'In Progress') {
            statusField.set_value('In Progress');
        }

        load_data(defaultLabel !== '-- All Teams --' ? userTeamValue : null, picField.get_value() , getStatusValue());
    }

    async function get_current_user_team() {
        try {
            const user = frappe.session.user;
            const r = await frappe.db.get_value('Employee', { user_id: user }, 'team');
            return r?.message?.team || null;
        } catch (e) {
            console.warn('get_current_user_team failed:', e);
            return null;
        }
    }

    function teamLabel(val) {
        return (val && val !== '-- All Teams --') ? val : 'All Teams';
    }

    function updateTeamHeaderFromField() {
        const el = document.getElementById('team_title');
        if (!el || !teamField) return;
        const label = teamLabel(teamField.get_value());
        el.textContent = `🧩 ${label} OVERVIEW`;
    }

    function getStartDateValue() {
        const v = startDateField?.get_value?.();
        return v || null;
    }

    function getEndDateValue() {
        const v = endDateField?.get_value?.();
        return v || null;
    }

    function validateDateAndReload() {
        const start = getStartDateValue();
        const end = getEndDateValue();
        if (start && end && end < start) {
            frappe.msgprint(__('End Date cannot be before Start Date'));
            // Reset end date to start to maintain valid range
            endDateField.set_value(start);
        }
        const selectedLabel = teamField.get_value();
        const teamDocname = TEAM_MAP.get(selectedLabel) || null;
        load_data(teamDocname, picField.get_value() , getStatusValue());
    }

    function load_data(teamDocname, picValue, status_value) {
        // teamDocname can be null for all teams
        // status_value can be null for all statuses
        frappe.call({
            method: 'hrms.task_management.page.division_summary.division_summary.get_team_overview',
            args: {
                team: teamDocname || null,
                pic_subtask: picValue || null,
                status: status_value || null,
                start_date: getStartDateValue(),
                end_date: getEndDateValue(),
            },
            callback: (r) => {
                if (!r.message) {
                    renderSubtaskTable([], []);
                    return;
                }
                const d = r.message;
                const rows = d.subtask_rows || [];
                const employees = d.employees || [];
                renderSubtaskTable(rows, employees);
            }
        });
    }
    

    // pagination state
    let pageSize = 15;
    let currentPage = 1;
    function renderSubtaskTable(rows, employees) {
        const wrap = document.getElementById("div_table_wrapper");
        if (!wrap) return;

        const safe = frappe.utils.escape_html;
        const fmt = (v) => {
            if (!v) return "-";
            try {
                const d = new Date(v);
                if (isNaN(d.getTime())) return v;
                return d.toLocaleString();
            } catch (e) { return v; }
        };

        // Build a set of employee identifiers (prefer employee_name)
        const empList = (employees || []).map(e => ({
            name: e.name || e.employee || e.employee_id || null,
            employee_name: e.employee_name || e.employee || e.name || '-',
        }));

        // Group subtasks by employee_name (fallback by employee id/name)
        const group = new Map();
        (rows || []).forEach(r => {
            const key = (r.employee_name || r.employee || '').trim() || 'UNKNOWN';
            if (!group.has(key)) group.set(key, []);
            group.get(key).push(r);
        });

        // Merge: ensure every employee gets at least one row
        let merged = [];
        empList.forEach(emp => {
            const key = (emp.employee_name || '').trim() || 'UNKNOWN';
            const subRows = group.get(key);
            if (subRows && subRows.length) {
                merged = merged.concat(subRows);
            } else {
                merged.push({
                    employee_name: emp.employee_name || '-',
                    maintask_name: '-',
                    tasks_name: '-',
                    subtask_name: '-',
                    priority: '-',
                    status: '-',
                    start_date: '-',
                });
            }
        });

        // Sort by employee_name A-Z
        merged.sort((a, b) => {
            const A = (a.employee_name || '').toLowerCase();
            const B = (b.employee_name || '').toLowerCase();
            return A.localeCompare(B);
        });
    function computeTotalPages() {
        return Math.max(1, Math.ceil(merged.length / pageSize));
    }

        const prioColor = (p) => {
            const x = (p || '').toLowerCase();
            if (x === 'high') return 'background:#fdecea;color:#b71c1c;';
            if (x === 'medium') return 'background:#fff8e1;color:#8d6e00;';
            if (x === 'low') return 'background:#e3f2fd;color:#0d47a1;';
            return 'background:#eee;color:#555;';
        };
        const statusColor = (s) => {
            switch (s) {
                case 'Done': return 'background:#e8f5e9;color:#1b5e20;';
                case 'Cancel': return 'background:#ffebee;color:#b71c1c;';
                case 'Pause': return 'background:#fff3e0;color:#e65100;';
                case 'Open': return 'background:#f5f5f5;color:#424242;';
                case 'Close': return 'background:#f3e5f5;color:#4a148c;';
                case 'In Progress': return 'background:#e3f2fd;color:#0d47a1;';
                default: return 'background:#eee;color:#555;';
            }
        };

        const render = () => {
            const totalPages = computeTotalPages();
            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;
            const pageRows = merged.slice(start, end);

            let html = `
                <table>
                    <thead>
                        <tr>
                            <th>Employee</th>
                            <th>MainTask</th>
                            <th>Task</th>
                            <th>SubTask</th>
                            <th>Priority</th>
                            <th>Status</th>
                            <th>Start Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${pageRows.map(r => `
                            <tr>
                                <td>${safe(r.employee_name || "-")}</td>
                                <td>${safe(r.maintask_name || "-")}</td>
                                <td>${safe(r.tasks_name || "-")}</td>
                                <td>${safe(r.subtask_name || "-")}</td>
                                <td>${(r.priority && r.priority !== '-') ? `<span class="pill" style="${prioColor(r.priority)}">${safe(r.priority)}</span>` : '-'}</td>
                                <td>${(r.status && r.status !== '-') ? `<span class="pill" style="${statusColor(r.status)}">${safe(r.status)}</span>` : '-'}</td>
                                <td>${safe(fmt(r.start_date || "-"))}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
                <div class="table-pager">
                    <div class="page-size-control">
                        <label>Show
                          <select id="page_size_select">
                            <option value="5">5</option>
                            <option value="10">10</option>
                            <option value="15">15</option>
                            <option value="25">25</option>
                            <option value="50">50</option>
                          </select>
                        per page</label>
                    </div>
                    <div>
                      <button class="btn btn-default btn-sm" data-act="first" ${currentPage === 1 ? 'disabled' : ''}>&laquo;</button>
                      <button class="btn btn-default btn-sm" data-act="prev" ${currentPage === 1 ? 'disabled' : ''}>&lsaquo;</button>
                      <span class="page-info">Page ${currentPage} / ${totalPages}</span>
                      <button class="btn btn-default btn-sm" data-act="next" ${currentPage === totalPages ? 'disabled' : ''}>&rsaquo;</button>
                      <button class="btn btn-default btn-sm" data-act="last" ${currentPage === totalPages ? 'disabled' : ''}>&raquo;</button>
                    </div>
                </div>
            `;
            wrap.innerHTML = html;
            // wire page-size select
            const sizeSel = wrap.querySelector('#page_size_select');
            if (sizeSel) {
                sizeSel.value = String(pageSize);
                sizeSel.onchange = () => {
                    const v = parseInt(sizeSel.value, 10) || 15;
                    pageSize = v;
                    currentPage = 1;
                    render();
                };
            }

            wrap.querySelectorAll('button[data-act]').forEach(btn => {
                btn.onclick = () => {
                    const act = btn.getAttribute('data-act');
                    if (act === 'first') currentPage = 1;
                    if (act === 'prev' && currentPage > 1) currentPage -= 1;
                    if (act === 'next' && currentPage < computeTotalPages()) currentPage += 1;
                    if (act === 'last') currentPage = computeTotalPages();
                    render();
                };
            });
        };

        if (!empList.length) {
            wrap.innerHTML = `<div class="empty">No data</div>`;
            return;
        }

        render();
    }
}