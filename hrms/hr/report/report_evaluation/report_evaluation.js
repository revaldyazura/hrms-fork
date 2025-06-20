// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Report Evaluation"] = {
	filters: [
		// {
		// 	"fieldname": "my_filter",
		// 	"label": __("My Filter"),
		// 	"fieldtype": "Data",
		// 	"reqd": 1,
		// },
	],
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

		return value;
	}
};
