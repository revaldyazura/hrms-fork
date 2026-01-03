// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tasks", {
	refresh(frm) {
		let workspace = "Task Management";

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: workspace,
			doctype: frm.doctype,
			type: "Form",
		};
		frappe.breadcrumbs.update();

		if (frm.is_new()) {
			frm.set_df_property("status", "options", ["Open"]);
			frm.set_value("status", "Open");
		}

		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.tasks.tasks.user_edit_tasks",
				args: {
					task_name: frm.doc.name,
				},
				callback: function (r) {
					const readonly_fields = [
						"target_time",
						"maintask",
						"task_pic",
						"unit_target_time",
					];
					if (r.message.includes("task_pics") && !r.message.includes("owner_tasks") &&
						!r.message.includes("admin") && !r.message.includes("assign_by_maintask") && !r.message.includes("pic_maintask")) {
						readonly_fields.forEach((field) => {
							frm.set_df_property(field, "read_only", 1);
						});
					} else if (r.message.includes("none")) {
						frm.set_read_only(true);
						frm.disable_save();
					} else if (r.message.includes("admin")) {
						
					}

					if (
						(r.message.includes("task_pics") || r.message.includes("admin"))
						&&
						["Open", "In Progress"].includes(frm.doc.status)
					) {
						frm.add_custom_button(
							"Generate SubTask from Template",
							() => {
								frappe.call({
									method: "hrms.hr.doctype.tasks.tasks.get_subtask_template_list",
									callback: (r) => {
										let options = r.message.map((d) => ({
											label: d.template_name,
											value: d.name,
										}));
										frappe.prompt(
											[
												{
													fieldtype: "Select",
													label: "Choose Template",
													fieldname: "template",
													options: options,
													reqd: 1,
												},
											],
											(values) => {
												frappe.call({
													method: "hrms.hr.doctype.tasks.tasks.get_template_details",
													args: { template_name: values.template },
													callback: (res) => {
														let subtask = res.message;
														show_subtask_dialog(frm, subtask);
													},
												});
											},
											"Select Template"
										);
									},
								});
							},
							__("Actions")
						);
						frm.add_custom_button(
							"Create SubTask for This Task",
							function () {
								if (!frm.doc || !frm.doc.name) return;
								frappe.route_options = {
									maintask: frm.doc.maintask,
									tasks: frm.doc.name,
								};
								frappe.new_doc("SubTask");
							},
							__("Actions")
						);
					}
				},
			});
			frm.add_custom_button(
				"Show SubTask of This Tasks",
				function () {
					if (!frm.doc.name) return;

					const make_dialog = () => {
						const dlg = new frappe.ui.Dialog({
							title: __("SubTask of {0}", [frm.doc.task_name || ""]),
							size: "large", // baseline; we'll override with custom CSS to reach ~85% viewport
							fields: [
								{ fieldname: "results_section", fieldtype: "Section Break" },
								{ fieldname: "subtask_html", fieldtype: "HTML" },
								{ fieldname: "pagination_html", fieldtype: "HTML" },
								{ fieldname: "bottom_actions", fieldtype: "HTML" },
							],
							primary_action_label: __("Close"),
							primary_action() {
								dlg.hide();
							},
						});

						// Tag wrapper & inject improved styling for full-width table
						dlg.$wrapper.addClass("wide-subtask-dialog");
						if (!document.getElementById("req-dialog-style-fixed")) {
							const style = document.createElement("style");
							style.id = "req-dialog-style-fixed";
							style.textContent = `
                        .wide-subtask-dialog .modal-dialog { max-width:85vw; width:85vw; }
                        .wide-subtask-dialog .modal-content { width:100%; }
                        .wide-subtask-dialog .modal-body { max-height:72vh; overflow:auto; padding: 8px 14px 12px; }
                        .wide-subtask-dialog .form-layout, 
                        .wide-subtask-dialog .form-page, 
                        .wide-subtask-dialog .form-section, 
                        .wide-subtask-dialog .section-body { width:100% !important; max-width:100% !important; margin:0; padding:0; }
                        .wide-subtask-dialog .form-column { width:100% !important; max-width:100% !important; flex:0 0 100%; padding:0; }
                        .wide-subtask-dialog .frappe-control { margin-bottom:6px; }
                        .wide-subtask-dialog .frappe-control[data-fieldname="subtask_html"],
                        .wide-subtask-dialog .frappe-control[data-fieldname="pagination_html"],
                        .wide-subtask-dialog .frappe-control[data-fieldname="bottom_actions"] { width:100% !important; margin:0; padding:0; }
                        .wide-subtask-dialog .req-table-wrapper { width:100%; }
                        .wide-subtask-dialog .req-table { width:100%; table-layout:auto; }
                        .wide-subtask-dialog .req-table th { white-space:nowrap; text-align:center; vertical-align:middle; }
                        .wide-subtask-dialog .req-table td { white-space:nowrap; }
                        .wide-subtask-dialog .req-table td.id-cell { white-space:normal; word-break:normal; font-family:inherit; }
                        .wide-subtask-dialog .req-table td.title-cell { white-space:normal; word-break:normal; overflow-wrap:break-word; hyphens:auto; min-width:150px; line-height:1.3; }
                        .wide-subtask-dialog .req-table td.desc-cell { white-space:normal; line-height:1.3; max-width:460px; width:35%; overflow:hidden; }
                        .wide-subtask-dialog .req-table td.wrap-cell { white-space:normal; line-height:1.3; word-break:break-word; }
                        .wide-subtask-dialog .req-table td.text-center { text-align:center; }
                        .wide-subtask-dialog .tech-val-icon { display:inline-block; width:18px; font-weight:600; color: var(--green, #2e7d32); }
                        .wide-subtask-dialog .tech-val-icon.off { color:#bbb; }
                        @media (max-width: 1200px) {
                            .wide-subtask-dialog .req-table th, .wide-subtask-dialog .req-table td { white-space:normal; }
                        }
                    `;
							document.head.appendChild(style);
						}
						// Force any existing form columns (after render) to 100%
						setTimeout(() => {
							dlg.$wrapper
								.find(".form-column")
								.css({ width: "100%", maxWidth: "100%", flex: "0 0 100%" });
						}, 0);

						const state = { page: 1, page_size: 5 };

						const columns = [
							{ key: "name", label: "ID" },
							{ key: "subtask_name", label: "SubTask Title" },
							{ key: "description", label: "Description" },
							{ key: "pic_subtask_name", label: "PIC SubTask Name" },
							{ key: "priority", label: "Priority" },
							{ key: "value", label: "Value" },
							{ key: "target_time", label: "Target Time" },
							{ key: "unit_target_time", label: "Unit Target Time" },
							{ key: "type", label: "SubTask Type" },
							{ key: "created_by", label: "Created By" },
							{ key: "status", label: "Status" },
							{ key: "actions", label: "Actions" },
						];

						function esc(v) {
							if (v == null) return "";
							return String(v)
								.replace(/&/g, "&amp;")
								.replace(/</g, "&lt;")
								.replace(/>/g, "&gt;")
								.replace(/"/g, "&quot;");
						}

						function strip_html(html) {
							if (!html) return "";
							// Fast path: if no tag markers, return as-is
							if (!/[<>&]/.test(html)) return html;
							const tmp = document.createElement("div");
							tmp.innerHTML = html;
							const text = tmp.textContent || tmp.innerText || "";
							return text.trim();
						}

						function fetch_and_render() {
							frappe.call({
								method: "hrms.hr.doctype.tasks.tasks.get_subtask",
								args: {
									task_id: frm.doc.name,
									page: state.page,
									page_size: state.page_size,
								},
								callback: (r) => {
									const payload = r.message || { rows: [], total: 0 };
									render_table(payload.rows, payload.total);
									render_pagination(payload.total);
								},
							});
						}

						function truncate(str, n = 60) {
							if (!str) return "";
							return str.length > n ? str.slice(0, n) + "…" : str;
						}

						function row_class(row) {
							if (row.status === "Done") return "success";
							if (row.status === "Cancel") return "danger";
							return "";
						}

						function render_table(rows, total) {
							let html = "";
							if (!rows.length) {
								html = `<div class="text-muted" style="padding:12px">${__(
									"No SubTask found."
								)}</div>`;
							} else {
								html +=
									'<div class="req-table-wrapper" style="max-height:420px; overflow:auto;">';
								html +=
									'<table class="table table-bordered table-compact req-table" style="margin:0">';
								html +=
									"<thead><tr>" +
									columns.map((c) => `<th>${esc(c.label)}</th>`).join("") +
									"</tr></thead>";
								html += "<tbody>";

								// Helper: truncate text to 140 chars with ellipsis
								function truncate_140(txt) {
									if (!txt) return "";
									return txt.length > 140 ? txt.slice(0, 140) + "..." : txt;
								}
								// Hyphen wrap for ID
								function hyphen_wrap(id) {
									if (!id) return "";
									// Escape first then insert <wbr> after '-'
									let safe = esc(id);
									return safe.replace(/-/g, "-<wbr>");
								}

								rows.forEach((row) => {
									html +=
										`<tr class="req-row ${row_class(row)}" data-name="${esc(
											row.name
										)}"` +
										` data-subtask_name="${esc(
											row.subtask_name || ""
										)}" data-description="${esc(row.description || "")}"` +
										` data-pic_subtask_name="${esc(
											row.pic_subtask_name || ""
										)}" data-priority="${esc(
											row.priority || ""
										)}" data-value="${esc(row.value || "")}"` +
										` data-target_time="${esc(
											row.target_time || ""
										)}" data-unit_target_time="${esc(
											row.unit_target_time || ""
										)}"` +
										` data-status="${esc(
											row.status || ""
										)}" data-created_by="${esc(row.created_by || "")}">`;
									columns.forEach((c) => {
										if (c.key === "name") {
											// Hyphen-based wrapping for ID
											const id_display = hyphen_wrap(row.name || "");
											html += `<td class="id-cell" title="${esc(
												row.name || ""
											)}">${id_display}</td>`;
										} else if (c.key === "subtask_name") {
											html += `<td class="title-cell" title="${esc(
												row.subtask_name || ""
											)}">${esc(row.subtask_name || "")}</td>`;
										} else if (c.key === "description") {
											const raw = row.description || "";
											const plain = strip_html(raw);
											const truncated = truncate_140(plain);
											html += `<td class="desc-cell" title="${esc(
												plain
											)}">${esc(truncated)}</td>`;
										} else if (c.key === "type") {
											const full_types = row.type || "";
											html += `<td class="desc-cell" title="${esc(
												full_types
											)}">${esc(full_types)}</td>`;
										} else if (c.key === "actions") {
											html += `<td class="action-cell" style="min-width:70px;">
                                        <button class="btn btn-xs btn-primary open-req" data-name="${esc(
												row.name
											)}">${__("View")}</button>
                                    </td>`;
										} else {
											html += `<td>${esc(row[c.key] || "")}</td>`;
										}
									});
									html += "</tr>";
								});
								html += "</tbody></table></div>";
								html += `<div class="mt-2 small text-muted">${__(
									"Total"
								)}: ${total}</div>`;
							}
							dlg.fields_dict.subtask_html.$wrapper.html(html);
							bind_row_events();
						}

						function render_pagination(total) {
							const total_pages = Math.max(1, Math.ceil(total / state.page_size));
							if (state.page > total_pages) state.page = total_pages;
							let html =
								'<div class="d-flex align-items-center gap" style="margin-top:8px;">';
							html += `<button class="btn btn-xs btn-default pag-btn" data-dir="prev" ${state.page <= 1 ? "disabled" : ""
								}>${__("Prev")}</button>`;
							html += `<span style="padding:0 8px">${__("Page")} ${state.page
								} / ${total_pages}</span>`;
							html += `<button class="btn btn-xs btn-default pag-btn" data-dir="next" ${state.page >= total_pages ? "disabled" : ""
								}>${__("Next")}</button>`;
							html += "</div>";
							dlg.fields_dict.pagination_html.$wrapper.html(html);
							dlg.fields_dict.pagination_html.$wrapper
								.find(".pag-btn")
								.on("click", function () {
									const dir = $(this).data("dir");
									if (dir === "prev" && state.page > 1) {
										state.page -= 1;
									}
									if (dir === "next") {
										state.page += 1;
									}
									fetch_and_render();
								});
						}

						function bind_row_events() {
							// Open button
							dlg.$wrapper
								.find(".open-req")
								.off("click")
								.on("click", function () {
									const docname = $(this).data("name");
									frappe.set_route("Form", "SubTask", docname);
								});
						}

						dlg.show();
						fetch_and_render();
					};

					make_dialog();
				},
				__("Actions")
			);
		}
	},
	onload: function (frm) {
		frm.set_query("maintask", function () {
			return {
				query: "hrms.hr.doctype.tasks.tasks.get_open_maintask_as_the_owner",
			};
		});
		// frm.set_query("pic_task", function () {
		// 	if (!frm.doc.maintask) {
		// 		frappe.msgprint("Choose the main task field first.");
		// 		return {};
		// 	}
		// 	return {
		// 		query: "hrms.hr.doctype.tasks.tasks.get_employees_by_role_and_team",
		// 		filters: {
		// 			maintask: frm.doc.maintask,
		// 		},
		// 	};
		// });
		frappe.after_ajax(() => {
			// Tunggu hingga field tersedia di DOM
			setTimeout(() => {
				const field_wrapper = frm.fields_dict["target_time"];
				if (!field_wrapper) return;

				const input = field_wrapper.$wrapper.find("input");

				input.on("input", function () {
					let value = $(this).val();

					// Cek apakah hanya angka
					if (!/^\d*$/.test(value)) {
						frappe.msgprint({
							title: __("Invalid Input"),
							message: __("Only numeric values are allowed in Target Time."),
							indicator: "red",
						});
						$(this).val(value.replace(/\D/g, ""));
					}
					if (value === "0") {
						frappe.msgprint({
							title: __("Invalid Value"),
							message: __("Target Time must be greater than 0."),
							indicator: "red",
						});
						$(this).val("1"); // Kosongkan input
						return;
					}
				});
			}, 300); // Delay sedikit agar field render dulu
		});
		frm.fields_dict["task_pic"].grid.get_field("employee").get_query = function (
			doc,
			cdt,
			cdn
		) {
			if (!frm.doc.maintask) {
				frappe.msgprint("Choose the main task field first.");
				return {};
			}
			return {
				query: "hrms.hr.doctype.tasks.tasks.get_employees_by_role_and_team",
				filters: {
					maintask: frm.doc.maintask,
				},
			};
		};
	},
});

