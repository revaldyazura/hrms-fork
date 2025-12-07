frappe.pages['maintask-summary'].on_page_load = async function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'MainTask Summary',
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
  .card {
    background: #f9f9f9;
    border: 1px solid #ddd;
    border-radius: 14px;
    padding: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,.08);
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
        <h2 id="maintask_title">Report Summary</h2>
        <h3 >🧩 Tracker</h3>
        <div class="card">
            <div id="tracker_table_wrapper"></div>
        </div>
        <h3 style="margin-top:16px">🏷️ Priority</h3>
        <div class="card">
            <div id="priority_table_wrapper"></div>
        </div>
        <h3 style="margin-top:16px">👤 PIC SubTask</h3>
        <div class="card">
            <div id="pic_table_wrapper"></div>
        </div>
    </div>
  `);

    const maintaskField = page.add_field({
        label: "MainTask",
        fieldtype: "Link",
        options: "MainTask",
        fieldname: "maintask_filter",
        onchange: async () => {
            const value = maintaskField.get_value();
            const displayName = await getMainTaskTitle(value);
            updateMainTaskTitle(displayName);
            load_data();
        }
    });

    async function getMainTaskTitle(maintask) {
        try {
            const r = await frappe.db.get_value("MainTask", maintask, "maintask_name");
            return r?.message?.maintask_name || maintask;
        } catch (e) {
            return maintask;
        }
    }

    function updateMainTaskTitle(displayName) {
        const el = document.getElementById('maintask_title');
        if (!el) return;
        el.textContent = displayName ? `${displayName} Report Summary` : "Report Summary";
    }

    function load_data() {
        const maintask = maintaskField.get_value() || null;
        const trackerTableWrapper = document.getElementById("tracker_table_wrapper");
        const priorityTableWrapper = document.getElementById("priority_table_wrapper");
        const picTableWrapper = document.getElementById("pic_table_wrapper");

        if (!trackerTableWrapper || !priorityTableWrapper || !picTableWrapper) return;
        trackerTableWrapper.innerHTML = '<div class="empty">Loading…</div>';
        priorityTableWrapper.innerHTML = '<div class="empty">Loading…</div>';
        picTableWrapper.innerHTML = '<div class="empty">Loading…</div>';

        frappe.call({
            method: 'hrms.task_management.page.maintask_summary.maintask_summary.get_maintask_subtask_tracker',
            args: { maintask },
            callback: (r) => {
                if (!r.message) {
                    renderTracker({ columns: [], rows: [] });
                    renderPriority({ columns: [], rows: [] });
                    renderPic({ columns: [], rows: [] });
                    return;
                }
                renderTracker(r.message);
                renderPriority({
                    columns: r.message.priority_columns || [],
                    rows: r.message.priority_rows || []
                });
                renderPic({
                    columns: r.message.pic_columns || [],
                    rows: r.message.pic_rows || []
                });
            }
        });
    }

    function renderTracker(payload) {
        const wrap = document.getElementById("tracker_table_wrapper");
        if (!wrap) return;
        const safe = frappe.utils.escape_html;

        const columns = payload.type_columns || [];
        const rows = payload.type_rows || [];

        if (!columns.length) {
            if (!maintaskField.get_value()) {
                wrap.innerHTML = `<div class="empty">Please select a MainTask to view the report.</div>`;
                return;
            }
            if (!maintaskField.get_value()) {
                wrap.innerHTML = `<div class="empty">Please select a MainTask to view the report.</div>`;
                return;
            }
            wrap.innerHTML = `<div class="empty">No data</div>`;
            return;
        }

        const headerHtml = `
            <tr>
                ${columns.map(c => `<th>${safe(c.label || '')}</th>`).join('')}
            </tr>
        `;

        const bodyHtml = rows.length
            ? rows.map(r => `
                <tr>
                    ${columns.map(c => {
                const val = r[c.key];
                return `<td>${safe(val == null ? '-' : String(val))}</td>`;
            }).join('')}
                </tr>
            `).join('')
            : `<tr><td class="empty" colspan="${columns.length}">No data</td></tr>`;

        wrap.innerHTML = `
            <table>
                <thead>${headerHtml}</thead>
                <tbody>${bodyHtml}</tbody>
            </table>
        `;
    }

    function renderPriority(payload) {
        const wrap = document.getElementById("priority_table_wrapper");
        if (!wrap) return;
        const safe = frappe.utils.escape_html;

        const columns = payload.columns || [];
        const rows = payload.rows || [];

        if (!columns.length) {
            if (!maintaskField.get_value()) {
                wrap.innerHTML = `<div class="empty">Please select a MainTask to view the report.</div>`;
                return;
            }
            wrap.innerHTML = `<div class="empty">No data</div>`;
            return;
        }

        const headerHtml = `
            <tr>
                ${columns.map(c => `<th>${safe(c.label || '')}</th>`).join('')}
            </tr>
        `;

        const bodyHtml = rows.length
            ? rows.map(r => `
                <tr>
                    ${columns.map(c => {
                const val = r[c.key];
                return `<td>${safe(val == null ? '-' : String(val))}</td>`;
            }).join('')}
                </tr>
            `).join('')
            : `<tr><td class="empty" colspan="${columns.length}">No data</td></tr>`;

        wrap.innerHTML = `
            <table>
                <thead>${headerHtml}</thead>
                <tbody>${bodyHtml}</tbody>
            </table>
        `;
    }

    function renderPic(payload) {
        const wrap = document.getElementById("pic_table_wrapper");
        if (!wrap) return;
        const safe = frappe.utils.escape_html;

        const columns = payload.columns || [];
        const rows = payload.rows || [];

        if (!columns.length) {
            if (!maintaskField.get_value()) {
                wrap.innerHTML = `<div class="empty">Please select a MainTask to view the report.</div>`;
                return;
            }
            wrap.innerHTML = `<div class="empty">No data</div>`;
            return;
        }

        const headerHtml = `
            <tr>
                ${columns.map(c => `<th>${safe(c.label || '')}</th>`).join('')}
            </tr>
        `;

        const bodyHtml = rows.length
            ? rows.map(r => `
                <tr>
                    ${columns.map(c => {
                const val = r[c.key];
                return `<td>${safe(val == null ? '-' : String(val))}</td>`;
            }).join('')}
                </tr>
            `).join('')
            : `<tr><td class="empty" colspan="${columns.length}">No data</td></tr>`;

        wrap.innerHTML = `
            <table>
                <thead>${headerHtml}</thead>
                <tbody>${bodyHtml}</tbody>
            </table>
        `;
    }

    renderTracker({ columns: [], rows: [] });
    renderPriority({ columns: [], rows: [] });
    renderPic({ columns: [], rows: [] });



}