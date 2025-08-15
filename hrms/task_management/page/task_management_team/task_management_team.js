frappe.pages['task-management-team'].on_page_load = async function (wrapper) {
  var page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Team SubTask Overview',
    single_column: true
  });
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

  
  $(wrapper).find('.layout-main-section').html(`
    <div class="tmto">
      <h3>🧩 Team Overview</h3>
      <div class="metrics">
        ${m('Total Team Members', 'total_members')}
        ${m('Total Ongoing SubTask', 'ongoing_tasks')}
        ${m('Total Completed SubTask', 'completed_tasks')}
        ${m('Avg Completion Rate', 'avg_completion_rate')}
        ${m('Avg Value Load', 'avg_value')}
      </div>
      <h4 style="margin-top:16px">📊 Team Workload Visualization</h4>
      <div class="grid">
        ${c('Ongoing SubTask per Member (Sorted)', 'chart_ongoing')}
        ${c('Avg Value Load per Member (Sorted)', 'chart_value')}
        ${c('Completion Rate per Member (Sorted)', 'chart_completion')}
        ${c('High Priority SubTask (Sorted)', 'chart_highprio')}
      </div>
    </div>
  `);

  function m(label, id) {
    return `<div class="card metric"><div class="label">${label}</div><div id="${id}" class="value">–</div></div>`
  }
  function c(title, id) {
    return `<div class="card chart"><div class="title">${title}</div><canvas id="${id}" height="120"></canvas></div>`
  }

  load_data();
  function setText(id, val) { document.getElementById(id).innerText = val ?? '–'; }

  function drawBar(canvasId, src, opts = {}) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    if (src.labels.length !== src.values.length) {
      console.warn('Label/value length mismatch', src);
    }

    const truncate = (s, n = 12) => (s && s.length > n ? s.slice(0, n) + '…' : s);

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: src.labels,
        datasets: [{ data: src.values }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: '#0c0c0c9b',
            titleColor: '#ffffffff',
            bodyColor: '#ffffffff',
            borderColor: '#ffffffff',
            titleFont: {
              size: 14,
              weight: 'bold',
              family: "'Segoe UI', sans-serif"
            },
            bodyFont: {
              size: 13,
              family: "'Segoe UI', sans-serif"
            },
            borderWidth: 1,
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
              autoSkip: false,
              maxRotation: 60,
              minRotation: 60,
              callback: (val, idx) => truncate(src.labels[idx])
            }
          },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(0,0,0,0.08)' }
          }
        }
      }
    });
  }


  function load_data() {
    frappe.call({
      method: 'hrms.task_management.page.task_management_team.task_management_team.get_team_overview',
      callback: (r) => {
        if (!r.message) return;
        const d = r.message;
        setText('total_members', d.total_members);
        setText('ongoing_tasks', d.ongoing_tasks);
        setText('completed_tasks', d.completed_tasks);
        setText('avg_completion_rate', `${d.avg_completion_rate}%`);
        setText('avg_value', d.avg_value);

        drawBar('chart_ongoing', d.ongoing_per_member);
        drawBar('chart_value', d.value_per_member);
        drawBar('chart_completion', d.completion_rate_per_member, { max: 100, suffix: '%' });
        drawBar('chart_highprio', d.high_priority_per_member);
      }
    });
  }
}