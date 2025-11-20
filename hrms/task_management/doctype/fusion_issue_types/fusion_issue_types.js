// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fusion Issue Types", {
    onload(frm) {
        const m = sessionStorage.getItem('prefill_fusion_maintask');
        if (m) {
            // set field maintask hanya jika kosong (atau force set jika mau)
            if (!frm.doc.maintask) {
                frm.set_value('maintask', m);
            }
            // hapus supaya tidak terpakai untuk create dokumen lain
            sessionStorage.removeItem('prefill_fusion_maintask');
        }

        // juga fallback ke route_options kalau ada
        if (frappe.route_options && frappe.route_options.maintask) {
            frm.set_value('maintask', frappe.route_options.maintask);
            frappe.route_options = null;
        }
    }
});
