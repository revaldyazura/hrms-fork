frappe.listview_settings['MainTask'] = {
	add_fields: ['assigned_by', 'assigned_by_name'],

	formatters: {
		assigned_by(val, df, doc) {
			return doc.assigned_by_name || val;
		}
	}
}
