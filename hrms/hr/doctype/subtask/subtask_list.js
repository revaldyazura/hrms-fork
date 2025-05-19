frappe.listview_settings['SubTask'] = {
	get_indicator: function (doc) {
		var indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];
		indicator[1] = { Done: "green", Cancel: "red", Hold: "gray", Open: "blue" }[doc.status];
		return indicator;
	}
};
