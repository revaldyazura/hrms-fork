// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Pipeline Recruitment", {
// 	refresh(frm) {

// 	},
// });

// frappe.ui.form.on('Pipeline Recruitment', {
//   onload: function (frm) {
//     frappe.call({
//       method: 'hrms.hr.doctype.pipeline_recruitment.pipeline_recruitment.get_hr_user_recruiters',
//       callback: function (r) {
//         if (r.message) {
//           frm.set_query('team', function () {
//             return {
//               filters: {
//                 name: ['in', r.message]
//               }
//             };
//           });
//         }
//       }
//     });
//   }
// });

// frappe.ui.form.on('Pipeline Recruitment', {
//   onload: function (frm) {
//     frappe.call({
//       method: 'hrms.hr.doctype.pipeline_recruitment.pipeline_recruitment.get_hr_user_and_manager_employees',
//       callback: function (r) {
//         if (r.message) {
//           frm.set_query('team', function () {
//             return {
//               filters: {
//                 name: ['in', r.message]
//               }
//             };
//           });
//         }
//       }
//     });
//   }
// });

frappe.ui.form.on("Pipeline Recruitment", {
  team: function (frm) {
    frappe.call({
      method: "hrms.hr.doctype.pipeline_recruitment.pipeline_recruitment.get_hr_interviewer_emails",
      callback: function (r) {
        let options = [];
        if (r.message && r.message.length) {
          options = r.message.map(opt => opt.value);
        }
        if (!options.includes("recruitment@jkt.ebdesk.com")) {
          options.push("recruitment@jkt.ebdesk.com");
        }
        frm.set_df_property("interviewer", "options", options);
        frm.set_value("interviewer", options[0] || "recruitment@jkt.ebdesk.com");
      }
    });
  }
});

function set_interviewer_options(frm) {
    frappe.call({
        method: "hrms.hr.doctype.pipeline_recruitment.pipeline_recruitment.get_hr_interviewer_emails",
        callback: function (r) {
            let options = [];
            if (r.message && r.message.length) {
                options = r.message.map(opt => opt.value);
            }
            if (!options.includes("recruitment@jkt.ebdesk.com")) {
                options.push("recruitment@jkt.ebdesk.com");
            }
            frm.set_df_property("interviewer", "options", options);
            if (!frm.doc.interviewer || !options.includes(frm.doc.interviewer)) {
                frm.set_value("interviewer", options[0] || "recruitment@jkt.ebdesk.com");
            }
        }
    });
}

// frappe.ui.form.on("Pipeline Recruitment", {
//     onload: function(frm) {
//         set_interviewer_options(frm);
//     },
//     refresh: function(frm) {
//         set_interviewer_options(frm);
//     },
//     team: function(frm) {
//         set_interviewer_options(frm);
//     }
// });

frappe.ui.form.on("Pipeline Recruitment", {
  onload: function(frm) {
    set_interviewer_options(frm);
    frappe.call({
      method: 'hrms.hr.doctype.pipeline_recruitment.pipeline_recruitment.get_hr_user_recruiters',
      callback: function (r1) {
        let recruiter_ids = r1.message || [];
        frappe.call({
          method: 'hrms.hr.doctype.pipeline_recruitment.pipeline_recruitment.get_hr_user_and_manager_employees',
          callback: function (r2) {
            let all_ids = [...new Set([...recruiter_ids, ...(r2.message || [])])];
            frm.set_query('team', () => ({ filters: { name: ['in', all_ids] } }));
          }
        });
      }
    });z
  },
  refresh: set_interviewer_options,
  team: set_interviewer_options
});