frappe.listview_settings['Evaluation'] = {
	add_fields: ['subtask', 'subtask_name', 'pic_subtask', 'pic_subtask_name'],

	formatters: {
		subtask(val, df, doc) {
			return doc.subtask_name || val;
		}, pic_subtask(val, df, doc) {
			return doc.pic_subtask_name || val;
		}
	}
};
