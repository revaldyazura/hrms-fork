frappe.listview_settings['Tasks'] = {
	add_fields: ['maintask', 'maintask_name', 'pic_task', 'pic_task_name'],

	formatters: {
		maintask(val, df, doc) {
			return doc.maintask_name || val;
		}, pic_task(val, df, doc) {
			return doc.pic_task_name || val;
		}
	}
}
