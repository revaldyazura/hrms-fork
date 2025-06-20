// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Evaluation Summary"] = {
	onload: function (report) {
		frappe.query_report._prev_row = {}; // reset tiap reload
	},
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!frappe.query_report._prev_row) {
			frappe.query_report._prev_row = {};
		}

		const prev = frappe.query_report._prev_row;

		// if (["main_task"].includes(column.fieldname)) {
		// 	if (
		// 		data.main_task === prev.main_task
		// 	) {
		// 		return ""; // kosongkan kolom
		// 	} else {
		// 		prev.main_task = data.main_task;
		// 	}
		// }
		// if (["task"].includes(column.fieldname)) {
		// 	if (
		// 		data.task === prev.task
		// 	) {
		// 		return ""; // kosongkan kolom
		// 	} else {
		// 		prev.task = data.task;
		// 	}
		// }

		// Centering
		value = `<div style="text-align: center;">${value}</div>`;

		// Color status
		if (column.fieldname === "sub_task_status") {
			if (value.includes("Done")) {
				value = `<span style="color: green; font-weight: bold;">${value}</span>`;
			} else if (value.includes("Cancel")) {
				value = `<span style="color: red; font-weight: bold;">${value}</span>`;
			} else if (value.includes("Hold")) {
				value = `<span style="color: orange; font-weight: bold;">${value}</span>`;
			} else if (value.includes("Open")) {
				value = `<span style="color: blue; font-weight: bold;">${value}</span>`;
			}
		}

		return value;
	}
};
