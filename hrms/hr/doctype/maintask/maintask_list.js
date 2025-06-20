frappe.listview_settings['MainTask'] = {
	get_indicator: function (doc) {
		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		indicator[1] = {Done: "green", Cancel: "red", Hold: "orange", Open: "blue"}[doc.status];
		return indicator;
	},
	add_fields: ['assigned_by', 'assigned_by_name'],

	formatters: {
		assigned_by(val, df, doc) {
			return doc.assigned_by_name || val;
		}
	}
}
