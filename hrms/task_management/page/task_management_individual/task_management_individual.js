frappe.pages["task-management-individual"].on_page_load = async function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Task Management Individual",
		single_column: true,
	});

	if (!window.Chart) {
		await new Promise((res, rej) => {
			const s = document.createElement("script");
			s.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
			s.onload = res;
			s.onerror = rej;
			document.head.appendChild(s);
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
	  /* table styles */
	  .tmto table { width: 100%; border-collapse: collapse; font-size: 13px; }
	  .tmto thead th { text-transform: uppercase; font-size: 11px; letter-spacing: .3px; text-align: center; }
	  .tmto th, .tmto td { border-bottom: 1px solid #eee; padding: 8px 10px; }
	  .tmto th { color: #333; font-weight: 700; background: #fafafa; }
	  .tmto td { text-align: center; }
	  .tmto .empty { color: #888; padding: 8px 10px; }
	  .tmto .pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 600; line-height: 1.6; }
	  .tmto .table-pager { display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 8px; }
	  .tmto .page-info { font-size: 12px; color: #666; }
	`;
	$("<style>").text(css).appendTo($(wrapper));

	$(page.body).append(`
		<div class="tmto">
		  <h3 id="person_title">🧩 Personal Overview</h3>
		  <div class="metrics">
			${m("Ongoing SubTasks", "ongoing_tasks")}
			${m("Total Completed SubTask", "completed_tasks")}
			${m("High Priority SubTask", "high_priority_tasks")}
			${m("Completion Rate", "avg_completion_rate")}
			${m("Avg Value (Complexity) Load", "avg_value")}
		  </div>
		  <h4 style="margin-top:16px" >📊 Workload Visualization</h4>
		  <div class="grid">
			${c("Ongoing SubTask per MainTask (Sorted)", "chart_ongoing")}
			${c("Avg Value Load per MainTask (Sorted)", "chart_value")}
			${c("Completion Rate per MainTask (Sorted)", "chart_completion")}
			${c("High Priority SubTask per MainTask (Sorted)", "chart_highprio")}
		  </div>
		  <h4 style="margin-top:16px">📋 Current SubTask</h4>
		  <div class="card">
			<div id="current_table_wrapper"></div>
		  </div>
		</div>
	`);

	function m(label, id) {
		return `<div class="card metric"><div class="label">${label}</div><div id="${id}" class="value">–</div></div>`;
	}
	function c(title, id) {
		return `<div class="card chart"><div class="title">${title}</div><canvas id="${id}" height="120"></canvas></div>`;
	}

	function setText(id, val) {
		document.getElementById(id).innerText = val ?? "–";
	}

	const personField = page.add_field({
		label: "Employee",
		fieldtype: "Link",
		fieldname: "employee_filter",
		options: "Employee",
		placeholder: "Select Employee",
		reqd: 0,
		onchange: async () => {
			const value = personField.get_value();
			if (!value) {
				clearMetricsAndCharts();
				setPersonTitle(null);
				return;
			}
			const displayName = await getEmployeeName(value);
			setPersonTitle(displayName);
			const { start, end } = getDateFilters();
			load_data(value, start, end);
		},
	});

	// Date range filters
	const startDateField = page.add_field({
		label: "Start Date",
		fieldtype: "Date",
		fieldname: "start_date",
		reqd: 0,
		onchange: () => {
			const emp = personField.get_value();
			if (!emp) return; // wait for employee selection
			const { start, end } = getDateFilters(true);
			load_data(emp, start, end);
		},
	});

	const endDateField = page.add_field({
		label: "End Date",
		fieldtype: "Date",
		fieldname: "end_date",
		reqd: 0,
		onchange: () => {
			const emp = personField.get_value();
			if (!emp) return; // wait for employee selection
			const { start, end } = getDateFilters(true);
			load_data(emp, start, end);
		},
	});

	// Clear dates button (one-click reset)
	page.add_inner_button("Clear Dates", () => {
		// Reset field values
		startDateField?.set_value?.(null);
		endDateField?.set_value?.(null);
		// If employee is selected, refresh without date filters
		const emp = personField.get_value();
		if (emp) {
			load_data(emp, null, null);
		}
	});

	// start with empty state
	clearMetricsAndCharts();
	setPersonTitle(null);

	async function getEmployeeName(employeeName) {
		try {
			const r = await frappe.db.get_value("Employee", employeeName, "employee_name");
			return r?.message?.employee_name || employeeName;
		} catch (e) {
			return employeeName;
		}
	}

	function setPersonTitle(name) {
		const el = document.getElementById("person_title");
		if (!el) return;
		el.textContent = name ? `🧩 ${name} Overview` : "🧩 Personal Overview";
	}

	function getDateFilters(shouldValidate = false) {
		const rawStart = startDateField?.get_value?.() || null;
		const rawEnd = endDateField?.get_value?.() || null;
		// Only apply when both dates are provided
		if (rawStart && rawEnd) {
			if (shouldValidate && rawEnd < rawStart) {
				frappe.msgprint({
					message: "End Date must be on or after Start Date.",
					indicator: "red",
					title: "Invalid Date Range",
				});
				return { start: null, end: null };
			}
			return { start: rawStart, end: rawEnd };
		}
		// If only one is set or none, remove date filter
		return { start: null, end: null };
	}

	function drawBar(canvasId, src, opts = {}) {
		const ctx = document.getElementById(canvasId).getContext("2d");
		if (!src || !src.labels) return;

		const truncate = (s, n = 12) => (s && s.length > n ? s.slice(0, n) + "…" : s);

		new Chart(ctx, {
			type: "bar",
			data: {
				labels: src.labels,
				datasets: [{ data: src.values, backgroundColor: "rgba(66,165,245,0.6)" }],
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: "#ffffff",
						titleColor: "#000",
						bodyColor: "#000",
						borderColor: "#ccc",
						borderWidth: 1,
						titleFont: { size: 14, weight: "bold", family: "'Segoe UI', sans-serif" },
						bodyFont: { size: 13, family: "'Segoe UI', sans-serif" },
						callbacks: {
							title: (items) => src.labels[items[0].dataIndex],
							label: (ctx) => `${ctx.parsed.y}${opts.suffix || ""}`,
						},
					},
				},
				scales: {
					x: {
						offset: true,
						ticks: {
							autoSkip: false,
							maxRotation: 60,
							minRotation: 60,
							color: "#333",
							callback: (val, idx) => truncate(src.labels[idx]),
						},
						grid: { color: "#e0e0e0" },
					},
					y: {
						beginAtZero: true,
						ticks: { color: "#333" },
						grid: { color: "#e0e0e0" },
						suggestedMax: opts.max || undefined,
					},
				},
			},
		});
	}

	function load_data(employee_docname, start_date = null, end_date = null) {
		console.log("load_data for employee:", employee_docname);

		frappe.call({
			method: "hrms.task_management.page.task_management_individual.task_management_individual.get_employee_overview",
			args: {
				employee: employee_docname || null,
				start_date: start_date || null,
				end_date: end_date || null,
			},
			callback: (r) => {
				if (!r.message) return;
				const d = r.message;

				setText("ongoing_tasks", d.ongoing_tasks);
				setText("completed_tasks", d.completed_tasks);
				setText("high_priority_tasks", d.high_priority_tasks);
				setText("avg_completion_rate", `${d.avg_completion_rate}%`);
				setText("avg_value", d.avg_value);

				["chart_ongoing", "chart_value", "chart_completion", "chart_highprio"].forEach(
					(id) => {
						const old = Chart.getChart(id);
						if (old) old.destroy();
					}
				);

				drawBar("chart_ongoing", d.ongoing_per_maintask);
				drawBar("chart_value", d.value_per_maintask);
				drawBar("chart_completion", d.completion_rate_per_maintask, {
					max: 100,
					suffix: "%",
				});
				drawBar("chart_highprio", d.high_priority_per_maintask);

				renderSubtaskTable(d.current_subtasks || []);
			},
		});
	}

	function clearMetricsAndCharts() {
		setText("ongoing_tasks", "–");
		setText("completed_tasks", "–");
		setText("high_priority_tasks", "–");
		setText("avg_completion_rate", "–");
		setText("avg_value", "–");
		["chart_ongoing", "chart_value", "chart_completion", "chart_highprio"].forEach(
			(id) => {
				const old = Chart.getChart(id);
				if (old) old.destroy();
			}
		);
		const wrap = document.getElementById("current_table_wrapper");
		if (wrap) wrap.innerHTML = `<div class="empty">No data</div>`;
	}

	function renderSubtaskTable(rows) {
		const wrap = document.getElementById("current_table_wrapper");
		if (!wrap) return;
		if (!rows || rows.length === 0) {
			wrap.innerHTML = `<div class="empty">No data</div>`;
			return;
		}
		const fmt = (v) => {
			if (!v) return "";
			try {
				const d = new Date(v);
				if (isNaN(d.getTime())) return v;
				return d.toLocaleString();
			} catch(e) { return v; }
		};

		// pagination state
		const pageSize = 5;
		let currentPage = 1;
		const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));

		const prioColor = (p) => {
			const x = (p || '').toLowerCase();
			if (x === 'high') return 'background:#fdecea;color:#b71c1c;'; // red
			if (x === 'medium') return 'background:#fff8e1;color:#8d6e00;'; // yellow
			if (x === 'low') return 'background:#e3f2fd;color:#0d47a1;'; // blue
			return 'background:#eee;color:#555;';
		};
		const statusColor = (s) => {
			switch (s) {
				case 'Done': return 'background:#e8f5e9;color:#1b5e20;'; // green
				case 'Cancel': return 'background:#ffebee;color:#b71c1c;'; // red
				case 'Pause': return 'background:#fff3e0;color:#e65100;'; // orange
				case 'Open': return 'background:#f5f5f5;color:#424242;'; // grey
				case 'Close': return 'background:#f3e5f5;color:#4a148c;'; // purple
				case 'In Progress': return 'background:#e3f2fd;color:#0d47a1;'; // blue
				default: return 'background:#eee;color:#555;';
			}
		};

		const render = () => {
			const start = (currentPage - 1) * pageSize;
			const end = start + pageSize;
			const pageRows = rows.slice(start, end);
			let html = `
				<table>
					<thead>
						<tr>
							<th>MainTask</th>
							<th>Task</th>
							<th>SubTask</th>
							<th>Priority</th>
							<th>Status</th>
							<th>Open Date</th>
							<th>Done Date</th>
						</tr>
					</thead>
					<tbody>
						${pageRows.map(r => `
							<tr>
								<td>${frappe.utils.escape_html(r.maintask_name || "")}</td>
								<td>${frappe.utils.escape_html(r.tasks_name || "")}</td>
								<td>${frappe.utils.escape_html(r.subtask_name || "")}</td>
								<td><span class="pill" style="${prioColor(r.priority)}">${frappe.utils.escape_html(r.priority || "")}</span></td>
								<td><span class="pill" style="${statusColor(r.status)}">${frappe.utils.escape_html(r.status || "")}</span></td>
								<td>${frappe.utils.escape_html(fmt(r.open_date))}</td>
								<td>${frappe.utils.escape_html(fmt(r.done_date))}</td>
							</tr>
						`).join("")}
					</tbody>
				</table>
				<div class="table-pager">
					<button class="btn btn-default btn-sm" data-act="first" ${currentPage===1? 'disabled': ''}>&laquo;</button>
					<button class="btn btn-default btn-sm" data-act="prev" ${currentPage===1? 'disabled': ''}>&lsaquo;</button>
					<span class="page-info">Page ${currentPage} / ${totalPages}</span>
					<button class="btn btn-default btn-sm" data-act="next" ${currentPage===totalPages? 'disabled': ''}>&rsaquo;</button>
					<button class="btn btn-default btn-sm" data-act="last" ${currentPage===totalPages? 'disabled': ''}>&raquo;</button>
				</div>
			`;
			wrap.innerHTML = html;
			wrap.querySelectorAll('button[data-act]').forEach(btn => {
				btn.onclick = () => {
					const act = btn.getAttribute('data-act');
					if (act === 'first') currentPage = 1;
					if (act === 'prev' && currentPage > 1) currentPage -= 1;
					if (act === 'next' && currentPage < totalPages) currentPage += 1;
					if (act === 'last') currentPage = totalPages;
					render();
				};
			});
		};

		render();
	}
};
