// hrms/public/js/auto_repeat_override.js
(function() {
    if (frappe._patched_auto_repeat_prompt) return;
    frappe._patched_auto_repeat_prompt = true;

    const original = frappe.utils.new_auto_repeat_prompt;

    frappe.utils.new_auto_repeat_prompt = function(frm) {
        const fields = [
            {
                fieldname: "frequency",
                fieldtype: "Select",
                label: __("Frequency"),
                reqd: 1,
                options: [
                    { label: __("Daily"), value: "Daily" },
                    { label: __("Weekly"), value: "Weekly" },
                    { label: __("Monthly"), value: "Monthly" },
                    { label: __("Quarterly"), value: "Quarterly" },
                    { label: __("Half-yearly"), value: "Half-yearly" },
                    { label: __("Yearly"), value: "Yearly" },
                ],
            },
            {
                fieldname: "start_date",
                fieldtype: "Date",
                label: __("Start Date"),
                reqd: 1,
                default: frappe.datetime.nowdate(),
            },
            {
                fieldname: "end_date",
                fieldtype: "Date",
                label: __("End Date"),
                description: __("Must be after the Start Date (cannot be the same day). Leave empty to repeat indefinitely."),
            },
        ];

        const d = frappe.prompt(
            fields,
            function(values) {
                const start = values.start_date;
                const end = values.end_date;

                // Client-side early validation (supaya user tahu sebelum request server)
                if (end) {
                    if (end === start) {
                        frappe.msgprint({
                            title: __("Invalid Dates"),
                            message: __("End Date must not be the same as Start Date."),
                            indicator: "red"
                        });
                        return;
                    }
                    if (frappe.datetime.get_diff(end, start) <= 0) {
                        frappe.msgprint({
                            title: __("Invalid Dates"),
                            message: __("End Date must be after Start Date."),
                            indicator: "red"
                        });
                        return;
                    }
                }

                frappe.call({
                    method: "frappe.automation.doctype.auto_repeat.auto_repeat.make_auto_repeat",
                    args: {
                        doctype: frm.doc.doctype,
                        docname: frm.doc.name,
                        frequency: values.frequency,
                        start_date: start,
                        end_date: end
                    },
                    callback(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: __("Auto Repeat created for this document"),
                                indicator: "green"
                            });
                            frm.reload_doc();
                            // Tampilkan panduan setelah form reload (tunggu 2 detik supaya dokumen baru siap)
                            setTimeout(() => {
                                const autoRepeatName = frm?.doc?.auto_repeat;
                                if (autoRepeatName) {
                                    const dlg = frappe.msgprint({
                                        title: __('Next Step'),
                                        message: __([
                                            '<div style="line-height:1.5">',
                                            'Open the <b>Schedule</b> tab in the new Auto Repeat document to review / adjust the detailed schedule (e.g. specific weekday for Weekly, Repeat on Day for Monthly, end date, etc).',
                                            '<div style="display:flex;justify-content:flex-end;margin-top:12px;gap:8px;">',
                                            '<button class="btn btn-sm btn-primary" data-open-repeat>Open Repeat</button>',
                                            '</div>',
                                            '</div>'
                                        ].join('')),
                                        indicator: 'blue'
                                    });

                                    setTimeout(() => {
                                        const btn = dlg.$wrapper.find('[data-open-repeat]');
                                        btn.on('click', () => {
                                            dlg.hide();
                                            frappe.set_route('Form', 'Auto Repeat', autoRepeatName);

                                            const tryOpenSchedule = () => {
                                                try {
                                                    if (!(cur_frm && cur_frm.doc && cur_frm.doctype === 'Auto Repeat' && cur_frm.doc.name === autoRepeatName)) {
                                                        return false;
                                                    }
                                                    // 1. API resmi bila tersedia
                                                    if (cur_frm.page && typeof cur_frm.page.change_to === 'function') {
                                                        cur_frm.page.change_to('Schedule');
                                                        // verifikasi tab aktif dengan anchor data-fieldname
                                                        const activeAnchor = cur_frm.wrapper.querySelector('.form-tabs a.nav-link.active[data-fieldname="section_break_10"]');
                                                        if (activeAnchor) return true;
                                                    }
                                                    // 2. Langsung klik anchor berdasarkan data-fieldname (struktur DOM yg kamu kirim)
                                                    const scheduleAnchor = cur_frm.wrapper.querySelector('.form-tabs a.nav-link[data-fieldname="section_break_10"]');
                                                    if (scheduleAnchor) {
                                                        if (!scheduleAnchor.classList.contains('active')) scheduleAnchor.click();
                                                        return true;
                                                    }
                                                    // 3. Fallback: label teks (jika berbeda environment)
                                                    const links = cur_frm.wrapper.querySelectorAll('.form-tabs .nav-link, .form-tabs .nav-item .nav-link');
                                                    for (const el of links) {
                                                        const raw = (el.getAttribute('data-label') || el.innerText || '').trim().toLowerCase();
                                                        if (raw === 'schedule') {
                                                            el.click();
                                                            return true;
                                                        }
                                                    }
                                                } catch(e) { /* ignore */ }
                                                return false;
                                            };

                                            let attempts = 0;
                                            const interval = setInterval(() => {
                                                if (tryOpenSchedule() || attempts > 30) { // ~6 detik max
                                                    clearInterval(interval);
                                                }
                                                attempts++;
                                            }, 200);
                                        });
                                    }, 40);
                                }
                            }, 1000);
                        }
                    }
                });
            },
            __("Auto Repeat"),
            __("Save")
        );

        // ================= Real-time Date Validation & Constraints (Refactored) =================
        // Menghindari lag: hilangkan spam alert, gunakan inline message + debounce + restore last valid.
        setTimeout(() => {
            if (!d || d.hidden) return;
            const startField = d.get_field('start_date');
            const endField = d.get_field('end_date');
            if (!(startField && endField)) return;

            const $start = startField.$input;
            const $end = endField.$input;
            // Inline message container (sekali buat)
            let $msg = $end.parent().find('.invalid-end-msg');
            if (!$msg.length) {
                $msg = $('<div class="invalid-end-msg small" style="margin-top:4px; color:#dc2626; display:none;"></div>');
                $end.after($msg);
            }

            let currentMin = null;
            function setEndMin(startValUser) {
                if (!$end) return;
                if (startValUser) {
                    // Normalize user input to system format to avoid locale issues
                    let startSys;
                    try {
                        startSys = frappe.datetime.user_to_str(startValUser);
                    } catch(e) {
                        startSys = startValUser; // fallback if already sys format
                    }
                    const minDateStr = frappe.datetime.add_days(startSys, 1); // YYYY-MM-DD
                    if (currentMin !== minDateStr) { // update only if changed to reduce churn
                        currentMin = minDateStr;
                        // For native date inputs (if any)
                        $end.attr('min', minDateStr);
                        // For Flatpickr/Pickadate used by Frappe, pass a Date object for robustness
                        try {
                            if (endField.datepicker && endField.datepicker.config) {
                                const minDateObj = frappe.datetime.str_to_obj(minDateStr);
                                endField.datepicker.set('minDate', minDateObj);
                            }
                        } catch(e) { /* ignore */ }
                    }
                } else {
                    currentMin = null;
                    $end.removeAttr('min');
                    try {
                        if (endField.datepicker && endField.datepicker.config) {
                            endField.datepicker.set('minDate', null);
                        }
                    } catch(e) { /* ignore */ }
                }
            }

            let validating = false;
            let invalidActive = false;
            const validatePair = frappe.utils.debounce(() => {
                if (validating) return;
                validating = true;
                try {
                    const startValUser = $start.val();
                    const endValUser = $end.val();
                    setEndMin(startValUser);

                    // Jika belum ada start date, bersihkan pesan tapi jangan paksa apapun
                    if (!startValUser) {
                        if (invalidActive) { $msg.hide(); $end.removeClass('is-invalid'); invalidActive = false; }
                        return;
                    }

                    // Open ended (end kosong) = valid; sembunyikan pesan kalau sebelumnya invalid
                    if (!endValUser) {
                        if (invalidActive) { $msg.hide(); $end.removeClass('is-invalid'); invalidActive = false; }
                        return;
                    }

                    // Normalize both dates to system format (YYYY-MM-DD) before comparing
                    let startSys, endSys;
                    try { startSys = frappe.datetime.user_to_str(startValUser); } catch(e) { startSys = startValUser; }
                    try { endSys = frappe.datetime.user_to_str(endValUser); } catch(e) { endSys = endValUser; }
                    const diffOk = frappe.datetime.get_diff(endSys, startSys) > 0;
                    if (!diffOk) {
                        // Tunjukkan pesan persisten, JANGAN restore ke value lama (menghindari parse loop)
                        if (!invalidActive) {
                            $msg.text(__('End Date must be strictly after Start Date.')).show();
                            $end.addClass('is-invalid');
                            invalidActive = true;
                        }
                        // Kosongkan sekali agar user memilih ulang; jangan panggil set_value (memicu parse & msg lain)
                        if ($end.val()) {
                            $end.val('');
                        }
                        return;
                    }

                    // Valid
                    if (invalidActive) {
                        $msg.hide();
                        $end.removeClass('is-invalid');
                        invalidActive = false;
                    }
                } finally {
                    validating = false;
                }
            }, 100);

            $start.on('change', validatePair);
            $end.on('change', validatePair);
            validatePair();
        }, 10);
    };
})();