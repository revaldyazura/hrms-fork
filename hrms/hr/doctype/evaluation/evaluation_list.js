frappe.listview_settings['Evaluation'] = {
	get_indicator: function (doc) {
		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		indicator[1] = {Done: "green", Cancel: "red", Hold: "gray", Open: "blue"}[doc.status];
		return indicator;
	},
	add_fields: ['subtask', 'subtask_name', 'pic_subtask', 'pic_subtask_name'],

	formatters: {
		subtask(val, df, doc) {
			return doc.subtask_name || val;
		}, pic_subtask(val, df, doc) {
			return doc.pic_subtask_name || val;
		}
	}
};
