// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Report Task Management"] = {
	// filters: [
		// {
		// 	"fieldname": "my_filter",
		// 	"label": __("My Filter"),
		// 	"fieldtype": "Data",
		// 	"reqd": 1,
		// },
	// ],
	onload: function (report) {
		frappe.query_report._prev_row = {}; // reset tiap reload

		report.page.add_inner_button("Export Team Task", function () {
			let dialog = new frappe.ui.Dialog({
				title: "Export Team Task",
				fields: [
					{
						label: "Team Name",
						fieldname: "team",
						fieldtype: "Link",
						options: "Team",
						reqd: 1
					},
					{
						label: "From Date",
						fieldname: "from_date",
						fieldtype: "Datetime",
						reqd: 1
					},
					{
						label: "To Date",
						fieldname: "to_date",
						fieldtype: "Datetime",
						reqd: 1
					},
					{
						label: "Separate sheets by PIC",
						fieldname: "separate_sheets_by_pic",
						fieldtype: "Check",
						default: 0
					},
					{
						label: "Filter by Open Date",
						fieldname: "filter_by_open_date",
						fieldtype: "Check",
						default: 0
					}
				],
				primary_action_label: "Generate",
				primary_action(values) {
					// Validasi tanggal
					if (values.from_date > values.to_date) {
						frappe.msgprint({
							title: __("Invalid Date Range"),
							message: __("The <b>From Date</b> cannot be later than the <b>To Date</b>."),
							indicator: 'red'
						});
						return;
					}

					const encoded_filters = encodeURIComponent(JSON.stringify(values));
					window.open(
						`/api/method/hrms.hr.report.report_task_management.custom_export_task_management.export_team_task_management?filters=${encoded_filters}`
					);

					dialog.hide();
				}
			});

			dialog.show();
		});
	},
	filters: [
		{
			fieldname: "status",
			label: __("Sub Task Status"),
			fieldtype: "Select",
			options: " \nOpen\nIn Progress\nPause\nDone\nClose\nCancel",
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
			} else if (value.includes("Pause")) {
				value = `<span style="color: orange; font-weight: bold;">${value}</span>`;
			} else if (value.includes("Open")) {
				value = `<span style="color: grey; font-weight: bold;">${value}</span>`;
			}else if (value.includes("In Progress")) {
				value = `<span style="color: blue; font-weight: bold;">${value}</span>`;
			}else if (value.includes("Close")) {
				value = `<span style="color: violet; font-weight: bold;">${value}</span>`;
			}
		}

		return value;
	}
};
