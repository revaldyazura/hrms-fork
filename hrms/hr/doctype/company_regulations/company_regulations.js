// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company Regulations", {
    refresh(frm) {
        const can_manage_file =
            frappe.user.has_role("HR User") || frappe.user.has_role("System Manager");
        frm.toggle_display("file", can_manage_file);
        frm.toggle_display("show_file", Boolean(frm.doc.file));
    },

    file(frm) {
        frm.toggle_display("show_file", Boolean(frm.doc.file));
    },

    show_file(frm) {
        if (!frm.doc.file) {
            frappe.msgprint(__("No file attached."));
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __("View File"),
            size: "extra-large",
            fields: [
                {
                    fieldtype: "HTML",
                    fieldname: "file_viewer",
                },
            ],
        });

        dialog.show();

        dialog.$wrapper.find(".modal-dialog").css({
            width: "98vw",
            maxWidth: "98vw",
            height: "98vh",
            margin: "1vh auto",
        });

        dialog.$wrapper.find(".modal-content").css({
            height: "100%",
        });

        dialog.$wrapper.find(".modal-body").css({
            height: "calc(100% - 60px)",  // minus header height
            padding: "0",
        });

        dialog.$wrapper.find(".form-layout").css({
            height: "100%",
        });

        dialog.$wrapper.find(".form-page").css({
            height: "100%",
        });
        const file_url = frm.doc.file;
        const src = file_url.includes("#") ? file_url : `${file_url}#toolbar=0`;

        const $wrapper = dialog.fields_dict.file_viewer.$wrapper;

        $wrapper.css({
            height: "100%",
        });

        const $iframe = $("<iframe>", {
            src,
            css: {
                width: "100%",
                height: "90vh",
                border: "none",
                display: "block",
            },
        });

        $wrapper.empty().append($iframe);
    },
});
