frappe.pages['task-management-division'].on_page_load = async function (wrapper) {
  var page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Division SubTask Overview',
    single_column: true
  });

  const teamField = page.add_field({
    label: 'Team',
    fieldtype: 'Select',
    fieldname: 'team_filter',
    options: [],
    default: '-- All Teams --',
    onchange: () => {
      updateTeamHeaderFromField();
      const selectedLabel = teamField.get_value();         // ini label (team_name)
      const teamDocname = TEAM_MAP.get(selectedLabel) || null; // ini 'name'
      load_data(teamDocname);
    }
  });

  const TEAM_MAP = new Map(); // label -> value (docname)

  // 2) Muat daftar Team lalu set default = team user login
  await init_team_filter(teamField);
  updateTeamHeaderFromField();

  // ===== helpers filter =====
  async function init_team_filter(ctrl) {
    const { message } = await frappe.call({
      method: 'hrms.task_management.page.task_management_division.task_management_division.get_team_options'
    });
    const pairs = message || []; // [{label, value}]

    // isi map & opsi (label yang ditampilkan user)
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

    // default = team user (Employee.team = <name/docname>)
    const userTeamValue = await get_current_user_team(); // ini 'name'
    let defaultLabel = '-- All Teams --';
    for (const [label, val] of TEAM_MAP.entries()) {
      if (val === userTeamValue) {
        defaultLabel = label;
        break;
      }
    }
    ctrl.set_value(defaultLabel);
    updateTeamHeaderFromField();

    // load pertama kirim 'name' (atau null kalau All)
    load_data(defaultLabel !== '-- All Teams --' ? userTeamValue : null);
  }

  async function get_current_user_team() {
    try {
      const user = frappe.session.user;
      const r = await frappe.db.get_value('Employee', { user_id: user }, 'team');
      return r?.message?.team || null; // <- ini adalah docname Team (value)
    } catch (e) {
      console.warn('get_current_user_team failed:', e);
      return null;
    }
  }

  // 3) Chart.js
  if (!window.Chart) {
    await new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
      s.onload = res; s.onerror = rej; document.head.appendChild(s);
    });
  }


  const css = `
  .tmto {
    background: #ffffff;
    padding: 16px 18px 28px;
    color: #222;
  }
  .tmto h3, .tmto h4 {
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
`;
  $('<style>').text(css).appendTo($(wrapper));


  $(page.body).append(`
    <div class="tmto">
      <h3 id="team_title">🧩 ${teamField.get_value()} OVERVIEW</h3>
      <div class="metrics">
        ${m('Total Team Members', 'total_members')}
        ${m('Total Ongoing SubTask', 'ongoing_tasks')}
        ${m('Total Completed SubTask', 'completed_tasks')}
        ${m('Avg Completion Rate', 'avg_completion_rate')}
        ${m('Avg Value Load', 'avg_value')}
      </div>
      <h4 style="margin-top:16px" >📊 Workload Visualization</h4>
      <div class="grid">
        ${c('Ongoing SubTask per Member (Sorted)', 'chart_ongoing')}
        ${c('Avg Value Load per Member (Sorted)', 'chart_value')}
        ${c('Completion Rate per Member (Sorted)', 'chart_completion')}
        ${c('High Priority SubTask (Sorted)', 'chart_highprio')}
      </div>
    </div>
  `);

  function teamLabel(val) {
    return (val && val !== '-- All Teams --') ? val : 'All Teams';
  }

  function updateTeamHeaderFromField() {
    const el = document.getElementById('team_title');
    if (!el || !teamField) return;
    const label = teamLabel(teamField.get_value());
    // Gunakan textContent agar aman dari HTML injection
    el.textContent = `🧩 ${label} OVERVIEW`;
    // (opsional) update judul page-head juga
    // page.set_title(`Division SubTask Overview — ${label}`);
  }

  function m(label, id) {
    return `<div class="card metric"><div class="label">${label}</div><div id="${id}" class="value">–</div></div>`
  }
  function c(title, id) {
    return `<div class="card chart"><div class="title">${title}</div><canvas id="${id}" height="120"></canvas></div>`
  }

  // helper
  function setText(id, val) { document.getElementById(id).innerText = val ?? '–'; }

  function drawBar(canvasId, src, opts = {}) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    if (!src || !src.labels) return;

    const truncate = (s, n = 12) => (s && s.length > n ? s.slice(0, n) + '…' : s);

    new Chart(ctx, {
      type: 'bar',
      data: { labels: src.labels, datasets: [{ data: src.values, backgroundColor: 'rgba(66,165,245,0.6)' }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#ffffff', titleColor: '#000', bodyColor: '#000',
            borderColor: '#ccc', borderWidth: 1,
            titleFont: { size: 14, weight: 'bold', family: "'Segoe UI', sans-serif" },
            bodyFont: { size: 13, family: "'Segoe UI', sans-serif" },
            callbacks: {
              title: (items) => src.labels[items[0].dataIndex],
              label: (ctx) => `${ctx.parsed.y}`
            }
          }
        },
        scales: {
          x: {
            offset: true,
            ticks: {
              autoSkip: false, maxRotation: 60, minRotation: 60, color: '#333',
              callback: (val, idx) => truncate(src.labels[idx])
            },
            grid: { color: '#e0e0e0' }
          },
          y: { beginAtZero: true, ticks: { color: '#333' }, grid: { color: '#e0e0e0' } }
        }
      }
    });
  }


  function load_data(team_docname) {
    console.log('load_data for team:', team_docname);

    frappe.call({
      method: 'hrms.task_management.page.task_management_division.task_management_division.get_team_overview',
      args: { team: team_docname || null }, // <— kirim ke backend
      callback: (r) => {
        if (!r.message) return;
        const d = r.message;

        setText('total_members', d.total_members);
        setText('ongoing_tasks', d.ongoing_tasks);
        setText('completed_tasks', d.completed_tasks);
        setText('avg_completion_rate', `${d.avg_completion_rate}%`);
        setText('avg_value', d.avg_value);

        // re-render charts (bersihkan canvas kalau perlu)
        ['chart_ongoing', 'chart_value', 'chart_completion', 'chart_highprio'].forEach(id => {
          const old = Chart.getChart(id);
          if (old) old.destroy();
        });

        drawBar('chart_ongoing', d.ongoing_per_member);
        drawBar('chart_value', d.value_per_member);
        drawBar('chart_completion', d.completion_rate_per_member, { max: 100, suffix: '%' });
        drawBar('chart_highprio', d.high_priority_per_member);
      }
    });
  }
}