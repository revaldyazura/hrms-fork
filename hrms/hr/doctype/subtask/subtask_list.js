frappe.listview_settings['SubTask'] = {
	get_indicator: function (doc) {
		let color_map = {
			"Done": "green",
			"Resolved": "yellow",
			"Cancel": "red",
			"Pause": "orange",
			"Open": "grey",
			"Close": "purple",
			"In Progress": "blue" // pakai string key dan warna valid CSS
		};

		return [__(doc.status), color_map[doc.status] || "grey", "status,=," + doc.status];
	},
	add_fields: ['maintask', 'maintask_name', 'tasks', 'tasks_name', 'pic_subtask', 'pic_subtask_name', 'priority'],

	formatters: {
		// maintask(val, df, doc) {
		//  return doc.maintask_name || val;
		// },
		tasks(val, df, doc) {
			return doc.tasks_name || val;
		}, pic_subtask(val, df, doc) {
			return doc.pic_subtask_name || val;
		},
		priority(val, df, doc) {
			const priority_color = {
				'Low': '#28a745',
				'Medium': '#ffc107',
				'High': '#fd7e14',
				'Urgent': '#dc3545'
			};
			const pr = doc.priority || val || '';
			const color = priority_color[pr] || 'grey';
			// return an inline-styled badge; using translation function for label
			return `<span style="display:inline-block;padding:2px 8px;border-radius:10px;background:${color};color:#fff;font-size:0.85em;">${__(pr)}</span>`;
		}
	},
	refresh(listview) {
		let workspace = 'Task Management';

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: workspace,
			type: 'List'
		};
		frappe.breadcrumbs.update();

		// allow subject column to wrap to multiple lines (no ellipsis truncation)
		const applySubjectWrap = () => {
			document.querySelectorAll('.list-row-container .list-subject').forEach(function (col) {
				// sizing
				// col.style.maxWidth = "25vw";
				// col.style.minWidth = "25vw";
				// wrapping
				col.classList.remove('ellipsis');
				col.style.whiteSpace = 'normal';
				col.style.overflow = 'visible';
				col.style.textOverflow = 'initial';
				// level container aligns center by default; align to start so multi-lines look OK
				col.style.alignItems = 'center';

				// remove ellipsis from parent left column (if any)
				const left = col.closest('.level-left');
				if (left) left.classList.remove('ellipsis');

				// ensure inner level-item can shrink/wrap
				col.querySelectorAll('.level-item').forEach(item => {
					item.style.minWidth = '0';
					item.style.maxWidth = '100%';
					item.style.justifyContent = 'flex-start';
					// let text take available width
					if (!item.classList.contains('select-like')) {
						item.style.flex = '1 1 auto';
					}
					item.classList.remove('ellipsis');
				});

				// remove ellipsis on inner wrappers/anchor so text can wrap
				const bold = col.querySelector('.bold');
				if (bold) bold.classList.remove('ellipsis');
				const a = col.querySelector('a.ellipsis, a');
				if (a) {
					a.classList.remove('ellipsis');
					// apply 2-line clamp with ellipsis
					if (!document.getElementById('subtask-multiline-clamp-style')) {
						const style = document.createElement('style');
						style.id = 'subtask-multiline-clamp-style';
						style.textContent = `
							.subtask-title-clamp {\n								display: -webkit-box;\n								-webkit-line-clamp: 2;\n								-webkit-box-orient: vertical;\n								overflow: hidden;\n								text-overflow: ellipsis;\n								white-space: normal !important;\n								word-break: break-word;\n							}
						`;
						document.head.appendChild(style);
					}
					a.classList.add('subtask-title-clamp');
				}
			})
		};
		// run after rows are appended
		requestAnimationFrame(applySubjectWrap);
		setTimeout(applySubjectWrap, 0);
		setTimeout(applySubjectWrap, 50);

		// bind dependent filter: limit `tasks` options by selected `maintask`
		const ensureDependentTaskFilter = () => {
			// Prefer v16 ListView page fields
			const page_fields = listview && listview.page && listview.page.fields_dict;
			const filter_area = listview && listview.filter_area; // fallback for older builds
			console.log('page fields', page_fields);
			console.log('filter_area', filter_area);
			if (!page_fields && !filter_area) return;

			const getMaintaskFilterValue = () => {
				// Prefer page fields in v16
				const mt_field = page_fields && page_fields.maintask;
				if (mt_field) {
					if (mt_field.value) return mt_field.value;
				}
			};

			const bindTasksQuery = () => {
				// Bind on page fields (v16)
				const tasks_field = page_fields && page_fields.tasks;
				console.log('task field', tasks_field);
				if (tasks_field) {
					const mt = getMaintaskFilterValue();
					console.log('maintask filter value', mt);
					const query_fn = () => ({ filters: { maintask: getMaintaskFilterValue() } });

					if (mt) {
						if (!tasks_field.set_query) {
							tasks_field.df.get_query = query_fn;
							tasks_field.get_query = query_fn;
						}
					} else {
						if (tasks_field.df) {
							delete tasks_field.df.get_query;
						}
						if (tasks_field.get_query) {
							delete tasks_field.get_query;
						}
					}
				}
			};

			// initial bind
			bindTasksQuery();

			// re-bind when filters UI changes (user edits maintask filter)
			const maybeRebind = () => setTimeout(bindTasksQuery, 0);
			if (filter_area && filter_area.wrapper) {
				filter_area.wrapper.addEventListener('change', maybeRebind);
				filter_area.wrapper.addEventListener('click', maybeRebind);
			}
		};

		// run after standard filters are constructed; try multiple times to ensure controls exist
		const attempts = [0, 50, 150, 300];
		attempts.forEach(ms => setTimeout(ensureDependentTaskFilter, ms));
	},
	onload(listview) {
		// hindari loop set_route berulang
		if (window.__subtask_pic_filter_applied) return;

		// Jika user sudah menambahkan query param di address bar (contoh ?maintask=MT-...) atau
		// framework sudah memiliki route_options (filter bawaan), jangan override route otomatis PIC.
		try {
			const has_query_params = (() => {
				// cek URL search (?a=1&b=2)
				const qs = new URLSearchParams(window.location.search || '');
				if ([...qs.keys()].length) return true;
				// cek route_options yang mungkin terisi oleh Frappe
				if (frappe.route_options && Object.keys(frappe.route_options).length) return true;
				return false;
			})();
			if (has_query_params) return; // jangan paksa filter PIC
		} catch (e) {
			console.warn('Check query params failed, fallback continue:', e);
		}

		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Employee',
				filters: { user_id: frappe.session.user },
				fieldname: 'name'
			},
			callback: (r) => {
				const employee_id = r?.message?.name;
				if (!employee_id) return;

				window.__subtask_pic_filter_applied = true;

				if (frappe.boot?.versions?.frappe?.startsWith?.('15')) {
					frappe.set_route('List', 'SubTask', 'List', { 'pic_subtask': ['=', employee_id] });
				} else {
					frappe.set_route('List', 'SubTask', { 'pic_subtask': ['=', employee_id] });
				}
			}
		});
	}
};
