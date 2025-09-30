frappe.listview_settings['Evaluation'] = {
	add_fields: ['subtask', 'subtask_name', 'pic_subtask', 'pic_subtask_name'],

	formatters: {
		subtask(val, df, doc) {
			return doc.subtask_name || val;
		}, pic_subtask(val, df, doc) {
			return doc.pic_subtask_name || val;
		}
	},

	refresh(listview) {
		let workspace = 'Task Management';

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: workspace,
			type: 'List'
		};
		frappe.breadcrumbs.update();

		document.querySelectorAll('.list-subject').forEach(function(col){
			col.style.maxWidth = "500px";
			col.style.minWidth = "500px";
		})
	},
};
