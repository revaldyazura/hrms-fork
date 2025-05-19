// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("SubTask", {
	refresh(frm) {
		frm.fields_dict['status'].$input.on('change', function () {
			var selectedOption = $(this).val(); // Get the selected value
			if (selectedOption === 'Cancel') {
				$(this).css('color', 'red'); // Change to red
			} else if (selectedOption === 'Done') {
				$(this).css('color', 'green'); // Change to green
			}
			// ... more options
		});
	},
});