function show_subtask_dialog(frm, subtask) {
	// Ambil MainTask dari field parent
	const main_task_name = frm.doc.maintask;

	if (!main_task_name) {
		frappe.msgprint("MainTask Not Found.");
		return;
	}

	// Ambil daftar employee dari MainTask.team
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "MainTask",
			name: main_task_name,
		},
		callback: function (r) {
			if (!r.message) {
				frappe.msgprint("Failed to get MainTask Data.");
				return;
			}

			const team_employees = (r.message.team || []).map((row) => row.employee);

			// Lanjut ke dialog setelah data team tersedia
			let fields = [];

			subtask.forEach((subtask, i) => {
				fields.push(
					{
						fieldname: `section_${i}`,
						fieldtype: "Section Break",
						label: `SubTask ${i + 1}: ${subtask.subtask_name_template}`,
					},
					{
						fieldname: `subtask_name_template_${i}`,
						label: "SubTask Name",
						fieldtype: "Data",
						default: `${subtask.subtask_name_template}`,
						reqd: 1,
					},
					{
						fieldname: `value_template_${i}`,
						label: "Value SubTask",
						fieldtype: "Select",
						options: ["1", "2", "3"],
						default: subtask.value_template,
					},
					{
						fieldname: `description_template_${i}`,
						label: "Description",
						fieldtype: "Text Editor",
						default: subtask.description_template,
					},
					{
						fieldname: `target_time_template_${i}`,
						label: "Target Time",
						fieldtype: "Int",
						default: subtask.target_time_template,
					},
					{
						fieldname: `unit_target_time_template_${i}`,
						label: "Unit Target Time",
						fieldtype: "Select",
						options: ["Hours", "Minutes"],
						default: subtask.unit_target_time_template,
					},
					{
						fieldname: `status_template_${i}`,
						label: "Status",
						fieldtype: "Select",
						options: ["Open"],
						default: subtask.status_template,
					},
					{
						fieldname: `priority_template_${i}`,
						label: "Priority",
						fieldtype: "Select",
						options: ["Low", "Medium", "High"],
						default: subtask.priority_template,
					},
					{
						fieldname: `pic_subtask_template_${i}`,
						label: "PIC SubTask",
						fieldtype: "Link",
						options: "Employee",
						reqd: 1,
					},
					{
						fieldname: `subtask_type_${i}`,
						label: "SubTask Type",
						fieldtype: "Table",
						cannot_add_rows: 0,
						fields: [
							{
								fieldname: "type",
								label: "Type",
								fieldtype: "Link",
								options: "SubTask Types",
								in_list_view: 1,
								reqd: 1,
							},
						],
					}
				);
			});

			let dialog = new frappe.ui.Dialog({
				title: "Generate SubTask from Template",
				fields: fields,
				size: "extra-large",
				primary_action_label: "Generate",
				primary_action(values) {
					frappe.call({
						method: "hrms.hr.doctype.tasks.tasks.create_subtask_from_template",
						args: {
							tasks: frm.doc.name,
							values: values,
							count: subtask.length,
						},
						callback: () => {
							subtask_route = "/app/subtask?tasks=" + frm.doc.name
							open_subtask_btn =
								`<div style='margin-top:12px; display:flex; justify-content:flex-end;'>
						<a class='btn btn-primary' href='${subtask_route}' style='min-width:170px; text-align:center;'>Open SubTask</a></div>`
							msg_html =
								`SubTask for ${frm.doc.task_name} generated successfully from template.`
								+ open_subtask_btn
							frappe.msgprint(msg_html, title = 'SubTask generated successfully');
							frm.reload_doc();
							dialog.hide();
						},
					});
				},
			});

			// Atur get_query untuk setiap PIC field
			subtask.forEach((subtask, i) => {
				const fieldname = `pic_subtask_template_${i}`;
				const field = dialog.get_field(fieldname);

				if (field) {
					field.get_query = () => {
						return {
							filters: [["Employee", "name", "in", team_employees]],
						};
					};
				}
			});

			dialog.show();
			subtask.forEach((sub, i) => {
				const table_field = dialog.fields_dict[`subtask_type_${i}`];
				if (table_field) {
					// Isi dengan 1 row default dari type_template
					table_field.df.data = [
						{
							type: sub.type_template || "",
						},
					];
					table_field.refresh();
				}
			});
		},
	});
}

frappe.ui.form.on("Task PIC", {
	employee: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.employee) return;

		const is_duplicate =
			frm.doc.task_pic.filter((r) => r.employee === row.employee).length > 1;
		if (is_duplicate) {
			frappe.msgprint(
				__("{0} has been choosen as PIC Task member", [
					frappe.model.get_value(cdt, cdn, "employee_name") || "",
				])
			);
			frappe.model.set_value(cdt, cdn, "employee", null);
			frappe.model.set_value(cdt, cdn, "employee_name", null);
			return;
		}
	},
});
