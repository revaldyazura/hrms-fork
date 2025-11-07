// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.views.calendar["SubTask"] = {
	field_map: {
		start: "subtask_open_date",
		end: "subtask_done_date",
		id: "name",
		// status: "status",
		title: "subtask_name",
	},
	gantt: true,
	filters: [
		{
			fieldtype: "Select",
			fieldname: "status",
			options: "Open\nIn Progress\nPause\nDone\nClose\nCancel",
			label: __("Status"),
		},
	],
	// get_events_method: "hrms.hr.doctype.subtask.subtask.get_events",
	get_events_method: "frappe.desk.calendar.get_events",

};
