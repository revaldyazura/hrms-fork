frappe.pages['evaluation-summary'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Evaluation Summary',
		single_column: true
	});
	// Tempatkan kontainer
	$(page.body).append(`
		<div class="filter-container">
		<div class="filter-row">
			<input type="text" id="filter-maintask" placeholder="Filter Main Task" class="form-control">
<!--			<input type="text" id="filter-assigned-by" placeholder="Filter Assigned By" class="form-control">-->
<!--			<input type="text" id="filter-pic-task" placeholder="Filter PIC Task" class="form-control">-->
<!--			<input type="text" id="filter-pic-subtask" placeholder="Filter PIC SubTask" class="form-control">-->
		</div>
		<div class="filter-row">
			<input type="text" id="filter-start-date" class="form-control" placeholder="Assign Date" onfocus="(this.type='date')"  onblur="(this.type='text')">
			<input type="text" id="filter-end-date" class="form-control" placeholder="Due Date" onfocus="(this.type='date')" onblur="(this.type='text')">
		</div>
		<div class="filter-actions" style="text-align: right;">
			<button id="reset-filters" class="btn btn-secondary">Reset Filters</button>
		</div>
		</div>
		<div id="evaluation-table"></div>

		<style>
			.filter-container {
				padding: 12px;
				margin: 10px 0px;
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

			#evaluation-table {
				overflow-x: auto;
				padding: 0px 12px;
			}

			#evaluation-table table {
				border-collapse: collapse;
				width: 100%;
				min-width: 1200px;
			}

			#evaluation-table th,
			#evaluation-table td {
				border: 1px solid #ccc;
				text-align: center;
				vertical-align: middle;
				padding: 8px;
			}

			#evaluation-table thead {
				background-color: #f0f0f0;
			}

			#evaluation-table td.bullet-list {
				text-align: left;
			}

			#evaluation-table td.bullet-list ul {
				padding-left: 20px;
				margin: 0;
			}

			#evaluation-table td.bullet-list ul li {
				list-style-type: disc;
				line-height: 1.5;
			}
		</style>
	`);

	frappe.call({
		method: "hrms.hr.page.evaluation_summary.evaluation_summary.get_evaluation_data",
		callback: function (r) {
			if (r.message) {
				console.log('data result: ', r.message)
				render_table(r.message);
				let allData = r.message; // simpan semua data

				// Fungsi filtering
				function applyFilters() {
					const maintask = $('#filter-maintask').val().toLowerCase();
					// const assignedBy = $('#filter-assigned-by').val().toLowerCase();

					const startDate = $('#filter-start-date').val();
					const endDate = $('#filter-end-date').val();
					if ((startDate && endDate) && (startDate > endDate)) {
						frappe.msgprint("You can't put start date over the due date, please change it okay.");
						return;
					}
					// const picTask = $('#filter-pic-task').val().toLowerCase();
					// const picSubtask = $('#filter-pic-subtask').val().toLowerCase();
					// const status = $('#filter-subtask-status').val().toLowerCase();

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
							// (!assignedBy || (row.assigned_by || "").toLowerCase().includes(assignedBy)) &&
							isInDateRange
							// &&
							// (!picTask || (row.pic_task_name || "").toLowerCase().includes(picTask)) &&
							// (!picSubtask || (row.pic_subtask_name || "").toLowerCase().includes(picSubtask)) &&
							// (!status || (row.sub_task_status || "").toLowerCase() === status)
						);
					});

					render_table(filtered);
				}

				// Trigger on input change
				$('#filter-maintask, #filter-start-date, #filter-end-date '
					// '#filter-assigned-by, ' +
					// +
					// '#filter-pic-task, #filter-pic-subtask, #filter-subtask-status'
				)
					.on('input change', applyFilters);
				$('#reset-filters').on('click', function () {
					$('#filter-maintask').val('');
					// $('#filter-assigned-by').val('');
					// $('#filter-pic-task').val('');
					// $('#filter-pic-subtask').val('');
					$('#filter-start-date').val('');
					$('#filter-end-date').val('');
					// $('#filter-subtask-status').val('');
					render_table(allData); // tampilkan semua data
				});
			}
		}
	});

	function convert_date(dateString, to_format) {
		const dateObject = new Date(dateString);
		const day = dateObject.getDate();
		const month = dateObject.getMonth() + 1;
		const fullYear = dateObject.getFullYear();
		const formattedDay = day < 10 ? '0' + day : day;
		const formattedMonth = month < 10 ? '0' + month : month;
		let formattedDate = ""
		if (to_format === "dd-mm-yyyy") {
			formattedDate = `${formattedDay}-${formattedMonth}-${fullYear}`;
		} else if (to_format === "yyyy-mm-dd") {
			formattedDate = `${fullYear}-${formattedMonth}-${formattedDay}`;
		}
		return formattedDate
	}

	function render_table(data) {
		const container = document.getElementById("evaluation-table");
		container.innerHTML = "";

		// Hitung rowspan
		const mainTaskRowspan = {};
		const taskRowspan = {};
		const picTaskRowspan = {};

		data.forEach(row => {
			mainTaskRowspan[row.mt_name] = (mainTaskRowspan[row.mt_name] || 0) + 1;
			const key = `${row.mt_name}|||${row.t_name}`;
			taskRowspan[key] = (taskRowspan[key] || 0) + 1;
			const picKey = `${row.t_name}|||${row.pic_task_user_id}`;
			picTaskRowspan[picKey] = (picTaskRowspan[picKey] || 0) + 1;
		});

		const table = document.createElement("table");
		table.className = "table table-bordered";
		table.style.width = "100%";
		table.innerHTML = `
		<thead>
			<tr>
				<th>Main Task</th>
				<th>Assign Date</th>
				<th>Due Date</th>
				<th>Task</th>
				<th>PIC Task</th>
				<th>Sub Task</th>
				<th>Sub Task Target Time</th>
				<th>PIC Sub Task</th>
				<th>Value</th>
				<th>Performance</th>
				<th>Final Target Time</th>
				<th>Contribution</th>
			</tr>
		</thead>
		<tbody></tbody>
	`;

		const tbody = table.querySelector("tbody");
		const renderedMainTask = {};
		const renderedTask = {};
		const renderedTaskPic = {};
		const renderedSubTask = {};

		data.forEach(row => {
			const isOwnerSubtask = row.pic_task_user_id === row.sub_task_owner

			const tr = document.createElement("tr");

			// Main Task Cell
			if (!renderedMainTask[row.mt_name]) {
				let td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.textContent = row.maintask_name || "-";
				tr.appendChild(td);

				// Assign Date
				td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.textContent = convert_date(row.assign_date, "dd-mm-yyyy") || "-";
				tr.appendChild(td);

				// Due Date
				td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.textContent = convert_date(row.due_date, "dd-mm-yyyy") || "-";
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

				renderedTask[taskKey] = true;
			} 

			const picKey = `${row.t_name}|||${row.pic_task_user_id}`;
			if (!renderedTaskPic[picKey]) {
				// PIC Task
				let td = document.createElement("td");
				td.rowSpan = picTaskRowspan[picKey];
				td.textContent = row.task_pic_name || "-";
				tr.appendChild(td);
				renderedTaskPic[picKey] = true;
			}
			
			if (isOwnerSubtask) {
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

				// Performance
				td = document.createElement("td");
				td.textContent = row.performance || "-";
				tr.appendChild(td);

				// Final Target Time
				td = document.createElement("td");
				td.textContent = row.final_target_time || "-";
				tr.appendChild(td);

				// Contribution
				td = document.createElement("td");
				td.textContent = row.contribution || "-";
				tr.appendChild(td);
			}
			console.log('column subtask', row.sub_task);
			tbody.appendChild(tr);
		});

		container.appendChild(table);
	}
}
