// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Report Task Management"] = {
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
	filters: [
		{
			fieldname: "status",
			label: __("Sub Task Status"),
			fieldtype: "Select",
			options: " \nOpen\nDone\nHold\nCancel",
			default: "Open",
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!frappe.query_report._prev_row) {
			frappe.query_report._prev_row = {};
		}

		const prev = frappe.query_report._prev_row;


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
