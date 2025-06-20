frappe.listview_settings['SubTask'] = {
	get_indicator: function (doc) {
		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		indicator[1] = {Done: "green", Cancel: "red", Hold: "orange", Open: "blue"}[doc.status];
		return indicator;
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
	get_bulk_edit_fields: function() {
        return [
            'pic_subtask', 'value', 'target_time'
        ];
    },
};
