frappe.listview_settings['SubTask'] = {
	get_indicator: function (doc) {
		let color_map = {
			"Done": "green",
			"Cancel": "red",
			"Pause": "orange",
			"Open": "grey",
			"Close": "purple",
			"In Progress": "blue" // pakai string key dan warna valid CSS
		};

		return [__(doc.status), color_map[doc.status] || "gray", "status,=," + doc.status];
	},
	add_fields: ['maintask', 'maintask_name', 'tasks', 'tasks_name', 'pic_subtask', 'pic_subtask_name'],

	formatters: {
		maintask(val, df, doc) {
			return doc.maintask_name || val;
		},
		tasks(val, df, doc) {
			return doc.tasks_name || val;
		}, pic_subtask(val, df, doc) {
			return doc.pic_subtask_name || val;
		},
	},
	refresh(listview) {
		let workspace = 'Task Management';

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: workspace,
			type: 'List'
		};
		frappe.breadcrumbs.update();
	},
	onload(listview) {
		// hindari loop set_route berulang
		if (window.__subtask_pic_filter_applied) return;

		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Employee',
				filters: { user_id: frappe.session.user },
				fieldname: 'name'
			},
			callback: (r) => {
				const employee_id = r?.message?.name;
				if (!employee_id) return;

				window.__subtask_pic_filter_applied = true;

				if (frappe.boot?.versions?.frappe?.startsWith?.('15')) {
					frappe.set_route('List', 'SubTask', 'List', { 'pic_subtask': ['=', employee_id] });
				} else {
					frappe.set_route('List', 'SubTask', { 'pic_subtask': ['=', employee_id] });
				}
			}
		});
	}
};
