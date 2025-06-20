frappe.pages['task-management-summary'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Task Management Summary',
		single_column: true
	});

	// Tempatkan kontainer
	$(page.body).append(`
		<div class="filter-container">
		<div class="filter-row">
			<input type="text" id="filter-maintask" placeholder="Filter Main Task" class="form-control">
			<input type="text" id="filter-assigned-by" placeholder="Filter Assigned By" class="form-control">
			<input type="text" id="filter-pic-task" placeholder="Filter PIC Task" class="form-control">
			<input type="text" id="filter-pic-subtask" placeholder="Filter PIC SubTask" class="form-control">
		</div>
		<div class="filter-row">
			<input type="date" id="filter-start-date" class="form-control" placeholder="Start Date">
			<input type="date" id="filter-end-date" class="form-control" placeholder="End Date">
			<select id="filter-subtask-status" class="form-control">
				<option value="">Sub Task Status</option>
				<option value="Open" style="color: blue">Open</option>
				<option value="Hold" style="color: orange">Hold</option>
				<option value="Done" style="color: green">Done</option>
				<option value="Cancel" style="color: red">Cancel</option>
			</select>
		</div>
		<div class="filter-actions" style="text-align: right;">
			<button id="reset-filters" class="btn btn-secondary">Reset Filters</button>
		</div>
		</div>
		<div id="main-task-table"></div>

		<style>
			.filter-container {
				padding: 12px;
				margin-top: 20px;
				margin-bottom: 20px;
				display: flex;
				flex-direction: column;
				gap: 10px;
			}

			.filter-row {
				display: flex;
				flex-wrap: wrap;
				gap: 10px;
			}

			.filter-row .form-control {
				flex: 1 1 200px;
				min-width: 160px;
				padding: 6px 10px;
			}

			#main-task-table {
				overflow-x: auto;
				padding: 12px;
			}

			#main-task-table table {
				border-collapse: collapse;
				width: 100%;
				min-width: 1200px;
			}

			#main-task-table th,
			#main-task-table td {
				border: 1px solid #ccc;
				text-align: center;
				vertical-align: middle;
				padding: 8px;
			}

			#main-task-table thead {
				background-color: #f0f0f0;
			}

			#main-task-table td.bullet-list {
				text-align: left;
			}

			#main-task-table td.bullet-list ul {
				padding-left: 20px;
				margin: 0;
			}

			#main-task-table td.bullet-list ul li {
				list-style-type: disc;
				line-height: 1.5;
			}
		</style>
	`);

	frappe.call({
		method: "hrms.hr.page.task_management_summary.task_management_summary.get_main_task_data",
		callback: function (r) {
			if (r.message) {
				console.log('data result: ', r.message)
				render_table(r.message);
				let allData = r.message; // simpan semua data

				// Fungsi filtering
				function applyFilters() {
					const maintask = $('#filter-maintask').val().toLowerCase();
					const assignedBy = $('#filter-assigned-by').val().toLowerCase();

					const startDate = $('#filter-start-date').val();
					const endDate = $('#filter-end-date').val();
					if (startDate && endDate && startDate > endDate) {
						frappe.msgprint("You can't put start date over the due date, please change it okay.");
						return;
					}
					const picTask = $('#filter-pic-task').val().toLowerCase();
					const picSubtask = $('#filter-pic-subtask').val().toLowerCase();
					const status = $('#filter-subtask-status').val().toLowerCase();

					const filtered = allData.filter(row => {
						const assignDate = (row.assign_date || "").split('T')[0]; // ensure format is YYYY-MM-DD
						const dueDate = (row.due_date || "").split('T')[0];
						let isInDateRange = true;
						if (startDate && endDate) {
							isInDateRange =
								(assignDate >= startDate && assignDate <= endDate) ||
								(dueDate >= startDate && dueDate <= endDate);
						}
						return (
							(!maintask || (row.maintask_name || "").toLowerCase().includes(maintask)) &&
							(!assignedBy || (row.assigned_by || "").toLowerCase().includes(assignedBy)) &&
							isInDateRange &&
							(!picTask || (row.pic_task_name || "").toLowerCase().includes(picTask)) &&
							(!picSubtask || (row.pic_subtask_name || "").toLowerCase().includes(picSubtask)) &&
							(!status || (row.sub_task_status || "").toLowerCase() === status)
						);
					});

					render_table(filtered);
				}

				// Trigger on input change
				$('#filter-maintask, #filter-assigned-by, #filter-start-date, #filter-end-date, #filter-pic-task, #filter-pic-subtask, #filter-subtask-status')
					.on('input change', applyFilters);
				$('#reset-filters').on('click', function () {
					$('#filter-maintask').val('');
					$('#filter-assigned-by').val('');
					$('#filter-pic-task').val('');
					$('#filter-pic-subtask').val('');
					$('#filter-start-date').val('');
					$('#filter-end-date').val('');
					$('#filter-subtask-status').val('');
					render_table(allData); // tampilkan semua data
				});
			}
		}
	});

	function render_table(data) {
		const container = document.getElementById("main-task-table");
		container.innerHTML = "";

		// Hitung rowspan
		const mainTaskRowspan = {};
		const taskRowspan = {};

		data.forEach(row => {
			mainTaskRowspan[row.mt_name] = (mainTaskRowspan[row.mt_name] || 0) + 1;
			const key = `${row.mt_name}|||${row.t_name}`;
			taskRowspan[key] = (taskRowspan[key] || 0) + 1;
		});

		const table = document.createElement("table");
		table.className = "table table-bordered";
		table.style.width = "100%";
		table.innerHTML = `
		<thead>
			<tr>
				<th>Main Task</th>
				<th>Assigned By</th>
				<th>Team</th>
				<th>Assign Date</th>
				<th>Due Date</th>
				<th>Task</th>
				<th>Task Target Time</th>
				<th>PIC Task</th>
				<th>Sub Task</th>
				<th>Sub Task Target Time</th>
				<th>PIC Sub Task</th>
				<th>Value</th>
				<th>Sub Task Status</th>
			</tr>
		</thead>
		<tbody></tbody>
	`;

		const tbody = table.querySelector("tbody");
		const renderedMainTask = {};
		const renderedTask = {};

		data.forEach(row => {
			const tr = document.createElement("tr");

			// Main Task Cell
			if (!renderedMainTask[row.mt_name]) {
				let td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.textContent = row.maintask_name || "-";
				tr.appendChild(td);

				// Assigned By
				td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.textContent = row.assigned_by || "-";
				tr.appendChild(td);

				// Team
				td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.className = "bullet-list";

				// Pisahkan string menjadi array dan buat bullet list
				let members = row.team_members ? row.team_members.split(',').map(s => s.trim()) : [];
				if (members.length > 0) {
					const ul = document.createElement("ul");
					members.forEach(member => {
						const li = document.createElement("li");
						li.textContent = member;
						ul.appendChild(li);
					});
					td.appendChild(ul);
				} else {
					td.textContent = "-";
				}

				tr.appendChild(td);

				// Assign Date
				td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.textContent = row.assign_date || "-";
				tr.appendChild(td);

				// Due Date
				td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.textContent = row.due_date || "-";
				tr.appendChild(td);

				renderedMainTask[row.mt_name] = true;
			}

			// Task Cell
			const taskKey = `${row.mt_name}|||${row.t_name}`;
			if (!renderedTask[taskKey]) {

				// Task Name
				let td = document.createElement("td");
				td.rowSpan = taskRowspan[taskKey];
				td.textContent = row.task || "-";
				tr.appendChild(td);

				// Task Target Time
				td = document.createElement("td");
				td.rowSpan = taskRowspan[taskKey];
				td.textContent = row.target_time || "-";
				tr.appendChild(td);

				// PIC Task
				td = document.createElement("td");
				td.rowSpan = taskRowspan[taskKey];
				td.textContent = row.pic_task_name || "-";
				tr.appendChild(td);

				renderedTask[taskKey] = true;
			}

			// Sub Task
			let td = document.createElement("td");
			td.textContent = row.sub_task || "-";
			tr.appendChild(td);

			// Sub Task Target Time
			td = document.createElement("td");
			td.textContent = row.subtask_target_time || "-";
			tr.appendChild(td);

			// PIC Sub Task
			td = document.createElement("td");
			td.textContent = row.pic_subtask_name || "-";
			tr.appendChild(td);

			// Value
			td = document.createElement("td");
			td.textContent = row.value_subtask || "-";
			tr.appendChild(td);

			// Sub Task Status
			td = document.createElement("td");
			if (row.sub_task_status == "Open") {
				td.style.color = "blue"
			} else if (row.sub_task_status == "Done") {
				td.style.color = "green"
			} else if (row.sub_task_status == "Hold") {
				td.style.color = "orange"
			} else if (row.sub_task_status == "Cancel") {
				td.style.color = "red"
			}
			td.textContent = row.sub_task_status || "-";
			tr.appendChild(td);

			tbody.appendChild(tr);
		});

		container.appendChild(table);
	}
}
