frappe.pages['task-management-summary'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Task Forge',
		single_column: true
	});

	// Tempatkan kontainer
	$(page.body).append(`
		<div class="filter-container">
		<div class="filter-row">
			<input type="text" id="filter-maintask" placeholder="Filter Main Task" class="form-control">
			<input type="text" id="filter-pic-subtask" placeholder="Filter PIC SubTask" class="form-control">
		</div>
		<div class="filter-row">
			<input type="text" id="filter-start-date" class="form-control" placeholder="Assign Date" onfocus="(this.type='date')"  onblur="(this.type='text')">
			<input type="text" id="filter-end-date" class="form-control" placeholder="Due Date" onfocus="(this.type='date')" onblur="(this.type='text')">
			<select id="filter-subtask-status" class="form-control">
				<option value="">Sub Task Status</option>
				<option value="Open" style="color: grey">Open</option>
				<option value="In Progress" style="color: blue">In Progress</option>
				<option value="Pause" style="color: orange">Pause</option>
				<option value="Done" style="color: green">Done</option>
				<option value="Close" style="color: purple">Close</option>
				<option value="Cancel" style="color: red">Cancel</option>
			</select>
		</div>
		<div class="filter-actions" style="text-align: right;">
			<button id="reset-filters" class="btn btn-secondary">Reset Filters</button>
		</div>
		</div>
		<div id="task-table"></div>
		<div id="pagination-controls" class="text-center m-3"></div>

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

			#task-table {
				overflow-x: auto;
				padding: 12px;
			}

			#task-table table {
				border-collapse: collapse;
				width: 100%;
				min-width: 1200px;
			}

			#task-table th,
			#task-table td {
				border: 1px solid #ccc;
				text-align: center;
				vertical-align: middle;
				padding: 8px;
			}

			#task-table thead {
				background-color: #f0f0f0;
			}

			#task-table td.bullet-list {
				text-align: left;
			}

			#task-table td.bullet-list ul {
				padding-left: 20px;
				margin: 0;
			}

			#task-table td.bullet-list ul li {
				list-style-type: disc;
				line-height: 1.5;
			}

			#pagination-controls button {
				border: 1px solid #ccc;
				padding: 6px 12px;
				margin: 0 4px;
				cursor: pointer;
				border-radius: 4px;
				background-color: #f9f9f9;
				transition: background-color 0.3s ease;
			}
			#pagination-controls button:hover {
				background-color: #e6e6e6;
			}
			#pagination-controls button.active {
				background-color: #007bff;
				color: white;
				border-color: #007bff;
			}
			#pagination-controls {
				display: flex;
				justify-content: center;
				align-items: center;
				gap: 6px;
				flex-wrap: wrap;
			}

			#pagination-controls .page-btn,
			#pagination-controls .arrow-btn {
				border: 1px solid #ccc;
				padding: 6px 12px;
				cursor: pointer;
				border-radius: 4px;
				background-color: #f9f9f9;
				transition: background-color 0.3s ease;
				font-weight: 500;
			}

			#pagination-controls .page-btn:hover,
			#pagination-controls .arrow-btn:hover {
				background-color: #e6e6e6;
			}

			#pagination-controls .page-btn.active {
				background-color: #007bff;
				color: white;
				border-color: #007bff;
				cursor: default;
			}

			#pagination-controls .ellipsis {
				padding: 6px 10px;
				color: #777;
				pointer-events: none;
			}
			
		</style>
	`);

	frappe.call({
		method: "hrms.hr.page.task_management_summary.task_management_summary.get_task_report_data",
		callback: function (r) {
			if (r.message) {
				console.log('task data result: ', r.message)
				render_table(r.message, 1);
				let allData = r.message; // simpan semua data

				// Fungsi filtering
				function applyFilters() {
					const maintask = $('#filter-maintask').val().toLowerCase();

					const startDate = $('#filter-start-date').val();
					const endDate = $('#filter-end-date').val();
					if (startDate && endDate && startDate > endDate) {
						frappe.msgprint("You can't put start date over the due date, please change it okay.");
						return;
					}
					// const picTask = $('#filter-pic-task').val().toLowerCase();
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
							isInDateRange &&
							// (!picTask || (row.pic_task_name || "").toLowerCase().includes(picTask)) &&
							(!picSubtask || (row.pic_subtask_name || "").toLowerCase().includes(picSubtask)) &&
							(!status || (row.sub_task_status || "").toLowerCase() === status)
						);
					});

					render_table(filtered, 1);
				}

				// Trigger on input change
				$('#filter-maintask,  #filter-start-date, #filter-end-date,  #filter-pic-subtask, #filter-subtask-status')
					.on('input change', applyFilters);
				$('#reset-filters').on('click', function () {
					$('#filter-maintask').val('');
					// $('#filter-pic-task').val('');
					$('#filter-pic-subtask').val('');
					$('#filter-start-date').val('');
					$('#filter-end-date').val('');
					$('#filter-subtask-status').val('');
					render_table(allData, 1); // tampilkan semua data
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

	function renderPaginationControls(currentPage, totalPages) {
		const pagination = document.getElementById("pagination-controls");
		pagination.innerHTML = "";

		const createButton = (text, page, className = "page-btn", disabled = false) => {
			const btn = document.createElement("button");
			btn.textContent = text;
			btn.className = className;
			if (disabled) {
				btn.disabled = true;
				btn.style.opacity = 0.5;
			}
			if (className === "page-btn" && page === currentPage) {
				btn.classList.add("active");
			}
			btn.addEventListener("click", () => {
				if (!disabled && page !== currentPage) {
					render_table(globalData, page); // ← panggil render_table dengan halaman baru
				}
			});
			return btn;
		};

		// tombol kiri
		pagination.appendChild(createButton("«", currentPage - 1, "arrow-btn", currentPage === 1));

		let maxPagesToShow = 5;
		let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
		let endPage = startPage + maxPagesToShow - 1;

		if (endPage > totalPages) {
			endPage = totalPages;
			startPage = Math.max(1, endPage - maxPagesToShow + 1);
		}

		if (startPage > 1) {
			pagination.appendChild(createButton("1", 1));
			if (startPage > 2) {
				pagination.appendChild(createEllipsis());
			}
		}

		for (let i = startPage; i <= endPage; i++) {
			pagination.appendChild(createButton(i, i));
		}

		if (endPage < totalPages) {
			if (endPage < totalPages - 1) {
				pagination.appendChild(createEllipsis());
			}
			pagination.appendChild(createButton(totalPages, totalPages));
		}

		pagination.appendChild(createButton("»", currentPage + 1, "arrow-btn", currentPage === totalPages));
	}

	function createEllipsis() {
		const ellipsis = document.createElement("span");
		ellipsis.className = "ellipsis";
		ellipsis.innerText = "...";
		return ellipsis;
	}




	let currentPage = 1;
	const mainTasksPerPage = 3;
	let globalData = [];

	function groupByMainTask(data) {
		const grouped = {};
		data.forEach(row => {
			if (!grouped[row.mt_name]) {
				grouped[row.mt_name] = [];
			}
			grouped[row.mt_name].push(row);
		});
		return grouped;
	}

	function paginateMainTaskGroups(groupedData, page = 1) {
		const mainTaskKeys = Object.keys(groupedData);
		const start = (page - 1) * mainTasksPerPage;
		const end = start + mainTasksPerPage;
		const selectedKeys = mainTaskKeys.slice(start, end);

		let paginatedRows = [];
		selectedKeys.forEach(key => {
			paginatedRows = paginatedRows.concat(groupedData[key]);
		});
		return paginatedRows;
	}


	function render_table(data, page = 1) {
		globalData = data; // simpan data yang akan dipakai ulang
		currentPage = page; // simpan current page global

		const container = document.getElementById("task-table");
		container.innerHTML = "";

		const grouped = groupByMainTask(data);
		const paginatedRows = paginateMainTaskGroups(grouped, page);

		// Hitung rowspan
		const mainTaskRowspan = {};
		const taskRowspan = {};
		const picTaskRowspan = {};

		data = paginatedRows;
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
				<th>Assigned By</th>
				<th>Team</th>
				<th>Assign Date</th>
				<th>Due Date</th>
				<th>Task</th>
				<th>Task Target Time</th>
				<th>PIC Task</th>
				<th>Sub Task</th>
				<th>Sub Task Target Time</th>
				<th>Sub Task Types</th>
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
		const renderedTaskPic = {};


		data.forEach(row => {
			const isOwnerSubtask = row.pic_task_user_id === row.sub_task_owner

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
				td.className = "bullet-list";
				let assign_members = row.assign_by_members ? row.assign_by_members.split(',').map(s => s.trim()) : [];
				if (assign_members.length > 0) {
					const ul = document.createElement("ul");
					assign_members.forEach(assign_member => {
						const li = document.createElement("li");
						li.textContent = assign_member
						ul.appendChild(li);
					});
					td.appendChild(ul);
				} else {
					td.textContent = "-";
				}
				tr.appendChild(td);

				// Team
				td = document.createElement("td");
				td.rowSpan = mainTaskRowspan[row.mt_name];
				td.className = "bullet-list";


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

				// Task Target Time
				td = document.createElement("td");
				td.rowSpan = taskRowspan[taskKey];
				td.textContent = row.target_time || "-";
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

			if (isOwnerSubtask) {// Sub Task
				let td = document.createElement("td");
				td.textContent = row.sub_task || "-";
				tr.appendChild(td);

				td = document.createElement("td");
				td.textContent = row.subtask_target_time || "-";
				tr.appendChild(td);

				td = document.createElement("td");
				// td.rowSpan = picTaskRowspan[picKey];
				td.className = "bullet-list";


				let subtask_types = row.subtask_types ? row.subtask_types.split(',').map(s => s.trim()) : [];
				if (subtask_types.length > 0) {
					const ul = document.createElement("ul");
					subtask_types.forEach(type => {
						const li = document.createElement("li");
						li.textContent = type;
						ul.appendChild(li);
					});
					td.appendChild(ul);
				} else {
					td.textContent = "-";
				}

				tr.appendChild(td);

				td = document.createElement("td");
				td.textContent = row.pic_subtask_name || "-";
				tr.appendChild(td);

				td = document.createElement("td");
				td.textContent = row.value_subtask || "-";
				tr.appendChild(td);

				td = document.createElement("td");
				td.textContent = row.sub_task_status || "-";
				if (row.sub_task_status === "Open") td.style.color = "grey";
				if (row.sub_task_status === "In Progress") td.style.color = "blue";
				else if (row.sub_task_status === "Done") td.style.color = "green";
				else if (row.sub_task_status === "Close") td.style.color = "purple";
				else if (row.sub_task_status === "Pause") td.style.color = "orange";
				else if (row.sub_task_status === "Cancel") td.style.color = "red";
				tr.appendChild(td);

			}
			// else {
			// 	for (let i =0; i<5; i++){
			// 		td = document.createElement("td")
			// 		td.textContent = "-"
			// 		tr.appendChild(td)
			// 	}
			// }
			tbody.appendChild(tr);

		});

		const totalPages = Math.ceil(Object.keys(grouped).length / mainTasksPerPage);
		renderPaginationControls(page, totalPages);
		container.appendChild(table);
	}

	// function render_table(data) {
	// 	const container = document.getElementById("task-table");
	// 	container.innerHTML = "";

	// 	// Buat struktur data: mt → task → pic_task → [subtask]
	// 	const grouped = {};
	// 	data.forEach(row => {
	// 		// hanya tampilkan subtask milik pic
	// 		if (row.pic_task_user_id !== row.sub_task_owner) return;

	// 		if (!grouped[row.mt_name]) grouped[row.mt_name] = { row, tasks: {} };
	// 		if (!grouped[row.mt_name].tasks[row.t_name]) {
	// 			grouped[row.mt_name].tasks[row.t_name] = {};
	// 		}
	// 		if (!grouped[row.mt_name].tasks[row.t_name][row.pic_task_user_id]) {
	// 			grouped[row.mt_name].tasks[row.t_name][row.pic_task_user_id] = {
	// 				pic_task_name: row.task_pic_name,
	// 				subtasks: []
	// 			};
	// 		}

	// 		grouped[row.mt_name].tasks[row.t_name][row.pic_task_user_id].subtasks.push(row);
	// 	});

	// 	// Bangun tabel
	// 	const table = document.createElement("table");
	// 	table.className = "table table-bordered";
	// 	table.style.width = "100%";
	// 	table.innerHTML = `
	// 	<thead>
	// 		<tr>
	// 			<th>Main Task</th>
	// 			<th>Assigned By</th>
	// 			<th>Team</th>
	// 			<th>Assign Date</th>
	// 			<th>Due Date</th>
	// 			<th>Task</th>
	// 			<th>Task Target Time</th>
	// 			<th>PIC Task</th>
	// 			<th>Sub Task</th>
	// 			<th>Sub Task Target Time</th>
	// 			<th>PIC Sub Task</th>
	// 			<th>Value</th>
	// 			<th>Sub Task Status</th>
	// 		</tr>
	// 	</thead>
	// 	<tbody></tbody>
	// `;

	// 	const tbody = table.querySelector("tbody");

	// 	for (const [mt_name, mt_group] of Object.entries(grouped)) {
	// 		let mtRendered = false;
	// 		const mt_rowspan = Object.values(mt_group.tasks)
	// 			.flatMap(t => Object.values(t).map(pic => pic.subtasks.length))
	// 			.reduce((a, b) => a + b, 0);

	// 		for (const [t_name, task_group] of Object.entries(mt_group.tasks)) {
	// 			for (const [pic_user_id, pic_data] of Object.entries(task_group)) {
	// 				const subtasks = pic_data.subtasks;
	// 				const task_rowspan = subtasks.length;

	// 				subtasks.forEach((row, index) => {
	// 					const tr = document.createElement("tr");

	// 					// Main Task info
	// 					if (!mtRendered) {
	// 						let td = document.createElement("td");
	// 						td.rowSpan = mt_rowspan;
	// 						td.textContent = row.maintask_name || "-";
	// 						tr.appendChild(td);

	// 						td = document.createElement("td");
	// 						td.rowSpan = mt_rowspan;
	// 						td.textContent = row.assigned_by || "-";
	// 						tr.appendChild(td);

	// 						td = document.createElement("td");
	// 						td.rowSpan = mt_rowspan;
	// 						td.className = "bullet-list";
	// 						const ul = document.createElement("ul");
	// 						row.team_members.split(',').map(s => s.trim()).forEach(member => {
	// 							const li = document.createElement("li");
	// 							li.textContent = member;
	// 							ul.appendChild(li);
	// 						});
	// 						td.appendChild(ul);
	// 						tr.appendChild(td);

	// 						td = document.createElement("td");
	// 						td.rowSpan = mt_rowspan;
	// 						td.textContent = convert_date(row.assign_date, "dd-mm-yyyy") || "-";
	// 						tr.appendChild(td);

	// 						td = document.createElement("td");
	// 						td.rowSpan = mt_rowspan;
	// 						td.textContent = convert_date(row.due_date, "dd-mm-yyyy") || "-";
	// 						tr.appendChild(td);

	// 						mtRendered = true;
	// 					}

	// 					// Task info
	// 					if (index === 0) {
	// 						let td = document.createElement("td");
	// 						td.rowSpan = task_rowspan;
	// 						td.textContent = row.task || "-";
	// 						tr.appendChild(td);

	// 						td = document.createElement("td");
	// 						td.rowSpan = task_rowspan;
	// 						td.textContent = row.target_time || "-";
	// 						tr.appendChild(td);

	// 						td = document.createElement("td");
	// 						td.rowSpan = task_rowspan;
	// 						td.textContent = pic_data.pic_task_name || "-";
	// 						tr.appendChild(td);
	// 					}

	// 					// SubTask info
	// 					let td = document.createElement("td");
	// 					td.textContent = row.sub_task || "-";
	// 					tr.appendChild(td);

	// 					td = document.createElement("td");
	// 					td.textContent = row.subtask_target_time || "-";
	// 					tr.appendChild(td);

	// 					td = document.createElement("td");
	// 					td.textContent = row.pic_subtask_name || "-";
	// 					tr.appendChild(td);

	// 					td = document.createElement("td");
	// 					td.textContent = row.value_subtask || "-";
	// 					tr.appendChild(td);

	// 					td = document.createElement("td");
	// 					td.textContent = row.sub_task_status || "-";
	// 					td.style.color = row.sub_task_status === "Open" ? "blue" :
	// 						row.sub_task_status === "Done" ? "green" :
	// 							row.sub_task_status === "Hold" ? "orange" :
	// 								row.sub_task_status === "Cancel" ? "red" : "";
	// 					tr.appendChild(td);

	// 					tbody.appendChild(tr);
	// 				});
	// 			}
	// 		}
	// 	}

	// 	container.appendChild(table);
	// }

}
