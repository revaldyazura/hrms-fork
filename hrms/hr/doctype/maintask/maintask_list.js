frappe.listview_settings['MainTask'] = {
	get_indicator: function (doc) {
		let color_map = {
			"Done": "green",
			"Cancel": "red",
			"Pause": "orange",
			"Open": "grey",
			"Close": "purple",
			"In Progress": "blue" // pakai string key dan warna valid CSS
		};
		
		return [__(doc.status), color_map[doc.status] || "grey", "status,=," + doc.status];
	},

	refresh(listview) {
		let workspace = 'Task Management';

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: workspace,
			type: 'List'
		};
		frappe.breadcrumbs.update();
	},
}
