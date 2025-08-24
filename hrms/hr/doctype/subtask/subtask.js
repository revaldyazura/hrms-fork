// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("SubTask", {
	refresh(frm) {
		if (frm.is_new()) {
			frm.set_df_property("status", "options", ["Open"]);
			frm.set_value("status", "Open");
			ensure_ai_button(frm);
			// 	frm.add_custom_button('Agent Suggestion for SubTask Value', async function () {
			// 		if (!frm.doc.subtask_name || !frm.doc.description) {
			// 			frappe.msgprint(__('Please fill Title and Description.'));
			// 			return;
			// 		}

			// 		frappe.prompt([
			// 			{
			// 				fieldtype: 'Data',
			// 				label: 'Title',
			// 				fieldname: 'subtask_name',
			// 				default: frm.doc.subtask_name,
			// 				reqd: 1
			// 			},
			// 			{
			// 				fieldtype: 'Text Editor',
			// 				label: 'Description',
			// 				fieldname: 'description',
			// 				default: frm.doc.description,
			// 				reqd: 1
			// 			}
			// 		], async (values) => {
			// 			try {
			// 				frappe.dom.freeze(__('Contacting Agent...'));

			// 				const response = await frappe.call({
			// 					method: "hrms.hr.doctype.subtask.subtask.ai_suggestion",
			// 					args: {
			// 						title: values.subtask_name,
			// 						description: values.description
			// 					}
			// 				});

			// 				frappe.dom.unfreeze();

			// 				const result = response.message || {};
			// 				if (result.error) {
			// 					throw result.error;
			// 				}

			// 				// ---- helper: escape biar aman di HTML
			// 				const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));

			// 				// ---- mapping nilai level -> Value SubTask (1/2/3)
			// 				const levelToValue = { "basic": 1, "intermediate": 2, "advanced": 3 };
			// 				let suggestedValue = 1; // default Basic
			// 				let topLevelRank = 1;

			// 				const relevant = Array.isArray(result.relevant_skillset) ? result.relevant_skillset : [];
			// 				relevant.forEach(it => {
			// 					const lvl = String(it.level || "").toLowerCase().trim();
			// 					const v = levelToValue[lvl] || 1;
			// 					if (v > topLevelRank) {
			// 						topLevelRank = v;
			// 						suggestedValue = v;
			// 					}
			// 				});

			// 				// ---- bikin tabel skillset (HTML)
			// 				const skillsTableRows = relevant.map((it, idx) => {
			// 					return `
			// 	<tr>
			// 		<td style="vertical-align:top;">${idx + 1}</td>
			// 		<td style="vertical-align:top;">${esc(it.skill)}</td>
			// 		<td style="vertical-align:top;">${esc(it.sub_skill_set)}</td>
			// 		<td style="vertical-align:top;">${esc(it.level)}</td>
			// 		<td style="vertical-align:top;">${esc(it.reasonings)}</td>
			// 	</tr>
			// `;
			// 				}).join("");

			// 				const skillsTable = `
			// 			<div style="max-height:240px; overflow:auto; border:1px solid #e5e7eb; border-radius:6px;">
			// 				<table class="table table-bordered" style="margin:0;">
			// 					<thead>
			// 						<tr>
			// 							<th style="width:40px;">#</th>
			// 							<th>Skill</th>
			// 							<th>Sub Skill</th>
			// 							<th>Level</th>
			// 							<th>Reasoning</th>
			// 						</tr>
			// 					</thead>
			// 					<tbody>${skillsTableRows || `
			// 						<tr><td colspan="5" style="text-align:center;color:#888;">No relevant skills detected</td></tr>
			// 					`}</tbody>
			// 				</table>
			// 			</div>
			// 		`;


			// 				// ---- dialog hasil AI
			// 				const d = new frappe.ui.Dialog({
			// 					title: 'Agent Suggestion',
			// 					fields: [
			// 						{ fieldtype: 'Section Break', label: 'Result' },
			// 						{
			// 							fieldtype: 'HTML', fieldname: 'ai_preview', options: `
			// 							<div style="margin:12px 0 6px; font-weight:600;">Relevant Skillset</div>
			// 							${skillsTable}
			// 						`},
			// 						{ fieldtype: 'Section Break' },
			// 						{
			// 							fieldtype: 'Select',
			// 							fieldname: 'picked_value',
			// 							label: 'Value SubTask',
			// 							options: [
			// 								{ label: '1 - Basic', value: '1' },
			// 								{ label: '2 - Intermediate', value: '2' },
			// 								{ label: '3 - Advanced', value: '3' }
			// 							],
			// 							default: String(suggestedValue),
			// 							description: __('Estimated difficulty level (you can change it).')
			// 						}
			// 					],
			// 					primary_action_label: 'Apply to Form',
			// 					primary_action(values2) {
			// 						if (values2.picked_value) {
			// 							frm.set_value('value', values2.picked_value);
			// 						}
			// 						d.hide();
			// 						frappe.show_alert({ message: __('Agent suggestion applied'), indicator: 'green' });
			// 					},
			// 					secondary_action_label: 'Close',
			// 					secondary_action() { d.hide(); }
			// 				});

			// 				d.show();

			// 			} catch (err) {
			// 				frappe.dom.unfreeze();
			// 				console.error(err);
			// 				frappe.msgprint(__('Failed to contact AI (server).'));
			// 			}
			// 		});
			// 	});
			function ensure_ai_button(frm) {
				// Hapus tombol lama jika ada (biar gak dobel binding)
				if (frm._ai_btn && frm._ai_btn.remove) {
					frm._ai_btn.remove();
					frm._ai_btn = null;
				}

				const hasCache = !!frm._ai_suggestion_cache;

				if (!hasCache) {
					// Mode awal: Generate Suggestion
					frm._ai_btn = frm.add_custom_button('Agent Suggestion for SubTask Value', async function () {
						if (!frm.doc.subtask_name || !frm.doc.description) {
							frappe.msgprint(__('Please fill Title and Description.'));
							return;
						}

						// Prompt user edit judul/desc
						frappe.prompt([
							{ fieldtype: 'Data', label: 'Title', fieldname: 'subtask_name', default: frm.doc.subtask_name, reqd: 1 },
							{ fieldtype: 'Text Editor', label: 'Description', fieldname: 'description', default: frm.doc.description, reqd: 1 }
						], async (values) => {
							try {
								frappe.dom.freeze(__('Contacting Agent...'));
								const response = await frappe.call({
									method: "hrms.hr.doctype.subtask.subtask.ai_suggestion",
									args: { title: values.subtask_name, description: values.description }
								});
								frappe.dom.unfreeze();

								const result = response.message || {};
								if (result.error) throw result.error;

								// ---- hitung suggestedValue & build HTML
								const cache = build_ai_cache(result);
								// taruh di memori form
								frm._ai_suggestion_cache = cache;

								// tampilkan dialog hasil
								show_ai_dialog(frm, cache);

								// ubah tombol jadi "Show Last Agent Suggestion"
								switch_to_show_last_mode(frm);

							} catch (err) {
								frappe.dom.unfreeze();
								console.error(err);
								frappe.msgprint(__('Failed to contact AI (server).'));
							}
						});
					});
				} else {
					// Sudah ada cache: langsung tombol “Show Last Agent Suggestion”
					switch_to_show_last_mode(frm);
				}
			}

			function switch_to_show_last_mode(frm) {
				if (frm._ai_btn && frm._ai_btn.text) {
					frm._ai_btn.text('Show Last Agent Suggestion');
					// bersihkan handler lama lalu pasang baru
					$(frm._ai_btn).off('click').on('click', function () {
						if (frm._ai_suggestion_cache) {
							show_ai_dialog(frm, frm._ai_suggestion_cache);
						} else {
							frappe.show_alert({ message: __('No cached suggestion found'), indicator: 'orange' });
						}
					});
				}
			}

			function build_ai_cache(result) {
				const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
				const levelToValue = { "basic": 1, "intermediate": 2, "advanced": 3 };

				const relevant = Array.isArray(result.relevant_skillset) ? result.relevant_skillset : [];

				let suggestedValue = 1;
				let topLevelRank = 1;
				relevant.forEach(it => {
					const lvl = String(it.level || "").toLowerCase().trim();
					const v = levelToValue[lvl] || 1;
					if (v > topLevelRank) { topLevelRank = v; suggestedValue = v; }
				});

				const rows = relevant.map((it, idx) => `
    <tr>
      <td style="vertical-align:top;">${idx + 1}</td>
      <td style="vertical-align:top;">${esc(it.skill)}</td>
      <td style="vertical-align:top;">${esc(it.sub_skill_set)}</td>
      <td style="vertical-align:top;">${esc(it.level)}</td>
      <td style="vertical-align:top;">${esc(it.reasonings)}</td>
    </tr>
  `).join("");

				const tableHTML = `
    <div style="max-height:240px; overflow:auto; border:1px solid #e5e7eb; border-radius:6px;">
      <table class="table table-bordered" style="margin:0;">
        <thead>
          <tr>
            <th style="width:40px;">#</th>
            <th>Skill</th>
            <th>Sub Skill</th>
            <th>Level</th>
            <th>Reasoning</th>
          </tr>
        </thead>
        <tbody>${rows || `<tr><td colspan="5" style="text-align:center;color:#888;">No relevant skills detected</td></tr>`
					}</tbody>
      </table>
    </div>
  `;

				return {
					raw: result,               // simpan raw kalau perlu
					relevant_skillset: relevant,
					suggestedValue,
					tableHTML
				};
			}

			function show_ai_dialog(frm, cache) {
				const d = new frappe.ui.Dialog({
					title: 'Agent Suggestion',
					fields: [
						{ fieldtype: 'Section Break', label: 'Result' },
						{
							fieldtype: 'HTML', fieldname: 'ai_preview', options: `
        <div style="margin:12px 0 6px; font-weight:600;">Relevant Skillset</div>
        ${cache.tableHTML}
      `},
						{ fieldtype: 'Section Break' },
						{
							fieldtype: 'Select',
							fieldname: 'picked_value',
							label: 'Value SubTask',
							options: [
								{ label: '1 - Basic', value: '1' },
								{ label: '2 - Intermediate', value: '2' },
								{ label: '3 - Advanced', value: '3' }
							],
							default: String(cache.suggestedValue),
							description: __('Estimated difficulty level (you can change it).')
						}
					],
					primary_action_label: 'Apply to Form',
					primary_action(values2) {
						if (values2.picked_value) {
							frm.set_value('value', values2.picked_value);
						}
						d.hide();
						frappe.show_alert({ message: __('Agent suggestion applied'), indicator: 'green' });
					},
					secondary_action_label: 'Close',
					secondary_action() { d.hide(); }
				});

				d.show();
			}

		}
		if (!frm.is_new()) {
			frappe.call({
				method: "hrms.hr.doctype.subtask.subtask.button_evaluation_subtask",
				args: {
					subtask: frm.doc.name
				},
				callback: function (r) {
					if (r.message == 'maintask_owner_done' || r.message == 'pic_task_done' || r.message == 'system_manager_done') {
						frm.add_custom_button("Evaluate This SubTask", () => {
							const dialog = new frappe.ui.Dialog({
								title: "Evaluate SubTask",
								fields: [
									{
										label: "SubTask",
										fieldname: "subtask",
										fieldtype: "Read Only",
										default: frm.doc.name
									},
									{
										label: "SubTask Title",
										fieldname: "subtask_name",
										fieldtype: "Read Only",
										default: frm.doc.subtask_name
									},
									{
										label: "PIC SubTask Name",
										fieldname: "pic_subtask_name",
										fieldtype: "Read Only",
										default: frm.doc.pic_subtask_name
									},
									{
										label: "Target Time Minutes",
										fieldname: "target_time_minutes",
										fieldtype: "Read Only",
										default: frm.doc.target_time_minutes
									},
									{
										label: "Total Time Minutes",
										fieldname: "total_time",
										fieldtype: "Read Only",
										default: frm.doc.total_time
									},
									{
										label: "Performance",
										fieldname: "performance",
										fieldtype: "Int",
										reqd: 1,
										description: "Grade of the selected subtask (1–120)"
									}
								],
								primary_action_label: "Submit",
								primary_action(values) {
									const perf = parseInt(values.performance);

									if (isNaN(perf) || perf < 0 || perf > 120) {
										frappe.msgprint({
											title: __("Invalid Input"),
											message: __("Performance must be a number between 0 and 120."),
											indicator: "red"
										});
										return;
									}

									frappe.call({
										method: "frappe.client.insert",
										args: {
											doc: {
												doctype: "Evaluation",
												subtask: values.subtask,
												performance: perf
											}
										},
										callback: function (r) {
											if (!r.exc) {
												frappe.msgprint("Evaluation submitted successfully.");
												dialog.hide();
											}
										}
									});
								}
							});

							dialog.show();

							// Tambahkan validasi real-time setelah dialog dirender
							setTimeout(() => {
								const input = dialog.fields_dict.performance.$wrapper.find("input");

								input.on("input", function () {
									let value = $(this).val();

									// Hapus karakter non-digit
									if (!/^\d*$/.test(value)) {
										frappe.msgprint({
											title: __("Invalid Input"),
											message: __("Only numeric values are allowed."),
											indicator: "red"
										});
										$(this).val(value.replace(/\D/g, ''));
									}

									if (value === "0") {
										frappe.msgprint({
											title: __("Invalid Value"),
											message: __("Performance must be greater than 0."),
											indicator: "red"
										});
										$(this).val("1"); // Kosongkan input
										return;
									}

									// Batas maksimum
									const numericValue = parseInt($(this).val() || "0");
									if (numericValue > 120) {
										frappe.msgprint("Maximum allowed value is 120.");
										$(this).val("120");
									}
								});
							}, 100);
						});
					} else if (r.message?.status == "Close") {
						frm.add_custom_button("View Evaluation", () => {
							frappe.set_route("Form", "Evaluation", r.message.evaluation_name);
						});
					}
				}
			})
			frappe.call({
				method: "hrms.hr.doctype.subtask.subtask.user_edit_subtask",
				args: {
					subtask_name: frm.doc.name
				},
				callback: function (r) {
					const readonly_fields = ['subtask_name', 'target_time', 'unit_target_time', 'maintask', 'tasks', "pic_subtask", "value", "priority", 'type', 'description'];
					if (frm.doc.status === "Close") {
						frm.set_value("status", "Close");
						frm.set_read_only(true);
						frm.disable_save();
					}
					if (r.message === "pic_subtask") {
						readonly_fields.forEach(field => {
							frm.set_df_property(field, "read_only", 1);
							// frm.set_value("status", "Open");
						});
						frm.set_df_property("status", "options", ["Open", "In Progress", "Pause", "Done"]);
					} else if (r.message == "task_pics" || r.message == "owner_task") {
						frm.set_df_property("status", "options", ["Open", "In Progress", "Pause", "Done", "Cancel"]);
					} else if (r.message === "none") {
						frm.set_read_only(true);
						frm.disable_save();
					}
				}
			});
		}
	},
	onload: function (frm) {
		frm.set_query("tasks", function () {
			return {
				query: "hrms.hr.doctype.subtask.subtask.get_task_with_same_pic"
			};
		});
		frm.set_query("pic_subtask", function () {
			if (!frm.doc.tasks) {
				frappe.msgprint("Choose the task field first.");
				return {};
			}
			return {
				query: "hrms.hr.doctype.subtask.subtask.get_employees_by_team",
				filters: {
					tasks: frm.doc.tasks
				}
			};
		});
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
							indicator: "red"
						});
						$(this).val(value.replace(/\D/g, ""));
					}
					if (value === "0") {
						frappe.msgprint({
							title: __("Invalid Value"),
							message: __("Target Time must be greater than 0."),
							indicator: "red"
						});
						$(this).val("1"); // Kosongkan input
						return;
					}
				});
			}, 300);
			setTimeout(() => {
				const field_wrapper = frm.fields_dict["subtask_name"];
				if (!field_wrapper) return;

				const input = field_wrapper.$wrapper.find("input");

				input.on("input", function () {
					const value = $(this).val();
					if (value.length === 140) {
						frappe.msgprint({
							title: __("Limit Reached"),
							message: __("You have reached the maximum of 140 characters for SubTask Title."),
							indicator: "yellow"
						});
						$(this).val(value.slice(0, 140)); // potong string agar tetap maksimal 140
					}
				});
			}, 300);
			// Delay sedikit agar field render dulu
		});
		if (!frm.is_new()) {

		}
	},

});
