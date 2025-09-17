frappe.listview_settings['Tasks'] = {
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
	add_fields: ['maintask', 'maintask_name', 'pic_task', 'pic_task_name'],

	formatters: {
		maintask(val, df, doc) {
			return doc.maintask_name || val;
		}, pic_task(val, df, doc) {
			return doc.pic_task_name || val;
		}
	}
}
