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
	get_bulk_edit_fields: function() {
        return [
            'pic_subtask', 'value', 'target_time'
        ];
    },
};
