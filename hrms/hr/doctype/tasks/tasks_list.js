frappe.listview_settings['Tasks'] = {
	get_indicator: function (doc) {
		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		indicator[1] = {Done: "green", Cancel: "red", Hold: "orange", Open: "blue"}[doc.status];
		return indicator;
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
