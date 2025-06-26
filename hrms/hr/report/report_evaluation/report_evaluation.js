// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Report Evaluation"] = {
	filters: [
        {
            fieldname: "maintask",
            label: "Main Task",
            fieldtype: "Link",
            options: "MainTask",
            reqd: 0
        }
    ],
	// onload: function (report) {
	// 	frappe.query_report._prev_row = {}; // reset tiap reload
	// },
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		// if (!frappe.query_report._prev_row) {
		// 	frappe.query_report._prev_row = {};
		// }
		//
		// const prev = frappe.query_report._prev_row;

		// Centering
		value = `<div style="text-align: center;">${value}</div>`;

		return value;
	}
};
