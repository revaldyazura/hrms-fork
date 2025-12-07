// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("SubTask", {
	refresh(frm) {
		let workspace = 'Task Management';

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: workspace,
			doctype: frm.doctype,
			type: 'Form'
		};
		frappe.breadcrumbs.update();

		if (frm.is_new()) {
			frm.set_df_property("status", "options", ["Open"]);
			frm.set_value("status", "Open");
			frm.set_df_property("total_time", "read_only", 1);

			ensure_subtask_value_agent_button(frm);
			ensure_pic_subtask_agent_button(frm);

			function ensure_subtask_value_agent_button(frm) {
				// Hapus tombol lama jika ada (biar gak dobel binding)
				if (frm._agent_subtask_value_btn && frm._agent_subtask_value_btn.remove) {
					frm._agent_subtask_value_btn.remove();
					frm._agent_subtask_value_btn = null;
				}

				const hasCache = !!frm._agent_subtask_value_cache;

				if (!hasCache) {
					// Mode awal: Generate Suggestion
					frm._agent_subtask_value_btn = frm.add_custom_button('Agent Suggestion for SubTask Value', async function () {
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
								frappe.dom.freeze(__('Contacting Agent Subtask Value Suggestion...'));
								const response = await frappe.call({
									method: "hrms.hr.doctype.subtask.subtask.subtask_value_agent_suggestion",
									args: { title: values.subtask_name, description: values.description }
								});
								frappe.dom.unfreeze();

								const result = response.message || {};
								if (result.error) throw result.error;

								// ---- hitung suggestedValue & build HTML
								const cache = build_agent_subtask_value_cache(result);
								// taruh di memori form
								frm._agent_subtask_value_cache = cache;

								// tampilkan dialog hasil
								show_agent_subtask_value(frm, cache);

								// ubah tombol jadi "Show Last Agent Suggestion"
								show_last_subtask_value(frm);

							} catch (err) {
								frappe.dom.unfreeze();
								console.error(err);
								frappe.msgprint(__('Failed to contact Agent Subtask Value (server).'));
							}
						});
					}, __('Actions'));
				} else {
					// Sudah ada cache: langsung tombol “Show Last Agent Suggestion”
					show_last_subtask_value(frm);
				}
			}

			function show_last_subtask_value(frm) {
				if (frm._agent_subtask_value_btn && frm._agent_subtask_value_btn.text) {
					frm._agent_subtask_value_btn.text('Show Last Subtask Value Suggestion');
					// bersihkan handler lama lalu pasang baru
					$(frm._agent_subtask_value_btn).off('click').on('click', function () {
						if (frm._agent_subtask_value_cache) {
							show_agent_subtask_value(frm, frm._agent_subtask_value_cache);
						} else {
							frappe.show_alert({ message: __('No cached suggestion found'), indicator: 'orange' });
						}
					});
				}
			}

			function build_agent_subtask_value_cache(result) {
				const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
				const levelToValue = { "basic": 1, "intermediate": 2, "advanced": 3 };

				const title = result.task || '';
				const description = result.description || '';
				const relevant = Array.isArray(result.relevant_skillset) ? result.relevant_skillset : [];

				// ---- helper: normalisasi skor
				const getScore = (it) => {
					// prioritas: percentage_score (0..1), fallback: percentage_score_str (e.g. "85%")
					if (it.percentage_score != null && it.percentage_score !== "") {
						const v = Number(it.percentage_score);
						return isFinite(v) ? v : 0;
					}
					if (it.percentage_score_str) {
						const s = String(it.percentage_score_str).replace("%", "").trim();
						const v = Number(s);
						return isFinite(v) ? v / 100 : 0;
					}
					return 0;
				};

				// ---- pilih item dengan skor tertinggi
				let bestIdx = -1;
				let bestScore = -1;
				relevant.forEach((it, idx) => {
					const sc = getScore(it);
					if (sc > bestScore) {
						bestScore = sc;
						bestIdx = idx;
					}
				});

				// suggestedValue: ambil level dari item skor tertinggi
				let suggestedValue = 1; // default
				if (bestIdx >= 0) {
					const lvl = String(relevant[bestIdx].level || "").toLowerCase().trim();
					suggestedValue = levelToValue[lvl] || 1;
				}

				// ---- build rows sesuai kolom baru
				const rows = relevant.map((it, idx) => {
					const scoreStr =
						it.percentage_score_str != null && it.percentage_score_str !== ""
							? String(it.percentage_score_str)
							: (getScore(it) * 100).toFixed(0) + "%"; // fallback kalau _str tidak ada
					return `
								<tr>
									<td style="vertical-align:top;">${idx + 1}</td>
									<td style="vertical-align:top;">${esc(it.skill)}</td>
									<td style="vertical-align:top;">${esc(it.sub_skill_set)}</td>
									<td style="vertical-align:top;">${esc(it.level)}</td>
									<td style="vertical-align:top;">${esc(it.reasonings)}</td>
									<td style="vertical-align:top;">${esc(scoreStr)}</td>
									<td style="vertical-align:top;">${esc(it.specialized)}</td>
									<td style="vertical-align:top;">${esc(it.reasoning_specialized)}</td>
								</tr>
							`;
				}).join("");

				const titleHtml = `<div style="margin:8px 0 6px;"><span style="font-weight:600;">Title: </span>${title}</div>`;
				const descHtml = `<div style="margin:0 0 6px;"><span style="font-weight:600;">Description: </span>${description}</div>`;

				const tableHTML = `
						${titleHtml}
						${descHtml}
					<div style="margin:12px 0 6px; font-weight:600;">Relevant Skillset</div>
					<div style="max-height:240px; overflow:auto; border:1px solid #e5e7eb; border-radius:6px;">
					<table class="table table-bordered" style="margin:0;">
						<thead>
						<tr>
							<th style="width:40px;">#</th>
							<th>Skill</th>
							<th>Sub Skill</th>
							<th>Level</th>
							<th>Reasoning</th>
							<th>Score</th>
							<th>Specialized</th>
							<th>Reasoning (Specialized)</th>
						</tr>
						</thead>
						<tbody>${rows || `<tr><td colspan="8" style="text-align:center;color:#888;">No relevant skills detected</td></tr>`
					}</tbody>
					</table>
					</div>
				`;

				return {
					raw: result,
					relevant_skillset: relevant,
					suggestedValue,    // ← sekarang diambil dari level milik skor tertinggi
					tableHTML,
					bestIndex: bestIdx,
					bestScore: bestScore
				};
			}

			function show_agent_subtask_value(frm, cache) {
				const d = new frappe.ui.Dialog({
					title: 'Agent SubTask Value Suggestion',
					size: 'large',
					fields: [
						{
							fieldtype: 'HTML', fieldname: 'agent_preview', options: `${cache.tableHTML}`
						},
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
						frappe.show_alert({ message: __('Subtask value suggestion applied'), indicator: 'green' });
					},
					secondary_action_label: 'Close',
					secondary_action() { d.hide(); }
				});

				d.show();
			}

			function ensure_pic_subtask_agent_button(frm) {
				// Hapus tombol lama jika ada (biar gak dobel binding)
				if (frm._agent_pic_subtask_btn && frm._agent_pic_subtask_btn.remove) {
					frm._agent_pic_subtask_btn.remove();
					frm._agent_pic_subtask_btn = null;
				}

				const hasCache = !!frm._agent_pic_subtask_cache;

				if (!hasCache) {
					// Mode awal: Generate Suggestion
					frm._agent_pic_subtask_btn = frm.add_custom_button('Agent Suggestion for PIC SubTask', async function () {
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
								frappe.dom.freeze(__('Contacting Agent PIC Subtask Suggestion...'));
								const response = await frappe.call({
									method: "hrms.hr.doctype.subtask.subtask.pic_subtask_agent_suggestion",
									args: { title: values.subtask_name, description: values.description }
								});
								frappe.dom.unfreeze();

								const result = response.message || {};
								if (result.error) throw result.error;

								// ---- hitung suggestedValue & build HTML
								const cache = build_agent_pic_subtask_cache(result);
								// taruh di memori form
								frm._agent_pic_subtask_cache = cache;

								// tampilkan dialog hasil
								show_agent_pic_subtask(frm, cache);

								// ubah tombol jadi "Show Last Agent Suggestion"
								show_last_pic_subtask(frm);

							} catch (err) {
								frappe.dom.unfreeze();
								console.error(err);
								frappe.msgprint(__('Failed to contact Agent PIC Subtask (server).'));
							}
						});
					}, __('Actions'));
				} else {
					// Sudah ada cache: langsung tombol “Show Last Agent Suggestion”
					show_last_pic_subtask(frm);
				}
			}

			function show_last_pic_subtask(frm) {
				if (frm._agent_pic_subtask_btn && frm._agent_pic_subtask_btn.text) {
					frm._agent_pic_subtask_btn.text('Show Last PIC Subtask Suggestion');
					// bersihkan handler lama lalu pasang baru
					$(frm._agent_pic_subtask_btn).off('click').on('click', function () {
						if (frm._agent_pic_subtask_cache) {
							show_agent_pic_subtask(frm, frm._agent_pic_subtask_cache);
						} else {
							frappe.show_alert({ message: __('No cached suggestion found'), indicator: 'orange' });
						}
					});
				}
			}

			function build_agent_pic_subtask_cache(result) {
				const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));

				const title = result.task || '';
				const description = result.description || '';
				const specialized_required = Array.isArray(result.specialized_required) ? result.specialized_required : [];
				const candidates = Array.isArray(result.candidates) ? result.candidates : [];

				// sort kandidat dari score tertinggi
				candidates.sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0));

				// kandidat terbaik (suggested PIC)
				const best = candidates[0] || null;
				const suggestedPIC = best ? String(best.name || '') : '';

				// build baris tabel kandidat
				const rows = candidates.map((it, idx) => {
					const scoreStr = (it.score_str && String(it.score_str).trim())
						? String(it.score_str).trim()
						: `${Math.round((Number(it.score) || 0) * 100)}%`;

					const matched = Array.isArray(it.matched_specialized) ? it.matched_specialized.join(', ') : '';
					return `
						<tr>
							<td style="vertical-align:top;">${idx + 1}</td>
							<td style="vertical-align:top;font-weight:600;">${esc(it.name)}</td>
							<td style="vertical-align:top;">${esc(scoreStr)}</td>
							<td style="vertical-align:top;">${esc(matched)}</td>
							<td style="vertical-align:top; white-space:pre-wrap;">${esc(it.pro || '')}</td>
							<td style="vertical-align:top; white-space:pre-wrap;">${esc(it.cons || '')}</td>
						</tr>
					`;
				}).join("");

				// header “Specialized Required”
				const titleHtml = `<div style="margin:8px 0 6px;"><span style="font-weight:600;">Title: </span>${title}</div>`;
				const descHtml = `<div style="margin:0 0 6px;"><span style="font-weight:600;">Description: </span>${description}</div>`;
				// gabungkan
				const specReqHtml = specialized_required.length
					? `<div style="margin:8px 0 6px;"><span style="font-weight:600;">Specialized Required:</span> ${specialized_required.map(esc).join(', ')}</div>`
					: '';
				const candidatesHtml = `<div style="margin:8px 0 6px;"><span style="font-weight:600;">Candidates:</span></div>`;

				const tableHTML = `
						${titleHtml}
						${descHtml}
						${specReqHtml}
						${candidatesHtml}
						<div style="max-height:300px; overflow:auto; border:1px solid #e5e7eb; border-radius:6px;">
						<table class="table table-bordered" style="margin:0;">
							<thead>
							<tr>
								<th style="width:40px;">#</th>
								<th>Name</th>
								<th>Score</th>
								<th>Matched Specialized</th>
								<th>Pros</th>
								<th>Cons</th>
							</tr>
							</thead>
							<tbody>${rows || `<tr><td colspan="6" style="text-align:center;color:#888;">No candidates</td></tr>`
					}</tbody>
						</table>
						</div>
					`;

				return {
					raw: result,
					specialized_required,
					candidates,
					suggestedPIC,   // ← nama kandidat score tertinggi
					tableHTML
				};
			}

			function show_agent_pic_subtask(frm, cache) {
				const candidateOptions = (cache.candidates || []).map(c => ({ label: c.name, value: c.name }));

				const d = new frappe.ui.Dialog({
					title: 'Agent PIC Subtask Suggestion',
					size: 'large',
					fields: [
						{
							fieldtype: 'HTML',
							fieldname: 'agent_preview',
							options: `${cache.tableHTML}`
						},
						{ fieldtype: 'Section Break' },
						{
							fieldtype: 'Select',
							fieldname: 'picked_pic',
							label: 'PIC Candidate',
							options: candidateOptions,
							default: cache.suggestedPIC || (candidateOptions[0]?.value || ''),
							description: __('Pick one of the suggested candidates.')
						}
					],
					primary_action_label: 'Apply to Form',
					primary_action: async function (values) {
						const pickedName = values.picked_pic;
						if (!pickedName) return;

						try {
							frappe.dom.freeze(__('Resolving Employee...'));
							const resp = await frappe.call({
								method: "hrms.hr.doctype.subtask.subtask.get_employee_from_agent_data",
								args: { name: pickedName, status: "Active", limit: 10 }
							});
							frappe.dom.unfreeze();

							const matches = resp.message || [];

							if (matches.length === 1) {
								await frm.set_value('pic_subtask', matches[0].name);
								await frm.set_value('pic_subtask_name', matches[0].employee_name);
								frappe.show_alert({ message: __('PIC applied: ') + matches[0].employee_name, indicator: 'green' });
								d.hide();
								return;
							}

							if (matches.length > 1) {
								const opts = matches.map(m => ({
									label: `${m.employee_name}  •  ${m.name}` + (m.department ? `  •  ${m.department}` : ''),
									value: m.name
								}));

								const pickDlg = new frappe.ui.Dialog({
									title: __('Select Employee for ') + pickedName,
									fields: [
										{
											fieldtype: 'HTML',
											fieldname: 'hint',
											options: `<div style="margin:6px 0 10px; color:#6b7280;">
											Agent suggested name: <b>${frappe.utils.escape_html(pickedName)}</b>
											</div>`
										},
										{
											fieldtype: 'Select',
											fieldname: 'emp',
											label: 'Employee',
											options: opts,
											reqd: 1
										}
									],
									primary_action_label: 'Apply',
									primary_action: async (vals) => {
										const chosenId = vals.emp;
										try {
											const { message } = await frappe.db.get_value('Employee', chosenId, ['employee_name']);
											await frm.set_value('pic_subtask', chosenId);
											await frm.set_value('pic_subtask_name', (message && message.employee_name) || chosenId);
											frappe.show_alert({ message: __('PIC applied'), indicator: 'green' });
											pickDlg.hide();
											d.hide();
										} catch (e) {
											console.error(e);
											frappe.msgprint(__('Failed to fetch Employee name'));
										}
									}
								});
								pickDlg.show();
								return;
							}

							return open_manual_employee_picker(frm, pickedName, d);

						} catch (e) {
							frappe.dom.unfreeze();
							console.error(e);
							frappe.msgprint(__('Failed to resolve Employee'));
						}
					},
					secondary_action_label: 'Close',
					secondary_action() { d.hide(); }
				});

				d.show();
			}

			function open_manual_employee_picker(frm, agentName, parentDialog) {
				const dlg = new frappe.ui.Dialog({
					title: __('Pick Employee Manually'),
					fields: [
						{
							fieldtype: 'HTML',
							fieldname: 'agent_hint',
							options: `<div style="margin:6px 0 10px; color:#6b7280;">
								Agent suggested name: <b>${frappe.utils.escape_html(agentName || '')}</b>
							</div>`
						},
						{
							fieldtype: 'Link',
							fieldname: 'emp',
							label: 'Employee',
							options: 'Employee',
							reqd: 1,
							get_query() {
								return { filters: { status: 'Active' } };
							},
							// ← fetch nama tiap kali user memilih/ubah employee
							change: async () => {
								const emp = dlg.get_value('emp');
								if (!emp) return dlg.set_value('emp_name', '');
								const { message } = await frappe.db.get_value('Employee', emp, ['employee_name']);
								dlg.set_value('emp_name', message?.employee_name || '');
							}
						},
						{
							fieldtype: 'Data',
							fieldname: 'emp_name',
							label: 'Employee Name',
							read_only: 1
						}
					],
					primary_action_label: 'Apply',
					primary_action: async (vals) => {
						if (!vals.emp) return;
						try {
							const { message } = await frappe.db.get_value('Employee', vals.emp, ['employee_name']);
							await frm.set_value('pic_subtask', vals.emp);
							await frm.set_value('pic_subtask_name', (message && message.employee_name) || vals.emp);
							frappe.show_alert({ message: __('PIC applied manually'), indicator: 'green' });
							dlg.hide();
							if (parentDialog) parentDialog.hide();
						} catch (err) {
							console.error(err);
							frappe.msgprint(__('Failed to fetch Employee name'));
						}
					}
				});

				dlg.show();
			}


		}
		if (!frm.is_new()) {

			frappe.call({
				method: "hrms.hr.doctype.subtask.subtask.button_evaluation_subtask",
				args: {
					subtask: frm.doc.name
				},
				callback: function (r) {
					if (r.message == 'maintask_owner_done' || r.message == 'pic_task_done' || r.message == 'administrator_done') {
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
											frm.reload_doc()
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
						}, __('Actions'));
					} else if (r.message?.status == "Close") {
						frm.add_custom_button("View Evaluation", () => {
							frappe.set_route("Form", "Evaluation", r.message.evaluation_name);
						}, __('Actions'));
					}
				}
			})
			frappe.call({
				method: "hrms.hr.doctype.subtask.subtask.user_edit_subtask",
				args: { subtask_name: frm.doc.name },
				callback: function (r) {
					apply_subtask_access_and_status(frm, r.message || "");
				}
			});
			// ================= Refactored Permission & Status Logic =================
			function apply_subtask_access_and_status(frm, flagString) {
				const flags = parse_role_flags(flagString);
				const status = frm.doc.status;
				frm.set_df_property('total_time', 'read_only', 1);

				// 4. Global override: status Close
				if (status === 'Close') {
					frm.set_value('status', 'Close'); // ensure consistent
					frm.set_read_only(true);
					frm.disable_save();
					return;
				}

				// NONE scenario
				if (flags.none) {
					frm.set_read_only(true);
					frm.disable_save();
					return;
				}

				// Additional permission: when status is Done -> only allow editing the status field
				if (status === 'Done' || status === 'Cancel') {
					try {
						const fields = frm.fields_dict || {};
						Object.keys(fields).forEach((fn) => {
							if (fn !== 'status') {
								frm.set_df_property(fn, 'read_only', 1);
							}
						});
						// make sure status stays editable
						frm.set_df_property('status', 'read_only', 0);
						// allow editing total_time when server indicates the current user
						// has any of the assign_by_maintask privileges that permit it.
						if (
							(flagString.includes("assign_by_maintask") ||
								flagString.includes("assign_by_maintask_supervisor") ||
								flagString.includes("assign_by_maintask_manager"))
						) {
							frm.set_df_property('total_time', 'read_only', 0);
						}
					} catch (e) {
						// noop
					}

					// compute and set status options as per scenario
					const scenarioForDone = derive_scenario(flags);
					const optsForDone = compute_status_options(scenarioForDone, status);
					const finalOptsForDone = ensure_includes(optsForDone, status);
					frm.set_df_property('status', 'options', finalOptsForDone);
					// re-ensure status stays editable (compute_status_options may toggle it)
					frm.set_df_property('status', 'read_only', 0);
					return;
				}

				const scenario = derive_scenario(flags); // 'PIC_ONLY' | 'PIC_PLUS' | 'OWNER_ONLY'

				// Apply field-level rules
				apply_field_rules(frm, scenario, status);

				// Compute status options
				const opts = compute_status_options(scenario, status);

				// Safety: include current status if missing
				const finalOpts = ensure_includes(opts, status);
				frm.set_df_property('status', 'options', finalOpts);
			}

			// Parse server flags
			function parse_role_flags(str) {
				const s = str || "";
				const has = (k) => s.includes(k);
				return {
					pic_subtask: has("pic_subtask"),
					owner_subtask: has("owner_subtask"),
					task_pics: has("task_pics"),
					owner_task: has("owner_task"),
					none: has("none")
				};
			}

			// Derive scenario
			function derive_scenario(f) {
				const ownerGroup = f.owner_subtask || f.task_pics || f.owner_task;
				if (f.pic_subtask && !ownerGroup) return 'PIC_ONLY';
				if (f.pic_subtask && ownerGroup) return 'PIC_PLUS';
				if (!f.pic_subtask && ownerGroup) return 'OWNER_ONLY';
				return 'NONE';
			}

			// Apply field locks
			function apply_field_rules(frm, scenario, status) {
				const readonlyPicOnlyFields = [
					'subtask_name', 'target_time', 'unit_target_time', 'maintask',
					'tasks', 'pic_subtask', 'value', 'priority', 'type', 'description'
				];

				if (scenario === 'PIC_ONLY') {
					readonlyPicOnlyFields.forEach(f => frm.set_df_property(f, 'read_only', 1));
				} else if (scenario === 'PIC_PLUS') {
					// pic_subtask hanya editable saat Open
					frm.set_df_property('pic_subtask', 'read_only', status !== 'Open');
				} else if (scenario === 'OWNER_ONLY') {
					// pic_subtask hanya editable saat Open
					frm.set_df_property('pic_subtask', 'read_only', status !== 'Open');
					// Jika sudah bukan Open/Cancel dan status ke In Progress / Pause / Done -> nanti kita lock di compute (status read_only)
				}
			}

			// Build status options per scenario & current status
			function compute_status_options(scenario, status) {
				if (scenario === 'PIC_ONLY') {
					switch (status) {
						case 'Open': return ['Open', 'In Progress'];
						case 'In Progress': return ['In Progress', 'Pause', 'Done'];
						case 'Pause': return ['Pause', 'In Progress'];
						case 'Done': return ['Done', 'In Progress'];
						case 'Cancel': return ['Cancel']; // fallback
						default: return [status];
					}
				}

				if (scenario === 'PIC_PLUS') {
					if (status === 'Open') return ['Open', 'In Progress', 'Cancel'];
					if (status === 'Cancel') return ['Cancel', 'Open'];
					// reuse PIC_ONLY mapping for the rest:
					return compute_status_options('PIC_ONLY', status);
				}

				if (scenario === 'OWNER_ONLY') {
					if (status === 'Open') return ['Open', 'Cancel'];
					if (status === 'Cancel') return ['Cancel', 'Open'];
					if (['In Progress', 'Pause', 'Done'].includes(status)) {
						// Lock—only current
						frm.set_df_property('status', 'read_only', 1);
						return [status];
					}
					return [status];
				}

				// NONE / fallback
				return [status];
			}

			// Ensure current status always inside options
			function ensure_includes(list, value) {
				if (!value) return list;
				return list.includes(value) ? list : [value, ...list];
			}
		}

		if (frm.doc.maintask) {
			sessionStorage.setItem('prefill_fusion_maintask', frm.doc.maintask);
		} else {
			// optional: remove jika tidak ada maintask
			sessionStorage.removeItem('prefill_fusion_maintask');
		}
	},
	onload: function (frm) {
		if (frm.doc.maintask) {
			sessionStorage.setItem('prefill_fusion_maintask', frm.doc.maintask);
		}
		if (!frm.doc.choose_maintask_manually) {
			frm.set_query("tasks", function () {
				return {
					query: "hrms.hr.doctype.subtask.subtask.get_task_with_same_pic"
				};
			});
		}
		frm.set_query("pic_subtask", function () {
			if (!frm.doc.tasks) {
				frappe.msgprint("Choose the task field first.");
				return {};
			}
			if (!frm.doc.maintask) {
				frappe.msgprint("Choose the maintask field first.");
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
		frm.fields_dict["issues_type"].grid.get_field("issue").get_query = function (
			doc,
			cdt,
			cdn
		) {
			if (!frm.doc.maintask || !frm.doc.tasks) {
				frappe.msgprint("Choose the maintask / task field first.");
				return {};
			}
			return {
				query: "hrms.hr.doctype.subtask.subtask.get_issues_by_maintask",
				filters: {
					maintask: frm.doc.maintask,
				},
			};
		};
	},
	choose_maintask_manually: function (frm) {
		if (frm.doc.choose_maintask_manually) {
			frm.set_df_property("maintask", "fetch_from", 0);
			frm.set_df_property("maintask", "permlevel", 0);
			frm.set_df_property("maintask", "read_only", 0);
			frm.set_df_property("maintask", "hidden", 0);
			frm.set_df_property("maintask", "reqd", 1);
			frappe.show_alert({ message: __('Maintask can be selected manually now'), indicator: 'green' });
			frm.set_query("tasks", function () {
				return {
					query: "hrms.hr.doctype.subtask.subtask.get_task_with_same_pic_and_maintask",
					filters: { maintask: frm.doc.maintask }
				};
			});
		} else {
			if (frm.doc.maintask) {
				// jika choose_maintask_manually di-uncheck, kita set maintask ke fetch_from
				frm.set_value("maintask", "");
				frm.set_value("tasks", "");
			}
			frm.set_df_property("maintask", "fetch_from", "tasks.maintask");
			frm.set_df_property("maintask", "permlevel", 2);
			frm.set_df_property("maintask", "read_only", 1);
			frappe.show_alert({ message: __('Maintask will follow Tasks again'), indicator: 'blue' });
			frm.set_query("tasks", function () {
				return {
					query: "hrms.hr.doctype.subtask.subtask.get_task_with_same_pic"
				};
			});
		}
	},
	maintask: function (frm) {
		// when maintask field changed in UI:
		// - if user is in manual mode, clear the `tasks` field so it doesn't conflict
		// - update sessionStorage prefill_fusion_maintask with the new value
		if (frm.doc.choose_maintask_manually) {
			// clear related task when maintask manually changed
			frm.set_value('tasks', '');
		}

		if (frm.doc.maintask) {
			sessionStorage.setItem('prefill_fusion_maintask', frm.doc.maintask);
		} else {
			sessionStorage.removeItem('prefill_fusion_maintask');
		}
	}
});
