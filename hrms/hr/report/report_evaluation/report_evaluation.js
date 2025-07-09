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

	onload: function (report) {
		report.page.add_inner_button("Export Individual Report", function () {
			let dialog = new frappe.ui.Dialog({
				title: "Export Individual Report",
				fields: [
					{
						label: "PIC SubTask",
						fieldname: "pic_subtask",
						fieldtype: "Link",
						options: "Employee",
						reqd: 1
					},
					{
						label: "From Date",
						fieldname: "from_date",
						fieldtype: "Date",
						reqd: 1
					},
					{
						label: "To Date",
						fieldname: "to_date",
						fieldtype: "Date",
						reqd: 1
					}
				],
				primary_action_label: "Generate Report",
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
						`/api/method/hrms.hr.report.report_evaluation.custom_report_evaluation.export_individual_evaluation?filters=${encoded_filters}`
					);

					dialog.hide();
				}
			});

			dialog.show();
		});
		report.page.add_inner_button("Export Department Report", function () {
			let dialog = new frappe.ui.Dialog({
				title: "Export Department Report",
				fields: [
					{
						label: "Department Name",
						fieldname: "department",
						fieldtype: "Link",
						options: "Department",
						reqd: 1,
						get_query: function () {
							return {
								filters: {
									parent_department: "All Departments"
								}
							}
						}
					},
					{
						label: "Division Name",
						fieldname: "division",
						fieldtype: "Link",
						options: "Department",
						reqd: 1
					},
					{
						label: "Section Name",
						fieldname: "section",
						fieldtype: "Link",
						options: "Department",
						reqd: 1
					},
					{
						label: "From Date",
						fieldname: "from_date",
						fieldtype: "Date",
						reqd: 1
					},
					{
						label: "To Date",
						fieldname: "to_date",
						fieldtype: "Date",
						reqd: 1
					}
				],
				primary_action_label: "Generate Report",
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
						`/api/method/hrms.hr.report.report_evaluation.custom_report_evaluation.export_evaluation_with_average?filters=${encoded_filters}`
					);

					dialog.hide();
				}
			});

			dialog.fields_dict.department.df.onchange = () => {
				const selected_department = dialog.get_value("department");

				if (!selected_department) {
					dialog.fields_dict.division.set_value("");
					dialog.fields_dict.section.set_value("");
					return;
				}

				dialog.fields_dict.division.set_value("");

				dialog.fields_dict.division.df.get_query = function () {
					return {
						filters: {
							parent_department: selected_department
						}
					};
				};

				dialog.fields_dict.division.refresh();
			};
			dialog.fields_dict.division.df.onchange = () => {
				const selected_division = dialog.get_value("division");

				if (!selected_division) {
					dialog.fields_dict.section.set_value("");
					return;
				}

				dialog.fields_dict.section.set_value("");


				dialog.fields_dict.section.df.get_query = function () {
					return {
						filters: {
							parent_department: selected_division
						}
					};
				};

				dialog.fields_dict.section.refresh();
			};

			dialog.show();
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		value = `<div style="text-align: center;">${value}</div>`;

		return value;
	}
};
